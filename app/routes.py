from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
)
from .models import db, StockCategory, Office, StockTransaction, Invoice
from .utils import get_financial_year, generate_next_invoice_number, generate_invoice_pdf
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.app_context_processor
def utility_processor():
    """Add utility functions to template context."""
    return {
        'now': datetime.utcnow
    }

@main_bp.route('/')
def index():
    """Home page, redirects to stock report."""
    return redirect(url_for('main.stock_report'))

# --- Stock Category Management ---

@main_bp.route('/stock/manage', methods=['GET', 'POST'])
def manage_stock():
    """Add/Delete Stock Categories."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                existing = StockCategory.query.filter(StockCategory.name.ilike(name)).first() # Case-insensitive check
                if not existing:
                    try:
                        new_category = StockCategory(name=name, current_stock=0)
                        db.session.add(new_category)
                        db.session.commit()
                        flash(f'Stock category "{name}" added successfully.', 'success')
                    except IntegrityError:
                        db.session.rollback()
                        flash(f'Stock category "{name}" already exists (database constraint).', 'warning')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error adding stock category: {e}', 'danger')
                        current_app.logger.error(f"Error adding stock category: {e}")
                else:
                    flash(f'Stock category "{name}" already exists.', 'warning')
            else:
                flash('Stock category name cannot be empty.', 'danger')
        elif action == 'delete':
            category_id = request.form.get('category_id')
            category = db.session.get(StockCategory, category_id) # Use db.session.get for primary key lookup
            if category:
                 # Basic check: prevent deletion if stock exists or transactions/invoices exist
                if category.current_stock != 0 or category.transactions or category.invoices:
                     flash(f'Cannot delete category "{category.name}" as it has non-zero stock, associated transactions, or invoices.', 'danger')
                else:
                    try:
                        db.session.delete(category)
                        db.session.commit()
                        flash(f'Stock category "{category.name}" deleted.', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error deleting stock category: {e}', 'danger')
                        current_app.logger.error(f"Error deleting stock category {category.name}: {e}")

            else:
                flash('Stock category not found.', 'danger')
        return redirect(url_for('main.manage_stock'))

    categories = StockCategory.query.order_by(StockCategory.name).all()
    return render_template('manage_stock.html', categories=categories)

# --- Office Management ---

@main_bp.route('/offices/manage', methods=['GET', 'POST'])
def manage_offices():
    """Add/Delete Sub-Offices."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                existing = Office.query.filter(Office.name.ilike(name)).first() # Case-insensitive check
                if not existing:
                    try:
                        new_office = Office(name=name)
                        db.session.add(new_office)
                        db.session.commit()
                        flash(f'Office "{name}" added successfully.', 'success')
                    except IntegrityError:
                        db.session.rollback()
                        flash(f'Office "{name}" already exists (database constraint).', 'warning')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error adding office: {e}', 'danger')
                        current_app.logger.error(f"Error adding office: {e}")
                else:
                    flash(f'Office "{name}" already exists.', 'warning')
            else:
                flash('Office name cannot be empty.', 'danger')
        elif action == 'delete':
            office_id = request.form.get('office_id')
            office = db.session.get(Office, office_id) # Use db.session.get
            if office:
                 # Basic check: prevent deletion if transactions or invoices exist
                if office.transactions or office.invoices:
                     flash(f'Cannot delete office "{office.name}" as it has associated transactions or invoices.', 'danger')
                else:
                    try:
                        db.session.delete(office)
                        db.session.commit()
                        flash(f'Office "{office.name}" deleted.', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error deleting office: {e}', 'danger')
                        current_app.logger.error(f"Error deleting office {office.name}: {e}")
            else:
                flash('Office not found.', 'danger')
        return redirect(url_for('main.manage_offices'))

    offices = Office.query.order_by(Office.name).all()
    return render_template('manage_offices.html', offices=offices)

# --- Stock Transactions ---

@main_bp.route('/stock/receive', methods=['GET', 'POST'])
def receive_stock():
    """Record stock received from parent office (increases head office stock)."""
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        quantity_str = request.form.get('quantity')
        transaction_date_str = request.form.get('transaction_date')

        category = db.session.get(StockCategory, category_id)
        quantity = None

        # Validate quantity
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                flash('Quantity must be a positive number.', 'danger')
                quantity = None # Reset quantity if invalid
        except (ValueError, TypeError):
            flash('Invalid quantity entered.', 'danger')

        if not category or quantity is None:
            # Redirect back to form if validation failed
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', categories=categories, selected_category=category_id, entered_quantity=quantity_str, entered_date=transaction_date_str)

        # Validate and parse date
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d') if transaction_date_str else datetime.utcnow().date()
            # Combine date with current time for consistency if needed, or store as Date
            transaction_datetime = datetime.combine(transaction_date, datetime.min.time()) # Store as datetime at start of day
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', categories=categories, selected_category=category_id, entered_quantity=quantity_str, entered_date=transaction_date_str)

        # --- Perform transaction ---
        try:
            # 1. Update stock level
            category.current_stock += quantity

            # 2. Record transaction
            transaction = StockTransaction(
                stock_category_id=category.id,
                quantity=quantity, # Positive for inflow
                transaction_type='IN',
                transaction_date=transaction_datetime
                # office_id is null for incoming from parent
            )
            db.session.add(transaction)
            db.session.commit()
            flash(f'Successfully received {quantity} of {category.name}. Current stock: {category.current_stock}', 'success')
            return redirect(url_for('main.stock_report')) # Redirect to report after successful receive

        except Exception as e:
            db.session.rollback()
            flash(f'Error receiving stock: {e}', 'danger')
            current_app.logger.error(f"Error receiving stock: {e}")
            # Redirect back to form with entered values on error
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', categories=categories, selected_category=category_id, entered_quantity=quantity_str, entered_date=transaction_date_str)


    # --- GET Request ---
    categories = StockCategory.query.order_by(StockCategory.name).all()
    return render_template('receive_stock.html', categories=categories)


@main_bp.route('/stock/supply', methods=['GET', 'POST'])
def supply_stock():
    """Supply stock to a sub-office (decreases head office stock) and generate invoice."""
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        office_id = request.form.get('office_id')
        quantity_str = request.form.get('quantity')
        transaction_date_str = request.form.get('transaction_date')

        category = db.session.get(StockCategory, category_id)
        office = db.session.get(Office, office_id)
        quantity = None

        # Validate quantity
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                flash('Quantity must be a positive number.', 'danger')
                quantity = None
        except (ValueError, TypeError):
            flash('Invalid quantity entered.', 'danger')

        # Validate category, office, and quantity presence
        if not category or not office or quantity is None:
            flash('Missing or invalid category, office, or quantity.', 'danger')
             # Redirect back to form preserving selections
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', categories=categories, offices=offices,
                                   selected_category=category_id, selected_office=office_id,
                                   entered_quantity=quantity_str, entered_date=transaction_date_str)

        # Validate stock level
        if category.current_stock < quantity:
            flash(f'Insufficient stock for {category.name}. Available: {category.current_stock}', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', categories=categories, offices=offices,
                                   selected_category=category_id, selected_office=office_id,
                                   entered_quantity=quantity_str, entered_date=transaction_date_str)

        # Validate and parse date
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d') if transaction_date_str else datetime.utcnow().date()
            transaction_datetime = datetime.combine(transaction_date, datetime.min.time()) # Store as datetime
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', categories=categories, offices=offices,
                                   selected_category=category_id, selected_office=office_id,
                                   entered_quantity=quantity_str, entered_date=transaction_date_str)

        # Determine financial year and generate invoice number
        fy = get_financial_year(transaction_datetime) # Use the transaction datetime
        inv_num = generate_next_invoice_number(office.id, category.id, fy)

        # --- Perform operations in a transaction ---
        try:
            # 1. Decrease stock
            category.current_stock -= quantity

            # 2. Create Invoice
            new_invoice = Invoice(
                invoice_number=inv_num,
                financial_year=fy,
                date=transaction_datetime, # Use consistent datetime
                created_at=datetime.utcnow(),  # Explicitly set creation timestamp
                office_id=office.id,
                stock_category_id=category.id,
                quantity=quantity
            )
            db.session.add(new_invoice)
            # Flush to get the new_invoice.id needed for the transaction
            db.session.flush()

            # 3. Record Stock Transaction (Outflow)
            transaction = StockTransaction(
                stock_category_id=category.id,
                office_id=office.id,
                quantity=-quantity, # Negative for outflow
                transaction_type='OUT',
                transaction_date=transaction_datetime, # Use consistent datetime
                invoice_id=new_invoice.id # Link transaction to the invoice
            )
            db.session.add(transaction)

            # 4. Commit all changes
            db.session.commit()
            flash(f'Successfully supplied {quantity} of {category.name} to {office.name}. Invoice {inv_num} ({fy}) generated.', 'success')
            # Redirect to view the generated invoice PDF in a new tab ideally, or directly
            # For simplicity, redirecting to the invoice list first
            return redirect(url_for('main.list_invoices'))
            # Alternative: Redirect directly to PDF (might be less user-friendly if they want to do more)
            # return redirect(url_for('main.view_invoice_pdf', invoice_id=new_invoice.id))

        except Exception as e:
            db.session.rollback() # Rollback ALL changes in case of any error
            flash(f'Error supplying stock: {e}', 'danger')
            current_app.logger.error(f"Error supplying stock: {e}")
            # Redirect back to form with entered values on error
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', categories=categories, offices=offices,
                                   selected_category=category_id, selected_office=office_id,
                                   entered_quantity=quantity_str, entered_date=transaction_date_str)


    # --- GET Request ---
    categories = StockCategory.query.order_by(StockCategory.name).all()
    offices = Office.query.order_by(Office.name).all()
    return render_template('supply_stock.html', categories=categories, offices=offices)

