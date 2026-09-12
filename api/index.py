import os
import psycopg2
from fastapi import FastAPI

app = FastAPI()


def check_db():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return {"status": "unhealthy", "db": "disconnected", "error": "DATABASE_URL not set"}
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn.cursor().execute("SELECT 1")
        conn.close()
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "db": "disconnected", "error": str(e)}


@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health():
    return check_db()


@app.get("/debug")
@app.get("/api/debug")
def debug():
    """Temporary: show all env vars visible to this function."""
    import os
    keys = list(os.environ.keys())
    has_db = "DATABASE_URL" in os.environ
    return {
        "has_DATABASE_URL": has_db,
        "env_var_count": len(keys),
        "all_keys": sorted(keys),
    }
