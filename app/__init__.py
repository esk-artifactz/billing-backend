from flask import Flask
from flask_cors import CORS
from app.config import config_by_name
from app.db import init_pool, get_connection, release_connection
from app.routes import register_blueprints


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(__name__)
    cfg = config_by_name[config_name]
    app.config.from_object(cfg)

    # Initialise psycopg2 connection pool
    init_pool(cfg.DATABASE_URL, cfg.DB_POOL_MIN_CONN, cfg.DB_POOL_MAX_CONN)

    CORS(app)

    # Register all blueprints
    register_blueprints(app)

    # Health check
    @app.route('/health')
    def health_check():
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            release_connection(conn)
            return {'status': 'healthy', 'message': 'Billing API is running', 'db': 'connected'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}, 500

    return app
