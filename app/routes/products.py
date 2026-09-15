import os
from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify
from app.db import get_connection, release_connection, get_cursor
from app.db_init import ensure_db

products_bp = Blueprint('products', __name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _product_to_dict(row: dict) -> dict:
    """Return a safe product dict."""
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, float):
            d[k] = float(v)
    return d


# ---------------------------------------------------------------------------
# GET /api/products
# ---------------------------------------------------------------------------

@products_bp.get('/products')
def list_products():
    """List all products. Any logged-in user can access."""
    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM products ORDER BY name")
        products = []
        for row in cur.fetchall():
            products.append(_product_to_dict(row))
        return jsonify({'products': products, 'total': len(products)})
    finally:
        cur.close(); conn.close()


# ---------------------------------------------------------------------------
# POST /api/products
# ---------------------------------------------------------------------------

@products_bp.post('/products')
def create_product():
    """Create a new product. Any logged-in user can access."""
    body = request.get_json(silent=True) or {}

    item_id          = (body.get('item_id') or '').strip()
    product_category = (body.get('product_category') or '').strip()
    subcategory      = (body.get('subcategory') or '').strip()
    barcode          = (body.get('barcode') or '').strip()
    name             = (body.get('name') or '').strip()
    brand            = (body.get('brand') or '').strip()
    expiry_date      = body.get('expiry_date')
    price            = body.get('price', 0)
    track_stock      = body.get('track_stock', True)
    stock_quantity   = body.get('stock_quantity')
    unit             = (body.get('unit') or 'pcs').strip()
    description      = (body.get('description') or '').strip()

    if not name:
        return jsonify({'detail': 'Product name is required'}), 400
    if not product_category:
        return jsonify({'detail': 'Product category is required'}), 400
    if track_stock and (stock_quantity is None or stock_quantity == ""):
        return jsonify({'detail': 'Stock quantity is required when track_stock is enabled'}), 400

    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        # Check for duplicate item_id or barcode
        if item_id:
            cur.execute("SELECT id FROM products WHERE item_id = %s", (item_id,))
            if cur.fetchone():
                return jsonify({'detail': 'Item ID already exists'}), 409
        if barcode:
            cur.execute("SELECT id FROM products WHERE barcode = %s", (barcode,))
            if cur.fetchone():
                return jsonify({'detail': 'Barcode already exists'}), 409

        cur.execute(
            """
            INSERT INTO products (item_id, product_category, subcategory, barcode, name, brand, expiry_date, price, track_stock, stock_quantity, unit, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (item_id or None, product_category, subcategory or None, barcode or None, name, brand or None, expiry_date, price, track_stock, stock_quantity if track_stock else None, unit, description or None),
        )
        product_row = cur.fetchone()
        conn.commit()
        return jsonify({'message': 'Product created successfully', 'product': _product_to_dict(product_row)}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    finally:
        cur.close(); conn.close()


# ---------------------------------------------------------------------------
# PUT /api/products/<id>
# ---------------------------------------------------------------------------

@products_bp.put('/products/<int:product_id>')
def update_product(product_id: int):
    """Update a product. Any logged-in user can access."""
    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cur.fetchone():
            return jsonify({'detail': 'Product not found'}), 404

        body = request.get_json(silent=True) or {}
        fields, values = [], []

        item_id          = (body.get('item_id') or '').strip()
        product_category = (body.get('product_category') or '').strip()
        subcategory      = (body.get('subcategory') or '').strip()
        barcode          = (body.get('barcode') or '').strip()
        name             = (body.get('name') or '').strip()
        brand            = (body.get('brand') or '').strip()
        expiry_date      = body.get('expiry_date')
        price            = body.get('price')
        track_stock      = body.get('track_stock')
        stock_quantity   = body.get('stock_quantity')
        unit             = (body.get('unit') or '').strip()
        description      = (body.get('description') or '').strip()
        active           = body.get('active')

        if item_id:
            fields.append("item_id = %s"); values.append(item_id)
        if product_category:
            fields.append("product_category = %s"); values.append(product_category)
        if subcategory:
            fields.append("subcategory = %s"); values.append(subcategory)
        if barcode:
            fields.append("barcode = %s"); values.append(barcode)
        if name:
            fields.append("name = %s"); values.append(name)
        if brand:
            fields.append("brand = %s"); values.append(brand)
        if expiry_date is not None:
            fields.append("expiry_date = %s"); values.append(expiry_date)
        if price is not None:
            fields.append("price = %s"); values.append(price)
        if track_stock is not None:
            fields.append("track_stock = %s"); values.append(track_stock)
        if stock_quantity is not None:
            fields.append("stock_quantity = %s"); values.append(stock_quantity)
        if unit:
            fields.append("unit = %s"); values.append(unit)
        if description:
            fields.append("description = %s"); values.append(description)
        if active is not None:
            fields.append("active = %s"); values.append(active)

        if fields:
            fields.append("updated_at = NOW()")
            values.append(product_id)
            cur.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = %s RETURNING *", values)
            product_row = cur.fetchone()
            conn.commit()
            return jsonify({'message': 'Product updated successfully', 'product': _product_to_dict(product_row)})
        else:
            return jsonify({'detail': 'No valid fields provided to update'}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    finally:
        cur.close(); conn.close()


# ---------------------------------------------------------------------------
# DELETE /api/products/<id>
# ---------------------------------------------------------------------------

@products_bp.delete('/products/<int:product_id>')
def delete_product(product_id: int):
    """Delete a product. Any logged-in user can access."""
    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cur.fetchone():
            return jsonify({'detail': 'Product not found'}), 404

        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        return jsonify({'message': 'Product deleted successfully'})
    finally:
        cur.close(); conn.close()
