"""Companion API 엔드포인트 테스트 (#13-C-8)

recruit/dismiss 액션 테스트. 최소 5개 케이스.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus
from src.db.models import Base
from src.services.companion_service import CompanionService


@pytest.fixture()
def companion_setup():
    """인메모리 DB + CompanionService"""
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


class TestRecruitAPI:
    def test_recruit_success(self, companion_setup) -> None:
        service, db, bus = companion_setup
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
        assert state is not None

    def test_recruit_rejected_relationship(self, companion_setup) -> None:
        service, db, bus = companion_setup
        accepted, reason, state = service.request_voluntary_companion(
            "p1", "npc1", "stranger", 0, {"X": 0.5}, "1_1", 10
        )
        assert accepted is False
        assert reason == "insufficient_relationship"

    def test_recruit_already_has_companion(self, companion_setup) -> None:
        service, db, bus = companion_setup
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
            service.request_voluntary_companion(
                "p1", "npc1", "friend", 50, {"X": 0.5}, "1_1", 10
            )
            accepted, reason, state = service.request_voluntary_companion(
                "p1", "npc2", "friend", 50, {"X": 0.5}, "2_2", 11
            )
        assert accepted is False
        assert reason == "already_has_companion"


class TestDismissAPI:
    def test_dismiss_success(self, companion_setup) -> None:
        service, db, bus = companion_setup
        with patch(
            "src.services.companion_service.roll_quest_companion", return_value=True
        ):
            service.request_quest_companion("p1", "npc1", "q1", 0.5, False, "1_1", 10)
        result = service.dismiss_companion("p1", 20)
        assert result is not None
        assert result.npc_id == "npc1"
        assert service.get_active_companion("p1") is None

    def test_dismiss_no_companion(self, companion_setup) -> None:
        service, db, bus = companion_setup
        result = service.dismiss_companion("p1", 20)
        assert result is None
