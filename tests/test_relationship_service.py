"""Relationship Service 통합 테스트 (인메모리 SQLite + EventBus)"""

import json

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import Session, sessionmaker

from src.core.event_bus import EventBus
from src.core.event_types import EventTypes
from src.core.npc.models import HEXACO
from src.core.relationship.models import RelationshipStatus
from src.db.models import Base
from src.db.models_v2 import NPCModel
from src.services.relationship_service import RelationshipService


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + RelationshipService"""
    engine = create_engine("sqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    bus = EventBus()
    service = RelationshipService(session, bus)
    return service, session, bus


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


# ── test_create_and_get_relationship ─────────────────────────


class TestCreateAndGet:
    def test_create_and_get_relationship(self, setup):
        """생성 → 조회 → 필드 일치"""
        service, session, bus = setup

        rel = service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            affinity=10.0,
            trust=20.0,
            familiarity=3,
        )

        assert rel.source_type == "player"
        assert rel.source_id == "p-001"
        assert rel.target_type == "npc"
        assert rel.target_id == "npc-001"
        assert rel.affinity == 10.0
        assert rel.trust == 20.0
        assert rel.familiarity == 3
        assert rel.status == RelationshipStatus.STRANGER

        # 조회
        loaded = service.get_relationship("player", "p-001", "npc", "npc-001")
        assert loaded is not None
        assert loaded.relationship_id == rel.relationship_id
        assert loaded.affinity == 10.0
        assert loaded.trust == 20.0
        assert loaded.familiarity == 3


# ── test_apply_dialogue_delta ────────────────────────────────


class TestDialogueDelta:
    def test_apply_dialogue_delta_with_damping(self, setup):
        """affinity=50인 상태에서 +5 적용 → 감쇠된 값 확인"""
        service, session, bus = setup

        service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            affinity=50.0,
        )

        rel = service.apply_dialogue_delta("p-001", "npc-001", 5.0, "friendly_talk")

        # damping at 50: 1.0 - (50/100)^1.2 ≈ 0.5647
        # actual ≈ 5 * 0.5647 ≈ 2.82
        # new affinity ≈ 52.82
        assert 52.0 < rel.affinity < 53.5
        assert rel.familiarity == 1  # +1 자동 증가

    def test_apply_dialogue_delta_meta_clamp(self, setup):
        """+10 제안 → +5로 클램프됨"""
        service, session, bus = setup

        service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            affinity=0.0,
        )

        rel = service.apply_dialogue_delta("p-001", "npc-001", 10.0, "very_friendly")

        # 10 → clamped to 5, damping at 0 = 1.0, actual = 5.0
        assert rel.affinity == pytest.approx(5.0, abs=0.01)

    def test_apply_dialogue_delta_triggers_transition(self, setup):
        """familiarity 2 → 대화 후 familiarity 3 → stranger→acquaintance 전이 + 이벤트 발행"""
        service, session, bus = setup

        service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            familiarity=2,
        )

        # 이벤트 캡처
        events: list = []
        bus.subscribe(EventTypes.RELATIONSHIP_CHANGED, lambda e: events.append(e))

        rel = service.apply_dialogue_delta("p-001", "npc-001", 0.0, "greeting")

        assert rel.familiarity == 3
        assert rel.status == RelationshipStatus.ACQUAINTANCE
        assert len(events) == 1
        assert events[0].data["old_status"] == "stranger"
        assert events[0].data["new_status"] == "acquaintance"


# ── test_apply_action_delta ──────────────────────────────────


class TestActionDelta:
    def test_apply_action_delta(self, setup):
        """부탁 수행 → affinity+10, trust+15 → 감쇠 적용 + DB 갱신"""
        service, session, bus = setup

        service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            affinity=0.0,
            trust=0.0,
            familiarity=0,
        )

        rel = service.apply_action_delta(
            "p-001",
            "npc-001",
            affinity_delta=10.0,
            trust_delta=15.0,
            familiarity_delta=1,
            reason="quest_completed",
        )

        # damping at 0 = 1.0 → full delta
        assert rel.affinity == pytest.approx(10.0, abs=0.01)
        assert rel.trust == pytest.approx(15.0, abs=0.01)
        assert rel.familiarity == 1

        # DB 반영 확인
        loaded = service.get_relationship("player", "p-001", "npc", "npc-001")
        assert loaded.affinity == pytest.approx(10.0, abs=0.01)
        assert loaded.trust == pytest.approx(15.0, abs=0.01)


# ── test_apply_reversal ──────────────────────────────────────


class TestReversal:
    def test_apply_reversal_betrayal(self, setup):
        """반전 후 수치 확인 + relationship_reversed 이벤트 확인"""
        service, session, bus = setup

        service.create_relationship(
            "player",
            "p-001",
            "npc",
            "npc-001",
            affinity=45.0,
            trust=40.0,
            familiarity=10,
            status=RelationshipStatus.FRIEND,
        )

        events: list = []
        bus.subscribe(EventTypes.RELATIONSHIP_REVERSED, lambda e: events.append(e))

        rel = service.apply_reversal("p-001", "npc-001", "betrayal")

        # affinity = -45, trust = 40 * 0.3 = 12
        assert rel.affinity == pytest.approx(-45.0, abs=0.01)
        assert rel.trust == pytest.approx(12.0, abs=0.01)

        # 이벤트 확인
        assert len(events) == 1
        assert events[0].data["reversal_type"] == "betrayal"
        assert events[0].data["old_status"] == "friend"


# ── test_process_familiarity_decay ───────────────────────────


class TestFamiliarityDecay:
    def test_process_familiarity_decay(self, setup):
        """60일 경과 관계 3건 → 감쇠 후 familiarity 확인"""
        service, session, bus = setup

        # 3건 관계, 마지막 상호작용 turn 0, familiarity 10
        for i in range(3):
            service.create_relationship(
                "player",
                f"p-{i}",
                "npc",
                f"npc-{i}",
                familiarity=10,
                last_interaction_turn=0,
            )

        # 60일 후
        count = service.process_familiarity_decay(current_turn=60)

        assert count == 3

        # 60일 → decay = 60 // 30 = 2 → familiarity = 10 - 2 = 8
        for i in range(3):
            rel = service.get_relationship("player", f"p-{i}", "npc", f"npc-{i}")
            assert rel.familiarity == 8


# ── test_create_initial_npc_relationships ────────────────────


class TestInitialNPCRelationships:
    def test_create_initial_npc_relationships(self, setup):
        """NPC 2명 존재하는 노드에 신규 NPC 승격 → 2건 관계 생성"""
        service, session, bus = setup

        # 기존 NPC 2명 + 신규 NPC 삽입
        _insert_npc(session, "npc-001", "node_001")
        _insert_npc(session, "npc-002", "node_001")
        _insert_npc(session, "npc-new", "node_001")

        rels = service.create_initial_npc_relationships("npc-new", "node_001")

        assert len(rels) == 2
        for rel in rels:
            assert rel.source_id == "npc-new"
            assert rel.familiarity == 5
            assert rel.status == RelationshipStatus.ACQUAINTANCE
            assert -10.0 <= rel.affinity <= 20.0
            assert 10.0 <= rel.trust <= 30.0


# ── test_generate_attitude_full_pipeline ─────────────────────


class TestGenerateAttitude:
    def test_generate_attitude_full_pipeline(self, setup):
        """hexaco + memory_tags → AttitudeContext 반환, 태그 2~7개"""
        service, session, bus = setup

        # PC→NPC 관계 생성
        service.create_relationship(
            "player",
            "player-001",
            "npc",
            "npc-001",
            affinity=35.0,
            trust=45.0,
            familiarity=8,
            status=RelationshipStatus.FRIEND,
        )

        hexaco = HEXACO(H=0.4, E=0.3, X=0.6, A=0.7, C=0.8, O=0.3)
        memory_tags = ["paid_on_time", "paid_on_time", "discussed_weapon"]

        attitude = service.generate_attitude(
            npc_id="npc-001",
            target_id="player-001",
            hexaco=hexaco,
            memory_tags=memory_tags,
            include_npc_opinions=False,
        )

        assert attitude.target_npc_id == "npc-001"
        assert 2 <= len(attitude.attitude_tags) <= 7
        assert attitude.relationship_status == "friend"
        # 기본 태그: friendly (affinity 35 >= 20), cautious_trust (trust 45 >= 30)
        assert "friendly" in attitude.attitude_tags
        assert "cautious_trust" in attitude.attitude_tags
