"""Lazy one-time DB initialisation — safe to import anywhere."""

_db_initialised = False


def ensure_db() -> None:
    """Create tables on the first call; no-op on subsequent calls."""
    global _db_initialised
    if _db_initialised:
        return
    from app.db import get_connection, release_connection
    from app.models import init_db
    conn = get_connection()
    try:
        init_db(conn)
        print("Database tables initialised successfully.")
        _db_initialised = True
    finally:
        release_connection(conn)
