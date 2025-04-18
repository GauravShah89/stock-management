from . import db
from datetime import datetime
from sqlalchemy import UniqueConstraint

class Office(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # Relationships: Links to invoices and transactions for this office
    invoices = db.relationship('Invoice', backref='office', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('StockTransaction', backref='office', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Office {self.name}>'

class StockCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    current_stock = db.Column(db.Integer, default=0, nullable=False) # Stock level at the head office
    # Relationships: Links to transactions and invoices for this stock category
    transactions = db.relationship('StockTransaction', backref='stock_category', lazy=True, cascade="all, delete-orphan")
    invoices = db.relationship('Invoice', backref='stock_category', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<StockCategory {self.name}>'

class StockTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_category_id = db.Column(db.Integer, db.ForeignKey('stock_category.id'), nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey('office.id'), nullable=True) # Null if received from parent, non-null if supplied to sub-office
    quantity = db.Column(db.Integer, nullable=False) # Positive for inflow, negative for outflow
    transaction_type = db.Column(db.String(10), nullable=False) # 'IN' or 'OUT'
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True) # Link to invoice if it's an outflow ('OUT')

    def __repr__(self):
        direction = "to" if self.transaction_type == 'OUT' else "from"
        office_name = self.office.name if self.office else "Parent Office"
        return f'<StockTransaction {abs(self.quantity)} {self.stock_category.name} {self.transaction_type} {direction} {office_name} on {self.transaction_date.strftime("%Y-%m-%d")}>'

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False) # Generated unique number per office/category/FY
    financial_year = db.Column(db.String(10), nullable=False) # e.g., FY2025-2026
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # When the record was created
    office_id = db.Column(db.Integer, db.ForeignKey('office.id'), nullable=False)
    stock_category_id = db.Column(db.Integer, db.ForeignKey('stock_category.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False) # The quantity dispatched in this invoice
    # Relationship: Links back to the specific stock transaction that generated this invoice
    transaction = db.relationship('StockTransaction', backref='invoice', uselist=False, lazy=True)

    # Constraint: Ensure invoice number is unique per office, category, and financial year
    __table_args__ = (UniqueConstraint('office_id', 'stock_category_id', 'financial_year', 'invoice_number', name='uq_invoice_number_office_category_fy'),)

    def __repr__(self):
        return f'<Invoice {self.invoice_number} ({self.financial_year}) for {self.office.name}>'