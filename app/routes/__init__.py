from flask import Flask
from app.routes.auth import auth_bp


def register_routes(app: Flask) -> None:
    """Register all blueprints with the Flask app."""
    app.register_blueprint(auth_bp, url_prefix='/api')
