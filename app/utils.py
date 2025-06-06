from datetime import datetime
from .models import Invoice, db
from io import BytesIO
from xhtml2pdf import pisa
from flask import render_template_string, make_response, current_app, render_template

def get_financial_year(date=None):
    """Determines the financial year (April 1 - March 31) for a given date."""
    if date is None:
        date = datetime.utcnow()
    year = date.year
    if date.month < 4: # Before April 1st (e.g., Jan, Feb, Mar 2025 are in FY2024-2025)
        return f"FY{year-1}-{year}"
    else: # On or after April 1st (e.g., Apr 2025 is in FY2025-2026)
        return f"FY{year}-{year+1}"

def generate_next_invoice_number(office_id, stock_category_id, financial_year):
    """
    Generates the next sequential invoice number for a given office,
    stock category, and financial year. Starts from 1 each financial year.
    """
    # Find the numerically highest invoice number for this combination in the current FY
    last_invoice = Invoice.query.filter_by(
        office_id=office_id,
        stock_category_id=stock_category_id,
        financial_year=financial_year
    ).order_by(db.cast(Invoice.invoice_number, db.Integer).desc()).first()

    if last_invoice:
        try:
            next_num = int(last_invoice.invoice_number) + 1
        except ValueError:
             # Fallback if somehow the last invoice number wasn't an integer
             current_app.logger.warning(f"Non-integer invoice number found: {last_invoice.invoice_number} for FY {financial_year}. Restarting count.")
             next_num = 1 # Or handle error differently
    else:
        # No previous invoice for this combo in this FY, start at 1
        next_num = 1

    return str(next_num) # Return as string

def render_pdf(template_src, context_dict={}):
    """Renders an HTML template to a PDF file response."""
    # Try loading from file first, fallback to string if needed
    try:
        html = render_template(template_src, **context_dict)
    except Exception:
         # Fallback to the hardcoded template string if file loading fails or not used
         html = render_template_string(INVOICE_TEMPLATE_HTML, **context_dict)

    result = BytesIO()
    # Ensure encoding is UTF-8 for special characters
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, encoding='UTF-8')

    if not pdf.err:
        response = make_response(result.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        # Get invoice number safely - context_dict contains the actual Invoice object
        invoice = context_dict.get('invoice')
        invoice_number = invoice.invoice_number if invoice else 'details'
        response.headers['Content-Disposition'] = f'inline; filename=invoice_{invoice_number}.pdf'
        return response
    else:
        current_app.logger.error(f"Error generating PDF: {pdf.err}")
        return "Error generating PDF", 500

# Basic Invoice HTML Template
INVOICE_TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ invoice.invoice_number }}</title>
    <style>
        @page { size: A4; margin: 1cm; }
        body { font-family: sans-serif; font-size: 10pt; }
        .header { text-align: center; margin-bottom: 20px; border-bottom: 1px solid #000; padding-bottom: 10px; }
        .header h1 { margin: 0; font-size: 18pt; }
        .details { margin-bottom: 20px; }
        .details p { margin: 3px 0; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th, td { border: 1px solid #333; padding: 6px; text-align: left; }
        th { background-color: #eee; font-weight: bold; }
        .footer { text-align: center; margin-top: 40px; font-size: 8pt; color: #555; position: fixed; bottom: 0; width: 100%; }
        .signature { margin-top: 50px; padding-top: 10px; }
        .signature p { margin-bottom: 30px; }
        .serial-numbers { margin-top: 10px; font-size: 9pt; padding: 5px; border: 1px dashed #999; }
    </style>
</head>
<body>
    <div class="header">
        <h1>INVOICE</h1>
        <p>Invoice No: {{ invoice.invoice_number }}</p>
        <p>Date: {{ invoice.date.strftime('%d-%b-%Y') }}</p>
        <p>Financial Year: {{ invoice.financial_year }}</p>
    </div>

    <div class="details">
        <p><strong>To (Sub-Office):</strong> {{ invoice.office.name }}</p>
    </div>

    <table>
        <thead>
            <tr>
                <th>Stock Category</th>
                <th>Quantity Dispatched</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{{ invoice.stock_category.name }}</td>
                <td>{{ invoice.quantity }}</td>
            </tr>
        </tbody>
    </table>

    {% if invoice.serial_numbers %}
    <div class="serial-numbers">
        <strong>Serial Numbers:</strong><br>
        {{ invoice.serial_numbers }}
    </div>
    {% endif %}

    <div class="signature">
        <p><strong>Received By:</strong> _______________________</p>
        <p><strong>Designation:</strong> _______________________</p>
        <p><strong>Date:</strong> _______________________</p>
    </div>

    <div class="footer">
        Generated by Stock Management System
        <br>
        {{ invoice.created_at.strftime('%Y-%m-%d %H:%M:%S') }}
    </div>
</body>
</html>
"""

def generate_invoice_pdf(invoice):
    """Generates a PDF response for a given invoice object."""
    context = {'invoice': invoice}
    # Use the HTML template file if it exists, otherwise the string above
    return render_pdf('invoice_template.html', context)