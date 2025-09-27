from fastapi import FastAPI

from .downloads import files_router, videos_router
from .health import router as health_router
from .run import router as run_router

__all__ = ["register_routes"]


def register_routes(app: FastAPI) -> None:
    """Attach all application routers to the provided FastAPI app."""

    app.include_router(health_router)
    app.include_router(run_router)
    app.include_router(videos_router)
    app.include_router(files_router)
