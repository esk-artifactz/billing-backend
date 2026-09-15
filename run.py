import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env for local dev (no-op on Vercel — env vars come from dashboard)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
