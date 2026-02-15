"""CompanionService 통합 테스트 (인메모리 SQLite + EventBus)

#13-B 검증: 최소 23개 테스트 케이스.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.db.models import Base
from src.services.companion_service import CompanionService


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + CompanionService"""
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
    service = CompanionService(db, bus)
    return service, db, bus


# === 조회 ===


class TestGetActiveCompanion:
    def test_no_companion(self, setup) -> None:
        service, db, bus = setup
        assert service.get_active_companion("player1") is None

    def test_active_companion_returned(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            accepted, state = service.request_quest_companion(
                player_id="p1",
                npc_id="npc1",
                quest_id="q1",
                npc_hexaco_a=0.5,
                is_rescue=False,
                npc_origin_node="1_1",
                current_turn=10,
            )
        assert accepted is True
        companion = service.get_active_companion("p1")
        assert companion is not None
        assert companion.npc_id == "npc1"

    def test_is_companion_true(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        assert service.is_companion("p1", "npc1") is True

    def test_is_companion_false(self, setup) -> None:
        service, db, bus = setup
        assert service.is_companion("p1", "npc_unknown") is False


# === 퀘스트 동행 ===


class TestQuestCompanion:
    def test_accept(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            accepted, state = service.request_quest_companion(
                "p1", "npc1", "q1", 0.5, False, "1_1", 10
            )
        assert accepted is True
        assert state is not None
        assert state.companion_type == "quest"
        assert state.quest_id == "q1"

    def test_reject(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=False
        ):
            accepted, state = service.request_quest_companion(
                "p1", "npc1", "q1", 0.5, False, "1_1", 10
            )
        assert accepted is False
        assert state is None

    def test_already_has_companion(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
            accepted, state = service.request_quest_companion(
                "p1", "npc2", "q2", 0.5, False, "2_2", 11
            )
        assert accepted is False
        assert state is None

    def test_companion_joined_event(self, setup) -> None:
        service, db, bus = setup
        events: list = []
        bus.subscribe(EventTypes.COMPANION_JOINED, lambda e: events.append(e))
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        assert len(events) == 1
        assert events[0].data["npc_id"] == "npc1"


# === 자발적 동행 ===


class TestVoluntaryCompanion:
    def test_accept_no_condition(self, setup) -> None:
        service, db, bus = setup
        with (
            patch(
                "src.services.companion_service.voluntary_companion_accept",
                return_value=(True, None),
            ),
            patch(
                "src.services.companion_service.roll_condition",
                return_value=(False, None),
            ),
        ):
            accepted, reason, state = service.request_voluntary_companion(
                "p1", "npc1", "friend", 50, {"X": 0.5}, "1_1", 10
            )
        assert accepted is True
        assert reason is None  # no condition
        assert state is not None
        assert state.companion_type == "voluntary"
        assert state.condition_type is None

    def test_accept_with_condition(self, setup) -> None:
        service, db, bus = setup
        with (
            patch(
                "src.services.companion_service.voluntary_companion_accept",
                return_value=(True, None),
            ),
            patch(
                "src.services.companion_service.roll_condition",
                return_value=(True, "time_limit"),
            ),
            patch(
                "src.services.companion_service.generate_condition_data",
                return_value={"turn_limit": 30},
            ),
        ):
            accepted, reason, state = service.request_voluntary_companion(
                "p1", "npc1", "friend", 50, {"X": 0.5}, "1_1", 10
            )
        assert accepted is True
        assert reason == "time_limit"
        assert state is not None
        assert state.condition_type == "time_limit"
        assert state.condition_data == {"turn_limit": 30}

    def test_reject_insufficient_relationship(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.voluntary_companion_accept",
            return_value=(False, "insufficient_relationship"),
        ):
            accepted, reason, state = service.request_voluntary_companion(
                "p1", "npc1", "stranger", 0, {"X": 0.5}, "1_1", 10
            )
        assert accepted is False
        assert reason == "insufficient_relationship"
        assert state is None

    def test_stranger_always_rejected(self, setup) -> None:
        service, db, bus = setup
        # Using real acceptance logic — stranger base = 0.0
        accepted, reason, state = service.request_voluntary_companion(
            "p1", "npc1", "stranger", 0, {"X": 0.5}, "1_1", 10
        )
        assert accepted is False
        assert reason == "insufficient_relationship"


# === 해산 ===


class TestDismiss:
    def test_dismiss_success(self, setup) -> None:
        service, db, bus = setup
        events: list = []
        bus.subscribe(EventTypes.COMPANION_DISBANDED, lambda e: events.append(e))
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        state = service.dismiss_companion("p1", 20)
        assert state is not None
        assert state.npc_id == "npc1"
        assert len(events) == 1
        assert events[0].data["disband_reason"] == "pc_dismiss"

    def test_dismiss_no_companion(self, setup) -> None:
        service, db, bus = setup
        result = service.dismiss_companion("p1", 20)
        assert result is None

    def test_disband_quest_complete(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)

        companion = service.get_active_companion("p1")
        assert companion is not None
        service._disband(companion, "quest_complete", 30)

        # 확인: 해산됨
        assert service.get_active_companion("p1") is None


# === 이동 동기화 ===


class TestMoveSync:
    def test_sync_companion_move(self, setup) -> None:
        service, db, bus = setup
        events: list = []
        bus.subscribe(EventTypes.COMPANION_MOVED, lambda e: events.append(e))
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        desc = service._sync_companion_move("p1", "2_2")
        assert desc is not None
        assert "npc1" in desc
        assert len(events) == 1

    def test_sync_no_companion(self, setup) -> None:
        service, db, bus = setup
        desc = service._sync_companion_move("p1", "2_2")
        assert desc is None


# === 대화 보정 ===


class TestDialogueBonus:
    def test_bonus_with_companion(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        assert service.get_companion_dialogue_bonus("p1", "npc1") == 2

    def test_no_bonus_without_companion(self, setup) -> None:
        service, db, bus = setup
        assert service.get_companion_dialogue_bonus("p1", "npc1") == 0

    def test_context_with_companion(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        ctx = service.build_companion_context("p1")
        assert ctx is not None
        assert ctx["companion_context"]["is_companion"] is True
        assert ctx["companion_context"]["npc_id"] == "npc1"

    def test_context_without_companion(self, setup) -> None:
        service, db, bus = setup
        assert service.build_companion_context("p1") is None


# === EventBus 핸들러 ===


class TestEventHandlers:
    def test_quest_completed_auto_disband(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)

        assert service.get_active_companion("p1") is not None

        bus.emit(
            GameEvent(
                event_type=EventTypes.QUEST_COMPLETED,
                data={"quest_id": "q1", "current_turn": 20},
                source="test",
            )
        )

        assert service.get_active_companion("p1") is None

    def test_npc_died_force_disband(self, setup) -> None:
        service, db, bus = setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)

        bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_DIED,
                data={"npc_id": "npc1", "current_turn": 15},
                source="test",
            )
        )

        assert service.get_active_companion("p1") is None

    def test_turn_processed_time_limit_expire(self, setup) -> None:
        service, db, bus = setup
        with (
            patch(
                "src.services.companion_service.voluntary_companion_accept",
                return_value=(True, None),
            ),
            patch(
                "src.services.companion_service.roll_condition",
                return_value=(True, "time_limit"),
            ),
            patch(
                "src.services.companion_service.generate_condition_data",
                return_value={"turn_limit": 10},
            ),
        ):
            service.request_voluntary_companion(
                "p1", "npc1", "friend", 50, {"X": 0.5}, "1_1", 10
            )

        assert service.get_active_companion("p1") is not None

        # Turn 20: started_turn=10, turn_limit=10 → expired (20-10 >= 10)
        bus.emit(
            GameEvent(
                event_type=EventTypes.TURN_PROCESSED,
                data={
                    "player_id": "p1",
                    "turn_number": 20,
                    "pc_node": "1_1",
                    "node_danger": 0.0,
                },
                source="test",
            )
        )

        assert service.get_active_companion("p1") is None
