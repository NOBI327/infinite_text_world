"""NPC Service 통합 테스트 (인메모리 SQLite + EventBus)"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.db.models import Base
from src.db.models_v2 import (
    BackgroundEntityModel,
    NPCMemoryModel,
    NPCModel,
    WorldPoolModel,
)
from src.services.npc_service import NPCService


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + NPC Service"""
    engine = create_engine("sqlite:///:memory:")

    # PRAGMA foreign_keys=ON
    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    bus = EventBus()
    service = NPCService(session, bus)
    return service, session, bus


# ── helpers ──────────────────────────────────────────────────


def _insert_entity(
    session: Session,
    entity_id: str = "e-001",
    entity_type: str = "resident",
    node_id: str = "3_5",
    role: str = "innkeeper",
    promotion_score: int = 0,
) -> BackgroundEntityModel:
    """테스트용 배경 엔티티 삽입"""
    model = BackgroundEntityModel(
        entity_id=entity_id,
        entity_type=entity_type,
        current_node=node_id,
        home_node=node_id if entity_type == "resident" else None,
        role=role,
        promotion_score=promotion_score,
    )
    session.add(model)
    session.flush()
    return model


# ── 테스트 ───────────────────────────────────────────────────


def test_create_background_entity_and_query(setup):
    """엔티티 생성 → get_background_entities_at_node 조회"""
    service, session, _ = setup
    _insert_entity(session, "e-001", "resident", "3_5", "innkeeper")
    _insert_entity(session, "e-002", "resident", "3_5", "patron")
    _insert_entity(session, "e-003", "resident", "4_4", "guard")

    entities = service.get_background_entities_at_node("3_5")
    assert len(entities) == 2
    assert {e.entity_id for e in entities} == {"e-001", "e-002"}


def test_promotion_flow(setup):
    """엔티티 생성 → ask_name(+50) → 즉시 승격 → NPCModel 존재 + promoted=True"""
    service, session, _ = setup
    _insert_entity(session, "e-010", "resident", "3_5", "innkeeper")

    status = service.add_promotion_score("e-010", "ask_name")
    assert status == "promoted"

    # background_entities에 promoted=True
    row = session.query(BackgroundEntityModel).filter_by(entity_id="e-010").first()
    assert row.promoted is True
    assert row.promoted_npc_id is not None

    # npcs 테이블에 레코드 존재
    npc_row = session.query(NPCModel).filter_by(npc_id=row.promoted_npc_id).first()
    assert npc_row is not None
    assert npc_row.role == "innkeeper"
    assert npc_row.origin_type == "promoted"


def test_promotion_event_emitted(setup):
    """승격 시 EventBus에 npc_promoted 이벤트 수신 확인"""
    service, session, bus = setup
    _insert_entity(session, "e-020", "resident", "3_5", "guard")

    received_events: list[GameEvent] = []
    bus.subscribe(EventTypes.NPC_PROMOTED, received_events.append)

    service.add_promotion_score("e-020", "ask_name")

    assert len(received_events) == 1
    ev = received_events[0]
    assert ev.event_type == EventTypes.NPC_PROMOTED
    assert ev.data["origin_type"] == "resident"
    assert ev.data["node_id"] == "3_5"
    assert "npc_id" in ev.data


def test_worldpool_registration(setup):
    """15점 이상 wanderer → WorldPool 레코드 존재"""
    service, session, _ = setup
    _insert_entity(session, "e-030", "wanderer", "5_5", "traveler")

    # greet = +15 → worldpool 임계값
    status = service.add_promotion_score("e-030", "greet")
    assert status == "worldpool"

    wp = session.query(WorldPoolModel).filter_by(entity_id="e-030").first()
    assert wp is not None
    assert wp.entity_type == "wanderer"
    assert wp.promotion_score == 15


def test_create_npc_for_quest(setup):
    """퀘스트용 NPC 생성 → npc_created 이벤트 확인"""
    service, session, bus = setup

    received_events: list[GameEvent] = []
    bus.subscribe(EventTypes.NPC_CREATED, received_events.append)

    npc = service.create_npc_for_quest("merchant", "7_2")
    assert npc.npc_id != ""
    assert npc.role == "merchant"
    assert npc.current_node == "7_2"
    assert npc.origin_type == "scripted"

    # DB에 존재
    row = session.query(NPCModel).filter_by(npc_id=npc.npc_id).first()
    assert row is not None

    # 이벤트
    assert len(received_events) == 1
    assert received_events[0].data["role"] == "merchant"


def test_save_and_get_memories(setup):
    """기억 저장 → 컨텍스트 조회 → Tier 1+2만 반환"""
    service, session, _ = setup

    # NPC 먼저 생성
    npc = service.create_npc_for_quest("guard", "3_5")
    npc_id = npc.npc_id

    # 기억 3개 저장 (importance < 0.8이므로 전부 Tier 2)
    service.save_memory(npc_id, "encounter", "첫 조우", turn=1)
    service.save_memory(npc_id, "conversation", "대화", turn=2)
    service.save_memory(npc_id, "trade", "거래", turn=3)

    context = service.get_memories_for_context(npc_id)
    assert len(context) == 3
    assert all(m.tier in (1, 2) for m in context)
    # turn 오름차순
    turns = [m.turn_created for m in context]
    assert turns == sorted(turns)


def test_tier1_slot_management_via_service(setup):
    """고임팩트 기억 6개 저장 → 고정 2 + 교체 3 + 강등 1"""
    service, session, _ = setup

    npc = service.create_npc_for_quest("scholar", "1_1")
    npc_id = npc.npc_id

    # 고임팩트 기억 6개 저장 (importance ≥ 0.8)
    for i in range(6):
        service.save_memory(
            npc_id,
            "betrayal",
            f"배신 {i}",
            turn=i + 1,
            emotional_valence=-0.8,
        )

    # DB에서 모든 기억 조회
    all_rows = session.query(NPCMemoryModel).filter_by(npc_id=npc_id).all()
    assert len(all_rows) == 6

    tier1_rows = [r for r in all_rows if r.tier == 1]
    tier2_rows = [r for r in all_rows if r.tier == 2]

    # Tier 1 = 고정 2 + 교체 3 = 5개
    assert len(tier1_rows) == 5
    # Tier 2 = 강등 1개
    assert len(tier2_rows) == 1

    # 고정 슬롯 확인
    fixed = [r for r in tier1_rows if r.is_fixed]
    assert len(fixed) == 2
    fixed_slots = {r.fixed_slot for r in fixed}
    assert fixed_slots == {1, 2}
