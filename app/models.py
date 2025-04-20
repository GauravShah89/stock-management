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
    office_id = db.Column(db.Integer, db.ForeignKey('office.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    reference_invoice = db.Column(db.String(100), nullable=True)  # For received stock invoice reference
    serial_numbers = db.Column(db.String(500), nullable=True)  # For serial numbers
    notes = db.Column(db.String(200), nullable=True)  # For any additional notes

    def __repr__(self):
        direction = "to" if self.transaction_type == 'OUT' else "from"
        office_name = self.office.name if self.office else "Parent Office"
        return f'<StockTransaction {abs(self.quantity)} {self.stock_category.name} {self.transaction_type} {direction} {office_name} on {self.transaction_date.strftime("%Y-%m-%d")}>'

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    financial_year = db.Column(db.String(10), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey('office.id'), nullable=False)
    stock_category_id = db.Column(db.Integer, db.ForeignKey('stock_category.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    serial_numbers = db.Column(db.String(500), nullable=True)  # For storing serial numbers
    acknowledgment_status = db.Column(db.String(20), default='PENDING', nullable=False)  # PENDING, ACKNOWLEDGED
    acknowledgment_date = db.Column(db.DateTime, nullable=True)  # When acknowledgment was received
    acknowledgment_note = db.Column(db.String(200), nullable=True)  # Any notes during acknowledgment
    transaction = db.relationship('StockTransaction', backref='invoice', uselist=False, lazy=True)

    __table_args__ = (UniqueConstraint('office_id', 'stock_category_id', 'financial_year', 'invoice_number', name='uq_invoice_number_office_category_fy'),)

    def __repr__(self):
        return f'<Invoice {self.invoice_number} ({self.financial_year}) for {self.office.name}>'