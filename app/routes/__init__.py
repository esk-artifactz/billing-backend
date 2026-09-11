from flask import Flask
from app.routes.auth import auth_bp


def register_blueprints(app: Flask) -> None:
    """Register all route blueprints with the Flask app."""
    app.register_blueprint(auth_bp, url_prefix='/api')
