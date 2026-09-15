from dotenv import load_dotenv
load_dotenv()  # no-op on Vercel (no .env file); env vars come from Vercel dashboard

from flask import Flask, jsonify
from flask_cors import CORS

from app.routes import register_routes
from app.db_init import ensure_db


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(__name__)
    CORS(app)

    # Register all routes
    register_routes(app)

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
            return jsonify({'status': 'healthy', 'message': 'Billing API is running', 'db': 'connected'})
        except Exception as e:
            return jsonify({'status': 'unhealthy', 'message': str(e)}), 500

    return app
