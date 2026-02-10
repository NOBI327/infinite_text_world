"""NPCCoreModule 통합 테스트 (ModuleManager + 인메모리 SQLite)"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import GameEvent
from src.core.event_types import EventTypes
from src.db.models import Base
from src.db.models_v2 import BackgroundEntityModel, NPCModel
from src.modules.geography.module import GeographyModule
from src.modules.module_manager import ModuleManager
from src.modules.npc.module import NPCCoreModule
from src.core.world_generator import WorldGenerator
from src.core.navigator import Navigator
from src.core.sub_grid import SubGridGenerator
from src.core.axiom_system import AxiomLoader


@pytest.fixture()
def setup():
    """인메모리 DB + ModuleManager + NPCCoreModule + GeographyModule"""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # ModuleManager (자체 EventBus 소유)
    manager = ModuleManager()
    bus = manager.event_bus

    # Geography 모듈 (npc_core 의존성)
    axiom_loader = AxiomLoader("src/data/itw_214_divine_axioms.json")
    world_gen = WorldGenerator(axiom_loader=axiom_loader)
    sub_grid_gen = SubGridGenerator(axiom_loader, seed=42)
    navigator = Navigator(world_gen, axiom_loader, sub_grid_gen)
    geo_module = GeographyModule(world_gen, navigator, sub_grid_gen)

    # NPC 모듈
    npc_module = NPCCoreModule(session, bus)

    manager.register(geo_module)
    manager.register(npc_module)
    manager.enable("geography")
    manager.enable("npc_core")

    return manager, npc_module, session, bus


def _insert_entity(session, entity_id="e-001", node_id="3_5", role="innkeeper"):
    """테스트용 배경 엔티티 삽입"""
    model = BackgroundEntityModel(
        entity_id=entity_id,
        entity_type="resident",
        current_node=node_id,
        home_node=node_id,
        role=role,
        promotion_score=0,
    )
    session.add(model)
    session.flush()
    return model


# ── 테스트 ───────────────────────────────────────────────────


def test_module_register_and_enable(setup):
    """ModuleManager에 등록 + 활성화 → enabled=True, name='npc_core'"""
    manager, npc_module, _, _ = setup

    assert manager.is_enabled("npc_core") is True
    assert npc_module.name == "npc_core"
    assert npc_module.enabled is True
    assert npc_module.dependencies == ["geography"]


def test_npc_needed_event_handling(setup):
    """npc_needed 이벤트 → 퀘스트용 NPC 자동 생성"""
    _, _, session, bus = setup

    bus.emit(
        GameEvent(
            event_type=EventTypes.NPC_NEEDED,
            data={"role": "merchant", "node_id": "7_2"},
            source="quest_service",
        )
    )

    # NPC가 생성되었는지 확인
    row = session.query(NPCModel).filter_by(role="merchant").first()
    assert row is not None
    assert row.current_node == "7_2"
    assert row.origin_type == "scripted"


def test_public_api_after_enable(setup):
    """활성화 후 공개 API 작동 확인"""
    _, npc_module, session, _ = setup

    # 배경 엔티티 삽입
    _insert_entity(session, "e-100", "5_5", "guard")

    # 공개 API로 조회
    entities = npc_module.get_background_entities_at_node("5_5")
    assert len(entities) == 1
    assert entities[0].entity_id == "e-100"

    # 승격
    status = npc_module.add_promotion_score("e-100", "ask_name")
    assert status == "promoted"

    # NPC 조회
    npcs = npc_module.get_npcs_at_node("5_5")
    assert len(npcs) == 1
    assert npcs[0].role == "guard"

    # ID 조회
    npc = npc_module.get_npc_by_id(npcs[0].npc_id)
    assert npc is not None
    assert npc.npc_id == npcs[0].npc_id
