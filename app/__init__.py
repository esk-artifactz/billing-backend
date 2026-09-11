from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import register_routers
from app.db_init import ensure_db


def create_app(config_name: str = 'default') -> FastAPI:
    app = FastAPI(
        title="Crown Tea Hub Billing API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routers
    register_routers(app)

    # Health check
    @app.get('/health')
    def health_check():
        try:
            ensure_db()
            from app.db import get_connection, release_connection, get_cursor
            conn = get_connection()
            cur = get_cursor(conn)
            cur.execute('SELECT 1')
            cur.close()
            release_connection(conn)
            return {'status': 'healthy', 'message': 'Billing API is running', 'db': 'connected'}
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={'status': 'unhealthy', 'message': str(e)},
            )

    return app
