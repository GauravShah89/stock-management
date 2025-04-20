from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
)
from .models import db, StockCategory, Office, StockTransaction, Invoice
from .utils import get_financial_year, generate_next_invoice_number, generate_invoice_pdf
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, case

main_bp = Blueprint('main', __name__)

@main_bp.app_context_processor
def utility_processor():
    """Add utility functions and models to template context."""
    return {
        'now': datetime.utcnow,
        'Invoice': Invoice  # Make Invoice model available in templates
    }

@main_bp.route('/')
def index():
    """Home page."""
    return render_template('index.html')

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

@main_bp.route('/stock/categories/modify/<int:category_id>', methods=['POST'])
def modify_category(category_id):
    """Modify an existing stock category."""
    category = db.session.get(StockCategory, category_id)
    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('main.manage_stock'))

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Category name cannot be empty.', 'danger')
        return redirect(url_for('main.manage_stock'))

    # Check if the new name already exists (excluding current category)
    existing = StockCategory.query.filter(StockCategory.name.ilike(new_name), StockCategory.id != category_id).first()
    if existing:
        flash(f'A category with the name "{new_name}" already exists.', 'warning')
        return redirect(url_for('main.manage_stock'))

    try:
        category.name = new_name
        db.session.commit()
        flash(f'Category name updated successfully to "{new_name}".', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f'A category with the name "{new_name}" already exists (database constraint).', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating category name: {e}', 'danger')
        current_app.logger.error(f"Error updating category {category.id}: {e}")

    return redirect(url_for('main.manage_stock'))

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

@main_bp.route('/offices/modify/<int:office_id>', methods=['POST'])
def modify_office(office_id):
    """Modify an existing office."""
    office = db.session.get(Office, office_id)
    if not office:
        flash('Office not found.', 'danger')
        return redirect(url_for('main.manage_offices'))

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Office name cannot be empty.', 'danger')
        return redirect(url_for('main.manage_offices'))

    # Check if the new name already exists (excluding current office)
    existing = Office.query.filter(Office.name.ilike(new_name), Office.id != office_id).first()
    if existing:
        flash(f'An office with the name "{new_name}" already exists.', 'warning')
        return redirect(url_for('main.manage_offices'))

    try:
        office.name = new_name
        db.session.commit()
        flash(f'Office name updated successfully to "{new_name}".', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f'An office with the name "{new_name}" already exists (database constraint).', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating office name: {e}', 'danger')
        current_app.logger.error(f"Error updating office {office.id}: {e}")

    return redirect(url_for('main.manage_offices'))

# --- Stock Transactions ---

@main_bp.route('/stock/receive', methods=['GET', 'POST'])
def receive_stock():
    """Record stock received from parent office (increases head office stock)."""
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        quantity_str = request.form.get('quantity')
        transaction_date_str = request.form.get('transaction_date')
        reference_invoice = request.form.get('reference_invoice')
        serial_numbers = request.form.get('serial_numbers')
        notes = request.form.get('notes')

        category = db.session.get(StockCategory, category_id)
        quantity = None

        # Validate quantity
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                flash('Quantity must be a positive number.', 'danger')
                quantity = None
        except (ValueError, TypeError):
            flash('Invalid quantity entered.', 'danger')

        if not category or quantity is None:
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', 
                                categories=categories, 
                                selected_category=category_id, 
                                entered_quantity=quantity_str,
                                entered_date=transaction_date_str,
                                reference_invoice=reference_invoice,
                                serial_numbers=serial_numbers,
                                notes=notes)

        # Validate and parse date
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d') if transaction_date_str else datetime.utcnow().date()
            transaction_datetime = datetime.combine(transaction_date, datetime.min.time())
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', 
                                categories=categories, 
                                selected_category=category_id,
                                entered_quantity=quantity_str,
                                entered_date=transaction_date_str,
                                reference_invoice=reference_invoice,
                                serial_numbers=serial_numbers,
                                notes=notes)

        try:
            # Update stock level
            category.current_stock += quantity

            # Record transaction with new fields
            transaction = StockTransaction(
                stock_category_id=category.id,
                quantity=quantity,
                transaction_type='IN',
                transaction_date=transaction_datetime,
                reference_invoice=reference_invoice,
                serial_numbers=serial_numbers,
                notes=notes
            )
            db.session.add(transaction)
            db.session.commit()
            flash(f'Successfully received {quantity} of {category.name}. Current stock: {category.current_stock}', 'success')
            return redirect(url_for('main.stock_report'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error receiving stock: {e}', 'danger')
            current_app.logger.error(f"Error receiving stock: {e}")
            categories = StockCategory.query.order_by(StockCategory.name).all()
            return render_template('receive_stock.html', 
                                categories=categories,
                                selected_category=category_id,
                                entered_quantity=quantity_str,
                                entered_date=transaction_date_str,
                                reference_invoice=reference_invoice,
                                serial_numbers=serial_numbers,
                                notes=notes)

    # GET Request
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
        serial_numbers = request.form.get('serial_numbers')

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
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', 
                                categories=categories, 
                                offices=offices,
                                selected_category=category_id, 
                                selected_office=office_id,
                                entered_quantity=quantity_str, 
                                entered_date=transaction_date_str,
                                serial_numbers=serial_numbers)

        # Validate stock level
        if category.current_stock < quantity:
            flash(f'Insufficient stock for {category.name}. Available: {category.current_stock}', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', 
                                categories=categories, 
                                offices=offices,
                                selected_category=category_id, 
                                selected_office=office_id,
                                entered_quantity=quantity_str, 
                                entered_date=transaction_date_str,
                                serial_numbers=serial_numbers)

        # Validate and parse date
        try:
            transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d') if transaction_date_str else datetime.utcnow().date()
            transaction_datetime = datetime.combine(transaction_date, datetime.min.time())
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', 
                                categories=categories, 
                                offices=offices,
                                selected_category=category_id, 
                                selected_office=office_id,
                                entered_quantity=quantity_str, 
                                entered_date=transaction_date_str,
                                serial_numbers=serial_numbers)

        # Determine financial year and generate invoice number
        fy = get_financial_year(transaction_datetime)
        inv_num = generate_next_invoice_number(office.id, category.id, fy)

        try:
            # 1. Decrease stock
            category.current_stock -= quantity

            # 2. Create Invoice with serial numbers and initial acknowledgment status
            new_invoice = Invoice(
                invoice_number=inv_num,
                financial_year=fy,
                date=transaction_datetime,
                created_at=datetime.utcnow(),
                office_id=office.id,
                stock_category_id=category.id,
                quantity=quantity,
                serial_numbers=serial_numbers,
                acknowledgment_status='PENDING'
            )
            db.session.add(new_invoice)
            db.session.flush()

            # 3. Record Stock Transaction with serial numbers
            transaction = StockTransaction(
                stock_category_id=category.id,
                office_id=office.id,
                quantity=-quantity,
                transaction_type='OUT',
                transaction_date=transaction_datetime,
                invoice_id=new_invoice.id,
                serial_numbers=serial_numbers
            )
            db.session.add(transaction)
            db.session.commit()

            flash(f'Successfully supplied {quantity} of {category.name} to {office.name}. Invoice {inv_num} ({fy}) generated.', 'success')
            return redirect(url_for('main.list_invoices'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error supplying stock: {e}', 'danger')
            current_app.logger.error(f"Error supplying stock: {e}")
            categories = StockCategory.query.order_by(StockCategory.name).all()
            offices = Office.query.order_by(Office.name).all()
            return render_template('supply_stock.html', 
                                categories=categories, 
                                offices=offices,
                                selected_category=category_id, 
                                selected_office=office_id,
                                entered_quantity=quantity_str, 
                                entered_date=transaction_date_str,
                                serial_numbers=serial_numbers)

    # GET Request
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
    """List invoices with filtering and sorting options."""
    page = request.args.get('page', 1, type=int)
    per_page = 15

    # Get filter parameters
    from_date = request.args.get('from_date', (datetime.utcnow().replace(day=1)).strftime('%Y-%m-%d'))
    to_date = request.args.get('to_date', datetime.utcnow().strftime('%Y-%m-%d'))
    category_id = request.args.get('category_id', type=int)
    office_id = request.args.get('office_id', type=int)
    acknowledgment_status = request.args.get('acknowledgment_status')
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    # Base query
    query = Invoice.query

    # Apply filters
    try:
        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
        to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
        query = query.filter(Invoice.date.between(
            from_date_obj, to_date_obj + timedelta(days=1)
        ))
    except ValueError:
        flash('Invalid date format. Using default date range.', 'warning')

    if category_id:
        query = query.filter_by(stock_category_id=category_id)
    if office_id:
        query = query.filter_by(office_id=office_id)
    if acknowledgment_status:
        query = query.filter_by(acknowledgment_status=acknowledgment_status)

    # Apply sorting
    if sort_by == 'created_at':
        order_col = Invoice.created_at
    elif sort_by == 'invoice_number':
        order_col = Invoice.invoice_number
    elif sort_by == 'quantity':
        order_col = Invoice.quantity
    elif sort_by == 'office':
        order_col = Office.name
        query = query.join(Office)
    elif sort_by == 'category':
        order_col = StockCategory.name
        query = query.join(StockCategory)
    else:
        order_col = Invoice.created_at

    if sort_order == 'asc':
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    # Execute query with pagination
    invoices_pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get categories and offices for filters
    categories = StockCategory.query.order_by(StockCategory.name).all()
    offices = Office.query.order_by(Office.name).all()

    return render_template('list_invoices.html',
                         invoices_pagination=invoices_pagination,
                         categories=categories,
                         offices=offices,
                         from_date=from_date,
                         to_date=to_date,
                         selected_category=category_id,
                         selected_office=office_id,
                         selected_status=acknowledgment_status,
                         sort_by=sort_by,
                         sort_order=sort_order)

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

@main_bp.route('/acknowledgments')
def pending_acknowledgments():
    """Display invoices with their acknowledgment status."""
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    return render_template('pending_acknowledgments.html', invoices=invoices)

@main_bp.route('/acknowledge-invoice/<int:invoice_id>', methods=['POST'])
def acknowledge_invoice(invoice_id):
    """Mark an invoice as acknowledged."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('main.pending_acknowledgments'))

    note = request.form.get('acknowledgment_note', '')
    invoice.acknowledgment_status = 'ACKNOWLEDGED'
    invoice.acknowledgment_date = datetime.utcnow()
    invoice.acknowledgment_note = note

    try:
        db.session.commit()
        flash(f'Invoice #{invoice.invoice_number} has been acknowledged successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error acknowledging invoice: {str(e)}', 'danger')

    return redirect(url_for('main.pending_acknowledgments'))

@main_bp.route('/modify-acknowledgment/<int:invoice_id>', methods=['POST'])
def modify_acknowledgment(invoice_id):
    """Update the acknowledgment status and note for an invoice."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('main.pending_acknowledgments'))

    new_status = request.form.get('acknowledgment_status')
    new_note = request.form.get('acknowledgment_note', '')

    if new_status not in ['PENDING', 'ACKNOWLEDGED']:
        flash('Invalid acknowledgment status.', 'danger')
        return redirect(url_for('main.pending_acknowledgments'))

    try:
        invoice.acknowledgment_status = new_status
        invoice.acknowledgment_note = new_note
        
        # Update acknowledgment date only when changing to ACKNOWLEDGED
        if new_status == 'ACKNOWLEDGED':
            invoice.acknowledgment_date = datetime.utcnow()
        elif new_status == 'PENDING':
            invoice.acknowledgment_date = None

        db.session.commit()
        flash(f'Invoice #{invoice.invoice_number} acknowledgment status has been updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating acknowledgment: {str(e)}', 'danger')

    return redirect(url_for('main.pending_acknowledgments'))

@main_bp.route('/reports/transactions', methods=['GET'])
def transaction_report():
    """Comprehensive transaction report with filters and sorting."""
    # Get filter parameters
    from_date = request.args.get('from_date', (datetime.utcnow().replace(day=1)).strftime('%Y-%m-%d'))
    to_date = request.args.get('to_date', datetime.utcnow().strftime('%Y-%m-%d'))
    category_id = request.args.get('category_id', type=int)
    office_id = request.args.get('office_id', type=int)
    transaction_type = request.args.get('transaction_type')
    sort_by = request.args.get('sort_by', 'transaction_date')
    sort_order = request.args.get('sort_order', 'desc')

    # Base query
    query = StockTransaction.query

    # Apply filters
    try:
        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
        to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
        query = query.filter(StockTransaction.transaction_date.between(
            from_date_obj, to_date_obj + timedelta(days=1)
        ))
    except ValueError:
        flash('Invalid date format. Using default date range.', 'warning')

    if category_id:
        query = query.filter_by(stock_category_id=category_id)
    if office_id:
        query = query.filter_by(office_id=office_id)
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)

    # Apply sorting
    if sort_by == 'transaction_date':
        order_col = StockTransaction.transaction_date
    elif sort_by == 'quantity':
        order_col = StockTransaction.quantity
    elif sort_by == 'category':
        order_col = StockCategory.name
    elif sort_by == 'office':
        order_col = Office.name
    else:
        order_col = StockTransaction.transaction_date

    if sort_order == 'asc':
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    # Add joins for sorting if needed
    if sort_by == 'category':
        query = query.join(StockCategory)
    elif sort_by == 'office':
        query = query.join(Office)

    # Execute query with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    transactions = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get categories and offices for filters
    categories = StockCategory.query.order_by(StockCategory.name).all()
    offices = Office.query.order_by(Office.name).all()

    return render_template('transaction_report.html',
                         transactions=transactions,
                         categories=categories,
                         offices=offices,
                         from_date=from_date,
                         to_date=to_date,
                         selected_category=category_id,
                         selected_office=office_id,
                         selected_type=transaction_type,
                         sort_by=sort_by,
                         sort_order=sort_order)

@main_bp.route('/reports/stock-movement')
def stock_movement_report():
    """Report showing stock movement trends over time."""
    # Get filter parameters
    from_date = request.args.get('from_date', (datetime.utcnow().replace(day=1)).strftime('%Y-%m-%d'))
    to_date = request.args.get('to_date', datetime.utcnow().strftime('%Y-%m-%d'))
    category_id = request.args.get('category_id', type=int)

    try:
        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
        to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Using default date range.', 'warning')
        from_date_obj = datetime.utcnow().replace(day=1)
        to_date_obj = datetime.utcnow()

    # Base query for movements
    movements = db.session.query(
        StockCategory.name.label('category_name'),
        func.sum(case((StockTransaction.transaction_type == 'IN', StockTransaction.quantity), else_=0)).label('total_in'),
        func.sum(case((StockTransaction.transaction_type == 'OUT', -StockTransaction.quantity), else_=0)).label('total_out'),
        Office.name.label('office_name'),
        func.date(StockTransaction.transaction_date).label('date')
    ).join(
        StockCategory,
        StockTransaction.stock_category_id == StockCategory.id
    ).outerjoin(
        Office,
        StockTransaction.office_id == Office.id
    ).filter(
        StockTransaction.transaction_date.between(from_date_obj, to_date_obj + timedelta(days=1))
    )

    if category_id:
        movements = movements.filter(StockTransaction.stock_category_id == category_id)

    movements = movements.group_by(
        'category_name',
        'office_name',
        'date'
    ).order_by(
        'date',
        'category_name'
    ).all()

    # Get categories for filter
    categories = StockCategory.query.order_by(StockCategory.name).all()

    return render_template('stock_movement_report.html',
                         movements=movements,
                         categories=categories,
                         from_date=from_date,
                         to_date=to_date,
                         selected_category=category_id)