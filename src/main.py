"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api.health import router as health_router
from src.config import settings
from src.core.logging import get_logger, setup_logging
from src.db.database import engine
from src.db.models import Base

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")
    yield


app = FastAPI(title="Infinite Text World", lifespan=lifespan)

app.include_router(health_router)
