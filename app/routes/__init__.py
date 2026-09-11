from fastapi import FastAPI
from app.routes.auth import auth_router


def register_routers(app: FastAPI) -> None:
    """Include all route routers with the FastAPI app."""
    app.include_router(auth_router, prefix='/api')
