from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import config_by_name
from app.db import init_pool, get_connection, release_connection, get_cursor
from app.routes import register_routers


def create_app(config_name: str = 'default') -> FastAPI:
    cfg = config_by_name[config_name]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: initialise the connection pool and DB tables
        init_pool(cfg.DATABASE_URL, cfg.DB_POOL_MIN_CONN, cfg.DB_POOL_MAX_CONN)
        from app.models import init_db
        conn = get_connection()
        try:
            init_db(conn)
            print("Database tables initialised successfully.")
        finally:
            release_connection(conn)
        yield
        # Shutdown: nothing special needed for psycopg2 pool

    app = FastAPI(
        title="Crown Tea Hub Billing API",
        version="1.0.0",
        lifespan=lifespan,
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
