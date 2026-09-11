import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root before anything else
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

import uvicorn
from app import create_app

env = os.environ.get('APP_ENV', 'default')
app = create_app(env)

if __name__ == '__main__':
    uvicorn.run(
        'run:app',
        host='0.0.0.0',
        port=8000,
        reload=True,  # local dev only — Vercel ignores this block
    )
