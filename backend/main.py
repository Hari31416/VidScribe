from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import register_routes
from app.setup_admin_user import setup_admin_user
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for the application.
    Runs startup and shutdown tasks.
    """
    logger.info("🚀 Application starting up...")

    # Run admin user setup
    try:
        setup_admin_user()
    except Exception as e:
        logger.error(f"Failed to setup admin user: {e}")
        # We don't stop the app, but we log the error

    yield

    logger.info("🛑 Application shutting down...")


app = FastAPI(title="VidScribe API", version="0.1.0", lifespan=lifespan)

# Allow access from typical local dev origins. Adjust as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; narrow this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_routes(app)
