"""DialogueService 통합 테스트 (인메모리 SQLite + EventBus)

#10-D 검증: 최소 12개 테스트 케이스.
"""

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.db.models import Base
from src.db.models_v2 import DialogueSessionModel, DialogueTurnModel
from src.services.ai import MockProvider
from src.services.dialogue_service import DialogueService
from src.services.narrative_service import NarrativeService


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + DialogueService"""
    engine = create_engine("sqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    bus = EventBus()

    provider = MockProvider()
    narrative = NarrativeService(provider)

    service = DialogueService(db, bus, narrative)
    return service, db, bus


# ── helpers ──────────────────────────────────────────────────


def _default_npc_data() -> dict:
    return {
        "name": "Hans",
        "race": "human",
        "role": "blacksmith",
        "hexaco": {"H": 0.5, "E": 0.5, "X": 0.7, "A": 0.5, "C": 0.5, "O": 0.5},
        "manner_tags": ["polite"],
        "npc_opinions": {},
        "node_environment": "forge",
    }


def _default_relationship_data() -> dict:
    return {
        "status": "stranger",
        "familiarity": 0,
    }


def _start_session(service):
    """헬퍼: 기본 세션 시작"""
    return service.start_session(
        player_id="player_001",
        npc_id="npc_001",
        node_id="node_001",
        game_turn=10,
        npc_data=_default_npc_data(),
        relationship_data=_default_relationship_data(),
        npc_memories=["met_before"],
        pc_constraints={"axioms": ["Fire_01"], "items": ["rope"], "stats": {"EXEC": 2}},
    )


# ── start_session ──────────────────────────────────────────────


class TestStartSession:
    def test_session_creation(self, setup):
        """세션 생성 + 예산 계산"""
        service, db, bus = setup
        session = _start_session(service)

        assert session.session_id is not None
        assert session.player_id == "player_001"
        assert session.npc_id == "npc_001"
        assert session.status == "active"
        # stranger(3) + hexaco_x=0.7(+1) = 4
        assert session.budget_total == 4
        assert session.budget_remaining == 4

    def test_session_db_record(self, setup):
        """DB에 세션 레코드 생성 확인"""
        service, db, bus = setup
        session = _start_session(service)

        row = (
            db.query(DialogueSessionModel)
            .filter_by(session_id=session.session_id)
            .first()
        )
        assert row is not None
        assert row.player_id == "player_001"
        assert row.npc_id == "npc_001"
        assert row.budget_total == 4

    def test_dialogue_started_event(self, setup):
        """dialogue_started 이벤트 발행 확인"""
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.DIALOGUE_STARTED, lambda e: events.append(e))

        _start_session(service)

        assert len(events) == 1
        assert events[0].data["npc_id"] == "npc_001"


# ── process_turn ──────────────────────────────────────────────


class TestProcessTurn:
    def test_normal_turn(self, setup):
        """정상 대화 턴 (MockProvider)"""
        service, db, bus = setup
        _start_session(service)

        result = service.process_turn("こんにちは")

        assert result["session_status"] == "active"
        assert result["turn_index"] == 0
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_budget_decrease(self, setup):
        """budget 차감 + phase 전환"""
        service, db, bus = setup
        session = _start_session(service)
        initial_budget = session.budget_remaining

        service.process_turn("hello")

        assert session.budget_remaining == initial_budget - 1

    def test_pc_end_intent(self, setup):
        """PC 종료 의사 감지 (키워드)"""
        service, db, bus = setup
        _start_session(service)

        result = service.process_turn("bye")

        assert result["session_status"] == "ended_by_pc"
        assert service.get_active_session() is None

    def test_npc_end_conversation(self, setup):
        """NPC 종료 의사 — end_conversation: true 시뮬레이션"""
        service, db, bus = setup
        _start_session(service)

        # MockProvider는 wants_to_continue=True를 반환하므로
        # 정상적으로는 NPC 종료가 발생하지 않음
        # 직접 _check_npc_end_intent 테스트
        meta = {"dialogue_state": {"end_conversation": True, "wants_to_continue": True}}
        assert service._check_npc_end_intent(meta) is True

    def test_npc_no_continue(self, setup):
        """NPC wants_to_continue=False → 종료"""
        service, db, bus = setup
        meta = {
            "dialogue_state": {"end_conversation": False, "wants_to_continue": False}
        }
        assert service._check_npc_end_intent(meta) is True

    def test_budget_exhaustion(self, setup):
        """budget 0 → 하드 종료"""
        service, db, bus = setup
        session = _start_session(service)

        # 예산을 1로 강제 설정
        session.budget_remaining = 1

        result = service.process_turn("hello")

        # 1턴 실행 후 budget 0 → ended_by_budget
        assert result["session_status"] == "ended_by_budget"

    def test_turn_saved_to_db(self, setup):
        """턴 DB 저장 확인"""
        service, db, bus = setup
        session = _start_session(service)

        service.process_turn("こんにちは")

        rows = (
            db.query(DialogueTurnModel).filter_by(session_id=session.session_id).all()
        )
        assert len(rows) == 1
        assert rows[0].pc_input == "こんにちは"
        assert rows[0].turn_index == 0


# ── end_session ──────────────────────────────────────────────


class TestEndSession:
    def test_dialogue_ended_event(self, setup):
        """dialogue_ended 이벤트 발행 확인"""
        service, db, bus = setup
        _start_session(service)

        events = []
        bus.subscribe(EventTypes.DIALOGUE_ENDED, lambda e: events.append(e))
        bus.reset_chain()

        service.end_session("ended_by_pc")

        assert len(events) == 1
        assert events[0].data["reason"] == "ended_by_pc"
        assert events[0].data["npc_id"] == "npc_001"

    def test_db_updated_on_end(self, setup):
        """종료 시 DB 갱신"""
        service, db, bus = setup
        session = _start_session(service)

        service.end_session("ended_by_pc")

        row = (
            db.query(DialogueSessionModel)
            .filter_by(session_id=session.session_id)
            .first()
        )
        assert row is not None
        assert row.status == "ended_by_pc"

    def test_active_session_cleared(self, setup):
        """종료 후 active_session 해제"""
        service, db, bus = setup
        _start_session(service)

        service.end_session("ended_by_pc")

        assert service.get_active_session() is None


# ── EventBus 핸들러 ──────────────────────────────────────────


class TestEventHandlers:
    def test_on_attitude_response(self, setup):
        """태도 태그 수신 → npc_context에 반영"""
        service, db, bus = setup
        _start_session(service)

        bus.reset_chain()
        bus.emit(
            GameEvent(
                event_type=EventTypes.ATTITUDE_RESPONSE,
                data={"attitude_tags": ["friendly", "cautious"]},
                source="relationship_service",
            )
        )

        session = service.get_active_session()
        assert session is not None
        assert session.npc_context["attitude_tags"] == ["friendly", "cautious"]

    def test_on_quest_seed_generated(self, setup):
        """퀘스트 시드 수신 → 세션에 시드 주입"""
        service, db, bus = setup
        _start_session(service)

        seed = {"seed_id": "seed_001", "type": "rumor", "tier": 3}
        bus.reset_chain()
        bus.emit(
            GameEvent(
                event_type=EventTypes.QUEST_SEED_GENERATED,
                data={"seed": seed},
                source="quest_service",
            )
        )

        session = service.get_active_session()
        assert session is not None
        assert session.quest_seed == seed


# ── seed 전달 시나리오 ──────────────────────────────────────


class TestSeedDelivery:
    def test_seed_delivered_tracking(self, setup):
        """seed_delivered 추적"""
        service, db, bus = setup
        session = _start_session(service)

        assert session.seed_delivered is False
        assert session.seed_result is None
