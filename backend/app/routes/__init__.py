from fastapi import FastAPI

from .auth import router as auth_router
from .downloads import files_router, videos_router
from .health import router as health_router
from .run import router as run_router
from .uploads import router as uploads_router

__all__ = ["register_routes"]


def register_routes(app: FastAPI) -> None:
    """Attach all application routers to the provided FastAPI app."""

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(run_router, prefix="/api/v1")
    app.include_router(videos_router, prefix="/api/v1")
    app.include_router(files_router, prefix="/api/v1")
    app.include_router(uploads_router, prefix="/api/v1")
