from datetime import datetime
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_connection, release_connection, get_cursor

auth_bp = Blueprint('auth', __name__)

VALID_ROLES = ('Admin', 'Cashier')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _user_to_dict(row: dict) -> dict:
    """Return a safe user dict — password_hash is never exposed."""
    d = dict(row)
    d.pop('password_hash', None)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _get_user_role(cur, user_id) -> str | None:
    """Return the role name assigned to a user, or None."""
    cur.execute(
        """
        SELECT r.name
          FROM roles r
          JOIN user_roles ur ON ur.role_id = r.id
         WHERE ur.user_id = %s
         LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    return row['name'] if row else None


def _assign_role(cur, user_id, role_name: str) -> None:
    """Replace a user's current role with the given role."""
    cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
    role = cur.fetchone()
    if role is None:
        raise ValueError(f"Role '{role_name}' does not exist. Valid roles: {VALID_ROLES}")
    cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cur.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
        (user_id, role['id']),
    )


# ---------------------------------------------------------------------------
# POST /api/register
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    username  = data.get('username', '').strip()
    password  = data.get('password', '').strip()
    full_name = data.get('full_name', '').strip()
    role      = data.get('role', '').strip()

    if not username or not password or not full_name:
        return jsonify({'error': 'username, password, and full_name are required'}), 400

    if not role or role not in VALID_ROLES:
        return jsonify({'error': f'role is required and must be one of {VALID_ROLES}'}), 400

    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({'error': 'Username already exists'}), 409

        cur.execute(
            """
            INSERT INTO users (username, password_hash, full_name)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (username, generate_password_hash(password), full_name),
        )
        user_row = cur.fetchone()
        _assign_role(cur, user_row['id'], role)
        conn.commit()

        user = _user_to_dict(user_row)
        user['role'] = role
        return jsonify({'message': 'User created successfully', 'user': user}), 201
    except ValueError as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# POST /api/login
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Invalid username or password'}), 401

        if not user['active']:
            return jsonify({'error': 'Account is disabled'}), 403

        user_data = _user_to_dict(user)
        user_data['role'] = _get_user_role(cur, user['id'])
        return jsonify({'message': 'Login successful', 'user': user_data}), 200
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# PUT /api/users/<id>
# ---------------------------------------------------------------------------

@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json() or {}

    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if cur.fetchone() is None:
            return jsonify({'error': 'User not found'}), 404

        fields, values = [], []

        if data.get('full_name', '').strip():
            fields.append("full_name = %s")
            values.append(data['full_name'].strip())

        if data.get('username', '').strip():
            fields.append("username = %s")
            values.append(data['username'].strip())

        if data.get('password', '').strip():
            fields.append("password_hash = %s")
            values.append(generate_password_hash(data['password'].strip()))

        if 'active' in data:
            fields.append("active = %s")
            values.append(bool(data['active']))

        if fields:
            fields.append("updated_at = NOW()")
            values.append(user_id)
            cur.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s RETURNING *",
                values,
            )
            user_row = cur.fetchone()
        else:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_row = cur.fetchone()

        new_role = data.get('role', '').strip()
        if new_role:
            if new_role not in VALID_ROLES:
                return jsonify({'error': f'role must be one of {VALID_ROLES}'}), 400
            _assign_role(cur, user_id, new_role)

        if not fields and not new_role:
            return jsonify({'error': 'No valid fields provided to update'}), 400

        conn.commit()

        user = _user_to_dict(user_row)
        user['role'] = _get_user_role(cur, user_id)
        return jsonify({'message': 'User updated successfully', 'user': user}), 200
    except ValueError as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()
        release_connection(conn)
