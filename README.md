# Crown Tea Hub Billing Backend

A Flask-based billing backend API with PostgreSQL database integration.

## Features

- Customer management (CRUD operations)
- Invoice generation and management
- Invoice items with automatic calculations
- Payment processing and tracking
- PostgreSQL database with SQLAlchemy ORM
- Database migrations with Flask-Migrate
- CORS enabled for cross-origin requests

## Prerequisites

- Python 3.8+
- PostgreSQL database (Neon database configured)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
The `.env` file is already configured with your PostgreSQL connection string.

3. Initialize database migrations:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

## Running the Application

### Development Mode
```bash
python run.py
```

Or using Flask:
```bash
flask run
```

The API will be available at `http://localhost:5000`

### Production Mode
Set the `FLASK_ENV` environment variable to `production` before running.

## API Endpoints

### Health Check
- `GET /health` - Check API status

### Customers
- `GET /api/billing/customers` - Get all customers
- `GET /api/billing/customers/<id>` - Get specific customer
- `POST /api/billing/customers` - Create new customer
- `PUT /api/billing/customers/<id>` - Update customer
- `DELETE /api/billing/customers/<id>` - Delete customer
- `GET /api/billing/customers/<id>/invoices` - Get customer's invoices

### Invoices
- `GET /api/billing/invoices` - Get all invoices
- `GET /api/billing/invoices/<id>` - Get specific invoice with items and payments
- `POST /api/billing/invoices` - Create new invoice
- `PUT /api/billing/invoices/<id>` - Update invoice
- `DELETE /api/billing/invoices/<id>` - Delete invoice

### Payments
- `GET /api/billing/payments` - Get all payments
- `GET /api/billing/payments/<id>` - Get specific payment
- `POST /api/billing/payments` - Create new payment
- `PUT /api/billing/payments/<id>` - Update payment
- `DELETE /api/billing/payments/<id>` - Delete payment

## Database Models

### Customer
- id, name, email, phone, address, created_at, updated_at

### Invoice
- id, customer_id, invoice_number, issue_date, due_date, subtotal, tax_amount, total_amount, status, notes, created_at, updated_at

### InvoiceItem
- id, invoice_id, description, quantity, unit_price, line_total, created_at

### Payment
- id, invoice_id, payment_date, amount, payment_method, transaction_id, status, notes, created_at, updated_at

## Example API Usage

### Create a Customer
```bash
curl -X POST http://localhost:5000/api/billing/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "123-456-7890",
    "address": "123 Main St, City, State 12345"
  }'
```

### Create an Invoice
```bash
curl -X POST http://localhost:5000/api/billing/invoices \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "invoice_number": "INV-2024001",
    "issue_date": "2024-01-15",
    "due_date": "2024-02-15",
    "tax_amount": 10.00,
    "items": [
      {
        "description": "Product A",
        "quantity": 2,
        "unit_price": 25.00
      },
      {
        "description": "Product B",
        "quantity": 1,
        "unit_price": 50.00
      }
    ]
  }'
```

### Create a Payment
```bash
curl -X POST http://localhost:5000/api/billing/payments \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": 1,
    "amount": 110.00,
    "payment_method": "credit_card",
    "transaction_id": "TXN123456"
  }'
```

## Configuration

Environment variables can be set in the `.env` file:
- `DATABASE_URL` - PostgreSQL connection string
- `FLASK_ENV` - Environment (development/production)
- `SECRET_KEY` - Flask secret key

## Database Migrations

To create new migrations after model changes:
```bash
flask db migrate -m "Description of changes"
flask db upgrade
```

To rollback:
```bash
flask db downgrade
```
