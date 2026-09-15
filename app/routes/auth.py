import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from flask import Blueprint, request, jsonify
from passlib.context import CryptContext
from werkzeug.security import check_password_hash as werkzeug_check

from app.db import get_connection, release_connection, get_cursor
from app.db_init import ensure_db

auth_bp = Blueprint('auth', __name__)

VALID_ROLES   = ('Admin', 'Cashier')
JWT_SECRET    = os.environ.get('SECRET_KEY', 'dev-secret-key')
JWT_ALGORITHM = 'HS256'
JWT_EXP_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def _verify_password(plain: str, hashed: str) -> bool:
    """Verify against bcrypt (new) or Werkzeug (legacy) hashes."""
    if hashed.startswith(('scrypt:', 'pbkdf2:', 'sha256$')):
        return werkzeug_check(hashed, plain)
    return pwd_context.verify(plain, hashed)


def _needs_rehash(hashed: str) -> bool:
    """Return True if the hash is a legacy Werkzeug hash."""
    return hashed.startswith(('scrypt:', 'pbkdf2:', 'sha256$'))


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        'sub': str(user_id),
        'username': username,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]), None
    except jwt.ExpiredSignatureError:
        return None, 'Token has expired'
    except jwt.InvalidTokenError:
        return None, 'Invalid token'


# ---------------------------------------------------------------------------
# Auth middleware helpers
# ---------------------------------------------------------------------------

def _get_current_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, (jsonify({'detail': 'Missing or invalid Authorization header'}), 401)
    token = auth.split(' ', 1)[1]
    payload, err = _decode_token(token)
    if err:
        return None, (jsonify({'detail': err}), 401)
    return payload, None


def _require_admin():
    payload, err_resp = _get_current_user()
    if err_resp:
        return None, err_resp
    if payload.get('role') != 'Admin':
        return None, (jsonify({'detail': 'Admin role required'}), 403)
    return payload, None


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

@auth_bp.post('/register')
def register():
    admin, err_resp = _require_admin()
    if err_resp:
        return err_resp

    body      = request.get_json(silent=True) or {}
    username  = (body.get('username') or '').strip()
    password  = (body.get('password') or '').strip()
    full_name = (body.get('full_name') or '').strip()
    role      = (body.get('role') or '').strip()

    if not username or not password or not full_name:
        return jsonify({'detail': 'username, password, and full_name are required'}), 400
    if not role or role not in VALID_ROLES:
        return jsonify({'detail': f'role is required and must be one of {VALID_ROLES}'}), 400

    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({'detail': 'Username already exists'}), 409

        cur.execute(
            """
            INSERT INTO users (username, password_hash, full_name)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (username, pwd_context.hash(password), full_name),
        )
        user_row = cur.fetchone()
        _assign_role(cur, user_row['id'], role)
        conn.commit()

        user = _user_to_dict(user_row)
        user['role'] = role
        return jsonify({'message': 'User created successfully', 'user': user}), 201
    except ValueError as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# POST /api/login
# ---------------------------------------------------------------------------

@auth_bp.post('/login')
def login():
    body     = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = (body.get('password') or '').strip()

    if not username or not password:
        return jsonify({'detail': 'username and password are required'}), 400

    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user is None or not _verify_password(password, user['password_hash']):
            return jsonify({'detail': 'Invalid username or password'}), 401

        if not user['active']:
            return jsonify({'detail': 'Account is disabled'}), 403

        # Migrate legacy Werkzeug hash → bcrypt on first successful login
        if _needs_rehash(user['password_hash']):
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (pwd_context.hash(password), user['id']),
            )
            conn.commit()

        role      = _get_user_role(cur, user['id'])
        token     = _create_token(user['id'], user['username'], role)
        user_data = _user_to_dict(user)
        user_data['role'] = role

        return jsonify({
            'message':    'Login successful',
            'token':      token,
            'token_type': 'bearer',
            'user':       user_data,
        })
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# GET /api/users
# ---------------------------------------------------------------------------

@auth_bp.get('/users')
def list_users():
    admin, err_resp = _require_admin()
    if err_resp:
        return err_resp

    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users ORDER BY id")
        users = []
        for row in cur.fetchall():
            u = _user_to_dict(row)
            u['role'] = _get_user_role(cur, row['id'])
            users.append(u)
        return jsonify({'users': users, 'total': len(users)})
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# PUT /api/users/<id>
# ---------------------------------------------------------------------------

@auth_bp.put('/users/<int:user_id>')
def update_user(user_id: int):
    admin, err_resp = _require_admin()
    if err_resp:
        return err_resp

    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if cur.fetchone() is None:
            return jsonify({'detail': 'User not found'}), 404

        body     = request.get_json(silent=True) or {}
        fields, values = [], []

        full_name = (body.get('full_name') or '').strip()
        username  = (body.get('username') or '').strip()
        password  = (body.get('password') or '').strip()
        active    = body.get('active')
        new_role  = (body.get('role') or '').strip()

        if full_name:
            fields.append("full_name = %s"); values.append(full_name)
        if username:
            fields.append("username = %s"); values.append(username)
        if password:
            fields.append("password_hash = %s"); values.append(pwd_context.hash(password))
        if active is not None:
            fields.append("active = %s"); values.append(active)

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

        if new_role:
            if new_role not in VALID_ROLES:
                return jsonify({'detail': f'role must be one of {VALID_ROLES}'}), 400
            _assign_role(cur, user_id, new_role)

        if not fields and not new_role:
            return jsonify({'detail': 'No valid fields provided to update'}), 400

        conn.commit()

        user = _user_to_dict(user_row)
        user['role'] = _get_user_role(cur, user_id)
        return jsonify({'message': 'User updated successfully', 'user': user})
    except ValueError as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({'detail': str(e)}), 400
    finally:
        cur.close()
        release_connection(conn)
