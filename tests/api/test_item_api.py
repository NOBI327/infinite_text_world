"""아이템 API 통합 테스트

#11-D 검증: 최소 7개 API 테스트 케이스.
TestClient + in-memory SQLite + MockProvider.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.game import router as game_router
from src.core.engine import ITWEngine
from src.core.event_bus import EventBus
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.registry import PrototypeRegistry
from src.db.models import Base
from src.services.ai import MockProvider
from src.services.dialogue_service import DialogueService
from src.services.item_service import ItemService
from src.services.narrative_service import NarrativeService

SEED_ITEMS_PATH = Path("src/data/seed_items.json")
AXIOM_TAG_MAPPING_PATH = Path("src/data/axiom_tag_mapping.json")


@pytest.fixture()
def client():
    """TestClient + 인메모리 환경 세팅"""
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa_event.listens_for(db_engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(db_engine)
    session_factory = sessionmaker(bind=db_engine)
    db = session_factory()

    bus = EventBus()
    provider = MockProvider()
    narrative_service = NarrativeService(provider)
    dialogue_service = DialogueService(db, bus, narrative_service)

    registry = PrototypeRegistry()
    registry.load_from_json(SEED_ITEMS_PATH)

    axiom_mapping = AxiomTagMapping()
    axiom_mapping.load_from_json(AXIOM_TAG_MAPPING_PATH)

    item_service = ItemService(db, bus, registry, axiom_mapping)
    item_service.sync_prototypes_to_db()

    engine = ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )

    app = FastAPI()
    app.include_router(game_router)
    app.state.narrative_service = narrative_service
    app.state.dialogue_service = dialogue_service
    app.state.item_service = item_service

    import src.main

    original_engine = src.main.game_engine
    src.main.game_engine = engine

    engine.register_player("test_player")

    yield TestClient(app), item_service

    src.main.game_engine = original_engine
    db.close()


# ── inventory ────────────────────────────────────────────────


class TestInventoryAPI:
    def test_empty_inventory(self, client) -> None:
        tc, item_service = client
        resp = tc.post(
            "/game/action",
            json={"player_id": "test_player", "action": "inventory", "params": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["items"] == []

    def test_inventory_with_items(self, client) -> None:
        tc, item_service = client
        item_service.create_instance("wpn_rusty_sword", "player", "test_player")
        resp = tc.post(
            "/game/action",
            json={"player_id": "test_player", "action": "inventory", "params": {}},
        )
        data = resp.json()
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["prototype_id"] == "wpn_rusty_sword"


# ── pickup ───────────────────────────────────────────────────


class TestPickupAPI:
    def test_pickup_success(self, client) -> None:
        tc, item_service = client
        inst = item_service.create_instance("wpn_rusty_sword", "node", "0_0")
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "pickup",
                "params": {"instance_id": inst.instance_id},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify item moved to player
        fetched = item_service.get_instance(inst.instance_id)
        assert fetched is not None
        assert fetched.owner_type == "player"

    def test_pickup_not_on_ground(self, client) -> None:
        tc, item_service = client
        inst = item_service.create_instance("wpn_rusty_sword", "player", "other_player")
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "pickup",
                "params": {"instance_id": inst.instance_id},
            },
        )
        assert resp.status_code == 400


# ── drop ─────────────────────────────────────────────────────


class TestDropAPI:
    def test_drop_success(self, client) -> None:
        tc, item_service = client
        inst = item_service.create_instance("wpn_rusty_sword", "player", "test_player")
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "drop",
                "params": {"instance_id": inst.instance_id},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ── use ──────────────────────────────────────────────────────


class TestUseAPI:
    def test_use_durability_loss(self, client) -> None:
        tc, item_service = client
        inst = item_service.create_instance("wpn_rusty_sword", "player", "test_player")
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "use",
                "params": {"instance_id": inst.instance_id},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["broken"] is False
        assert data["data"]["new_durability"] == 28

    def test_use_until_broken(self, client) -> None:
        tc, item_service = client
        inst = item_service.create_instance(
            "wpn_rusty_sword", "player", "test_player", current_durability=1
        )
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "use",
                "params": {"instance_id": inst.instance_id},
            },
        )
        data = resp.json()
        assert data["data"]["broken"] is True


# ── browse ───────────────────────────────────────────────────


class TestBrowseAPI:
    def test_browse_container(self, client) -> None:
        tc, item_service = client
        shelf = item_service.create_instance("misc_shop_shelf", "node", "0_0")
        item_service.create_instance("wpn_rusty_sword", "container", shelf.instance_id)
        resp = tc.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "browse",
                "params": {"container_id": shelf.instance_id},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["prototype_id"] == "wpn_rusty_sword"
