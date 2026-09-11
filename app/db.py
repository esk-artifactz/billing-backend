from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_connection_pool: pool.ThreadedConnectionPool | None = None


def init_pool(database_url: str, min_conn: int, max_conn: int) -> None:
    """Initialise the global psycopg2 connection pool."""
    global _connection_pool
    _connection_pool = pool.ThreadedConnectionPool(
        min_conn,
        max_conn,
        dsn=database_url,
        connect_timeout=15,
    )


def get_connection():
    """Borrow a connection from the pool."""
    return _connection_pool.getconn()


def release_connection(conn) -> None:
    """Return a connection to the pool."""
    _connection_pool.putconn(conn)


def get_cursor(conn):
    """Return a RealDictCursor so rows come back as plain dicts."""
    return conn.cursor(cursor_factory=RealDictCursor)
