"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api.game import router as game_router
from src.api.health import router as health_router
from src.config import settings
from src.core.engine import ITWEngine
from src.core.logging import get_logger, setup_logging
from src.db.database import engine as db_engine
from src.db.models import Base
from src.services.ai import get_ai_provider
from src.services.narrative_service import NarrativeService

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

# 글로벌 게임 엔진 인스턴스
game_engine: ITWEngine | None = None


def get_game_engine() -> ITWEngine:
    """게임 엔진 인스턴스 반환 (의존성 주입용)"""
    if game_engine is None:
        raise RuntimeError("Game engine not initialized")
    return game_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    global game_engine

    # DB 테이블 생성
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=db_engine)
    logger.info("Database tables created.")

    # 게임 엔진 초기화
    logger.info("Initializing game engine...")
    game_engine = ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )
    logger.info("Game engine initialized.")

    # AI Provider 및 NarrativeService 초기화
    logger.info("Initializing AI provider...")
    ai_provider = get_ai_provider()
    narrative_service = NarrativeService(ai_provider)
    app.state.narrative_service = narrative_service
    logger.info(f"AI provider initialized: {ai_provider.name}")

    yield

    # 종료 시 정리
    logger.info("Shutting down game engine...")
    game_engine = None


app = FastAPI(title="Infinite Text World", lifespan=lifespan)

app.include_router(health_router)
app.include_router(game_router)
