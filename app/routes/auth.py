from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
from werkzeug.security import check_password_hash as werkzeug_check, generate_password_hash as werkzeug_hash

from app.db import get_connection, release_connection, get_cursor
from app.db_init import ensure_db

auth_router = APIRouter()

VALID_ROLES = ('Admin', 'Cashier')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify against bcrypt (new) or Werkzeug (legacy) hashes."""
    # Werkzeug hashes start with 'scrypt:' or 'pbkdf2:' or 'sha256$'
    if hashed.startswith(('scrypt:', 'pbkdf2:', 'sha256$')):
        return werkzeug_check(hashed, plain)
    return pwd_context.verify(plain, hashed)


def _needs_rehash(hashed: str) -> bool:
    """Return True if the hash is a legacy Werkzeug hash."""
    return hashed.startswith(('scrypt:', 'pbkdf2:', 'sha256$'))


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    active: Optional[bool] = None
    role: Optional[str] = None


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

@auth_router.post('/register', status_code=201)
def register(body: RegisterRequest):
    ensure_db()
    username  = body.username.strip()
    password  = body.password.strip()
    full_name = body.full_name.strip()
    role      = body.role.strip()

    if not username or not password or not full_name:
        raise HTTPException(status_code=400, detail='username, password, and full_name are required')

    if not role or role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f'role is required and must be one of {VALID_ROLES}')

    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail='Username already exists')

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
        return {'message': 'User created successfully', 'user': user}
    except HTTPException:
        conn.rollback()
        raise
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# POST /api/login
# ---------------------------------------------------------------------------

@auth_router.post('/login')
def login(body: LoginRequest):
    ensure_db()
    username = body.username.strip()
    password = body.password.strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail='username and password are required')

    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user is None or not _verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail='Invalid username or password')

        if not user['active']:
            raise HTTPException(status_code=403, detail='Account is disabled')

        # Migrate legacy Werkzeug hash → bcrypt on first successful login
        if _needs_rehash(user['password_hash']):
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (pwd_context.hash(password), user['id']),
            )
            conn.commit()

        user_data = _user_to_dict(user)
        user_data['role'] = _get_user_role(cur, user['id'])
        return {'message': 'Login successful', 'user': user_data}
    finally:
        cur.close()
        release_connection(conn)


# ---------------------------------------------------------------------------
# PUT /api/users/<id>
# ---------------------------------------------------------------------------

@auth_router.put('/users/{user_id}')
def update_user(user_id: int, body: UpdateUserRequest):
    ensure_db()
    conn = get_connection()
    cur  = get_cursor(conn)
    try:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail='User not found')

        fields, values = [], []

        if body.full_name and body.full_name.strip():
            fields.append("full_name = %s")
            values.append(body.full_name.strip())

        if body.username and body.username.strip():
            fields.append("username = %s")
            values.append(body.username.strip())

        if body.password and body.password.strip():
            fields.append("password_hash = %s")
            values.append(pwd_context.hash(body.password.strip()))

        if body.active is not None:
            fields.append("active = %s")
            values.append(body.active)

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

        new_role = body.role.strip() if body.role else ''
        if new_role:
            if new_role not in VALID_ROLES:
                raise HTTPException(status_code=400, detail=f'role must be one of {VALID_ROLES}')
            _assign_role(cur, user_id, new_role)

        if not fields and not new_role:
            raise HTTPException(status_code=400, detail='No valid fields provided to update')

        conn.commit()

        user = _user_to_dict(user_row)
        user['role'] = _get_user_role(cur, user_id)
        return {'message': 'User updated successfully', 'user': user}
    except HTTPException:
        conn.rollback()
        raise
    except ValueError as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        release_connection(conn)