# --- Reports and Invoice Viewing ---

@main_bp.route('/stock/report')
def stock_report():
    """Display current stock levels for all categories at the head office."""
    categories = StockCategory.query.order_by(StockCategory.name).all()
    # Optional: Query recent transactions for display
    recent_transactions = StockTransaction.query.order_by(StockTransaction.transaction_date.desc()).limit(10).all()
    return render_template('stock_report.html', categories=categories, transactions=recent_transactions)

@main_bp.route('/invoice/<int:invoice_id>/pdf')
def view_invoice_pdf(invoice_id):
    """Generate and return the PDF for a specific invoice."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        abort(404, description="Invoice not found")
    pdf_response = generate_invoice_pdf(invoice)
    return pdf_response

@main_bp.route('/invoices')
def list_invoices():
    """List recent invoices with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = 15 # Number of invoices per page
    # Query invoices and order by creation timestamp descending
    invoices_pagination = Invoice.query.order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template('list_invoices.html', invoices_pagination=invoices_pagination)

@main_bp.route('/daily-supply-report')
def daily_supply_report():
    """Show supplies made on a particular day."""
    selected_date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    try:
        # Parse the selected date
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        
        # Query invoices for the selected date
        invoices = Invoice.query.filter(
            func.date(Invoice.created_at) == date_obj.date()
        ).order_by(Invoice.created_at.desc()).all()
        
        # Calculate summary by category
        summary = []
        if invoices:
            # Create a dictionary to store totals by category
            category_totals = {}
            for invoice in invoices:
                if invoice.stock_category not in category_totals:
                    category_totals[invoice.stock_category] = 0
                category_totals[invoice.stock_category] += invoice.quantity
            
            # Convert to list for template
            summary = [{'name': cat.name, 'total_quantity': total} 
                      for cat, total in category_totals.items()]
            # Sort by category name
            summary.sort(key=lambda x: x['name'])
        
        return render_template('daily_supply_report.html', 
                             selected_date=selected_date,
                             invoices=invoices,
                             summary=summary)
                             
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
        return redirect(url_for('main.daily_supply_report'))