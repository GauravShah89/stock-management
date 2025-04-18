# Stock Management System

A Flask-based web application for managing stock distribution from head office to sub-offices, with invoice generation capabilities.

## Features

- Stock Category Management
- Sub-Office Management
- Stock Operations:
  - Receive stock at head office
  - Supply stock to sub-offices
  - Automatic invoice generation
- Reports:
  - Current stock levels
  - Daily supply report
  - Transaction history
- PDF Invoice Generation

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python run.py
```

The application will be available at `http://127.0.0.1:5000/`

## Usage

1. First, add stock categories through the "Manage > Stock Categories" menu
2. Add sub-offices through the "Manage > Sub-Offices" menu
3. Use "Stock Actions > Receive Stock" to add initial stock quantities
4. Use "Stock Actions > Supply Stock" to distribute stock and generate invoices
5. View reports and manage invoices through the navigation menu

## Database

The application uses SQLite and stores the database in the `instance` folder. The database is automatically created when you first run the application.

## Development

- Built with Flask and SQLAlchemy
- Uses Bootstrap 5 for the frontend
- PDF generation using xhtml2pdf