"""RelationshipModule 통합 테스트 (ModuleManager + 인메모리 SQLite)"""

import json
from typing import List

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import Session, sessionmaker

from src.core.event_bus import GameEvent
from src.core.event_types import EventTypes
from src.core.npc.models import HEXACO
from src.core.relationship.models import RelationshipStatus
from src.core.world_generator import WorldGenerator
from src.core.navigator import Navigator
from src.core.sub_grid import SubGridGenerator
from src.core.axiom_system import AxiomLoader
from src.db.models import Base
from src.db.models_v2 import NPCModel
from src.modules.base import GameContext
from src.modules.geography.module import GeographyModule
from src.modules.module_manager import ModuleManager
from src.modules.npc.module import NPCCoreModule
from src.modules.relationship.module import RelationshipModule


@pytest.fixture()
def setup():
    """인메모리 DB + ModuleManager + Geography + NPC + Relationship 모듈"""
    engine = create_engine("sqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
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

    # Geography 모듈 (Layer 1)
    axiom_loader = AxiomLoader("src/data/itw_214_divine_axioms.json")
    world_gen = WorldGenerator(axiom_loader=axiom_loader)
    sub_grid_gen = SubGridGenerator(axiom_loader, seed=42)
    navigator = Navigator(world_gen, axiom_loader, sub_grid_gen)
    geo_module = GeographyModule(world_gen, navigator, sub_grid_gen)

    # NPC 모듈 (Layer 2)
    npc_module = NPCCoreModule(session, bus)

    # Relationship 모듈 (Layer 3)
    rel_module = RelationshipModule(session, bus)

    manager.register(geo_module)
    manager.register(npc_module)
    manager.register(rel_module)

    manager.enable("geography")
    manager.enable("npc_core")
    manager.enable("relationship")

    return manager, rel_module, session, bus


# ── helpers ──────────────────────────────────────────────────


def _insert_npc(
    session: Session,
    npc_id: str,
    node_id: str = "node_001",
    role: str = "merchant",
) -> NPCModel:
    """테스트용 NPC 삽입"""
    model = NPCModel(
        npc_id=npc_id,
        full_name=json.dumps({"given": "Test", "family": "NPC"}),
        given_name="Test",
        hexaco=json.dumps({"H": 0.5, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}),
        character_sheet="{}",
        resonance_shield="{}",
        current_node=node_id,
        origin_type="organic",
        role=role,
    )
    session.add(model)
    session.flush()
    return model


def _make_context(
    session: Session, player_id: str = "p-001", turn: int = 1
) -> GameContext:
    """테스트용 GameContext 생성"""
    return GameContext(
        player_id=player_id,
        current_node_id="node_001",
        current_turn=turn,
        db_session=session,
    )


# ── 테스트 ───────────────────────────────────────────────────


def test_module_register_and_initialize(setup):
    """ModuleManager에 등록 → enable 성공 → 속성 확인"""
    manager, rel_module, _, _ = setup

    assert manager.is_enabled("relationship") is True
    assert rel_module.name == "relationship"
    assert rel_module.enabled is True
    assert rel_module.dependencies == ["npc_core"]


def test_npc_promoted_creates_relationships(setup):
    """npc_promoted 이벤트 발행 → 초기 관계 생성 확인"""
    _, rel_module, session, bus = setup

    # 기존 NPC 2명 + 신규 NPC
    _insert_npc(session, "npc-001", "node_001")
    _insert_npc(session, "npc-002", "node_001")
    _insert_npc(session, "npc-new", "node_001")

    bus.emit(
        GameEvent(
            event_type=EventTypes.NPC_PROMOTED,
            data={"npc_id": "npc-new", "node_id": "node_001"},
            source="npc_service",
        )
    )

    # 공개 API로 관계 조회
    rels = rel_module.get_relationships_for("npc", "npc-new")
    assert len(rels) == 2
    for rel in rels:
        assert rel.source_id == "npc-new"
        assert rel.familiarity == 5
        assert rel.status == RelationshipStatus.ACQUAINTANCE


def test_dialogue_ended_applies_delta(setup):
    """dialogue_ended 이벤트 + delta → 수치 변동 확인"""
    _, rel_module, session, bus = setup

    # 먼저 관계 생성 (공개 API 경유하지 않고 서비스 직접 사용)
    assert rel_module._service is not None
    rel_module._service.create_relationship(
        "player", "p-001", "npc", "npc-001", affinity=0.0
    )

    bus.emit(
        GameEvent(
            event_type=EventTypes.DIALOGUE_ENDED,
            data={
                "player_id": "p-001",
                "npc_id": "npc-001",
                "relationship_delta": {
                    "affinity": 3.0,
                    "reason": "friendly_chat",
                },
            },
            source="dialogue_service",
        )
    )

    rel = rel_module.get_relationship("player", "p-001", "npc", "npc-001")
    assert rel is not None
    # affinity 0 + 3 (damping at 0 = 1.0) = 3.0
    assert rel.affinity == pytest.approx(3.0, abs=0.1)
    # familiarity +1 from dialogue
    assert rel.familiarity == 1


def test_attitude_request_response(setup):
    """attitude_request 이벤트 → attitude_response 수신 확인"""
    _, rel_module, session, bus = setup

    # 관계 생성
    assert rel_module._service is not None
    rel_module._service.create_relationship(
        "player",
        "player-001",
        "npc",
        "npc-001",
        affinity=35.0,
        trust=45.0,
        familiarity=8,
        status=RelationshipStatus.FRIEND,
    )

    # attitude_response 캡처
    responses: List[GameEvent] = []
    bus.subscribe(EventTypes.ATTITUDE_RESPONSE, lambda e: responses.append(e))

    hexaco = HEXACO(H=0.4, E=0.3, X=0.6, A=0.7, C=0.8, O=0.3)

    bus.emit(
        GameEvent(
            event_type=EventTypes.ATTITUDE_REQUEST,
            data={
                "request_id": "req-001",
                "npc_id": "npc-001",
                "target_id": "player-001",
                "hexaco": hexaco,
                "memory_tags": ["paid_on_time"],
                "include_npc_opinions": False,
            },
            source="dialogue_service",
        )
    )

    assert len(responses) == 1
    resp_data = responses[0].data
    assert resp_data["request_id"] == "req-001"
    assert resp_data["npc_id"] == "npc-001"
    assert resp_data["target_id"] == "player-001"
    assert 2 <= len(resp_data["attitude_tags"]) <= 7
    assert resp_data["relationship_status"] == "friend"
    assert "friendly" in resp_data["attitude_tags"]


def test_process_turn_decay(setup):
    """process_turn 호출 → familiarity 감쇠 확인"""
    manager, rel_module, session, _ = setup

    # 관계 생성 (last_interaction_turn=0, familiarity=10)
    assert rel_module._service is not None
    rel_module._service.create_relationship(
        "player",
        "p-001",
        "npc",
        "npc-001",
        familiarity=10,
        last_interaction_turn=0,
    )

    # 60턴 후 process_turn 호출
    context = _make_context(session, turn=60)
    manager.process_turn(context)

    rel = rel_module.get_relationship("player", "p-001", "npc", "npc-001")
    assert rel is not None
    # 60일 → decay = 60 // 30 = 2 → familiarity = 10 - 2 = 8
    assert rel.familiarity == 8


def test_dialogue_ended_no_delta_no_change(setup):
    """dialogue_ended에 delta 없으면 수치 변동 없음"""
    _, rel_module, session, bus = setup

    assert rel_module._service is not None
    rel_module._service.create_relationship(
        "player", "p-001", "npc", "npc-001", affinity=10.0
    )

    bus.emit(
        GameEvent(
            event_type=EventTypes.DIALOGUE_ENDED,
            data={
                "player_id": "p-001",
                "npc_id": "npc-001",
                # no relationship_delta
            },
            source="dialogue_service",
        )
    )

    rel = rel_module.get_relationship("player", "p-001", "npc", "npc-001")
    assert rel is not None
    assert rel.affinity == 10.0  # 변동 없음
