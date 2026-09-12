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
