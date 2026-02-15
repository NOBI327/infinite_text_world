"""Quest API 엔드포인트 테스트 (#12-D)"""

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus
from src.db.models import Base
from src.db.models_v2 import (
    NPCModel,
    QuestModel,
    QuestObjectiveModel,
)
from src.services.quest_service import QuestService


@pytest.fixture()
def quest_setup():
    """인메모리 DB + QuestService"""
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

    # 테스트용 NPC
    db.add(
        NPCModel(
            npc_id="npc_001",
            full_name="Test NPC",
            given_name="Test",
            hexaco="{}",
            character_sheet="{}",
            resonance_shield="{}",
            current_node="node_001",
            origin_type="promoted",
            role="merchant",
            tags="[]",
        )
    )
    db.commit()

    service = QuestService(db, bus)
    return service, db, bus


def _add_quest(db, quest_id="q_001", status="active"):
    db.add(
        QuestModel(
            quest_id=quest_id,
            title="테스트 퀘스트",
            description="설명",
            origin_type="conversation",
            origin_npc_id="npc_001",
            quest_type="deliver",
            seed_tier=3,
            status=status,
            activated_turn=1,
        )
    )
    db.commit()


def _add_objective(db, quest_id="q_001", objective_id="obj_001"):
    db.add(
        QuestObjectiveModel(
            objective_id=objective_id,
            quest_id=quest_id,
            description="아이템 전달",
            objective_type="deliver",
            status="active",
        )
    )
    db.commit()


class TestQuestListAPI:
    """quest_list 액션 테스트"""

    def test_quest_list_empty(self, quest_setup):
        service, db, bus = quest_setup
        active = service.get_active_quests()
        assert len(active) == 0

    def test_quest_list_with_quests(self, quest_setup):
        service, db, bus = quest_setup
        _add_quest(db)
        active = service.get_active_quests()
        assert len(active) == 1
        assert active[0].title == "테스트 퀘스트"


class TestQuestDetailAPI:
    """quest_detail 액션 테스트"""

    def test_quest_detail_with_objectives(self, quest_setup):
        service, db, bus = quest_setup
        _add_quest(db)
        _add_objective(db)

        quest = service.get_quest("q_001")
        assert quest is not None
        assert quest.title == "테스트 퀘스트"

        objectives = service.get_quest_objectives("q_001")
        assert len(objectives) == 1
        assert objectives[0].objective_type == "deliver"

    def test_quest_detail_not_found(self, quest_setup):
        service, db, bus = quest_setup
        quest = service.get_quest("nonexistent")
        assert quest is None


class TestQuestAbandonAPI:
    """quest_abandon 액션 테스트"""

    def test_abandon_success(self, quest_setup):
        service, db, bus = quest_setup
        _add_quest(db)

        result = service.abandon_quest("q_001", current_turn=10)
        assert result is True

        quest = service.get_quest("q_001")
        assert quest is not None
        assert quest.status == "abandoned"

    def test_abandon_already_completed(self, quest_setup):
        service, db, bus = quest_setup
        _add_quest(db, status="completed")

        result = service.abandon_quest("q_001", current_turn=10)
        assert result is False
