import os
import urllib.parse

import psycopg2
from psycopg2.extras import RealDictCursor


def _get_database_url() -> str:
    """Read and sanitise DATABASE_URL at call time (not import time)."""
    dsn = os.environ.get('DATABASE_URL', '')
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    parsed = urllib.parse.urlparse(dsn)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    params.pop('channel_binding', None)
    new_query = urllib.parse.urlencode({k: v[0] for k, v in params.items()})
    return parsed._replace(query=new_query).geturl()


def get_connection():
    """Open a fresh psycopg2 connection for this request."""
    return psycopg2.connect(_get_database_url(), connect_timeout=15)


def release_connection(conn) -> None:
    """Close the connection at end of request."""
    try:
        conn.close()
    except Exception:
        pass


def get_cursor(conn):
    """Return a RealDictCursor so rows come back as plain dicts."""
    return conn.cursor(cursor_factory=RealDictCursor)


# Keep init_pool as a no-op so no other imports break
def init_pool(*args, **kwargs) -> None:
    pass
