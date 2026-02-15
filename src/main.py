"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from src.api.game import router as game_router
from src.api.health import router as health_router
from src.config import settings
from src.core.engine import ITWEngine
from src.core.event_bus import EventBus
from src.core.logging import get_logger, setup_logging
from src.db.database import SessionLocal, engine as db_engine
from src.db.models import Base
import src.db.models_v2  # noqa: F401  Phase 2 테이블 등록
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.registry import PrototypeRegistry
from src.services.ai import get_ai_provider
from src.services.dialogue_service import DialogueService
from src.services.item_service import ItemService
from src.services.narrative_service import NarrativeService
from src.services.companion_service import CompanionService
from src.services.quest_service import QuestService

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

    # DialogueService 초기화
    logger.info("Initializing DialogueService...")
    event_bus = EventBus()
    db_session = SessionLocal()
    dialogue_service = DialogueService(db_session, event_bus, narrative_service)
    app.state.dialogue_service = dialogue_service
    app.state.event_bus = event_bus
    logger.info("DialogueService initialized.")

    # ItemService 초기화
    logger.info("Initializing ItemService...")
    registry = PrototypeRegistry()
    registry.load_from_json("src/data/seed_items.json")

    axiom_mapping = AxiomTagMapping()
    axiom_mapping.load_from_json("src/data/axiom_tag_mapping.json")

    item_service = ItemService(
        db=db_session,
        event_bus=event_bus,
        registry=registry,
        axiom_mapping=axiom_mapping,
    )
    item_service.sync_prototypes_to_db()
    app.state.item_service = item_service
    logger.info("ItemService initialized (60 prototypes synced).")

    # QuestService 초기화
    logger.info("Initializing QuestService...")
    quest_service = QuestService(
        db=db_session,
        event_bus=event_bus,
    )
    app.state.quest_service = quest_service
    logger.info("QuestService initialized.")

    # CompanionService 초기화
    logger.info("Initializing CompanionService...")
    companion_service = CompanionService(
        db=db_session,
        event_bus=event_bus,
    )
    app.state.companion_service = companion_service
    logger.info("CompanionService initialized.")

    yield

    # 종료 시 정리
    logger.info("Shutting down...")
    db_session.close()
    game_engine = None


app = FastAPI(title="Infinite Text World", lifespan=lifespan)

app.include_router(health_router)
app.include_router(game_router)
