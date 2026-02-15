"""QuestService 통합 테스트 (인메모리 SQLite + EventBus)

#12-C 검증: 최소 22개 테스트 케이스.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus
from src.core.event_types import EventTypes
from src.core.quest.models import QuestSeed
from src.db.models import Base
from src.db.models_v2 import (
    NPCModel,
    QuestChainEligibleModel,
    QuestModel,
    QuestObjectiveModel,
    QuestSeedModel,
)
from src.services.quest_service import QuestService


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + QuestService"""
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

    # 테스트용 NPC 생성 (FK 제약)
    npc = NPCModel(
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
    db.add(npc)
    db.commit()

    service = QuestService(db, bus)
    return service, db, bus


def _make_seed(npc_id: str = "npc_001", **kwargs) -> QuestSeed:
    defaults = {
        "seed_id": "seed_test_001",
        "npc_id": npc_id,
        "seed_type": "personal",
        "seed_tier": 2,
        "created_turn": 5,
        "ttl_turns": 20,
    }
    defaults.update(kwargs)
    return QuestSeed(**defaults)


def _save_seed_to_db(db, seed: QuestSeed, conv_count: int = 0) -> None:
    db.add(
        QuestSeedModel(
            seed_id=seed.seed_id,
            npc_id=seed.npc_id,
            seed_type=seed.seed_type,
            seed_tier=seed.seed_tier,
            created_turn=seed.created_turn,
            ttl_turns=seed.ttl_turns,
            status=seed.status,
            context_tags="[]",
            chain_id=seed.chain_id,
            unresolved_threads="[]",
            conversation_count_at_creation=conv_count,
        )
    )
    db.commit()


class TestSeedManagement:
    """Seed CRUD 테스트"""

    def test_create_seed_success(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_SEED_CREATED, lambda e: events.append(e))

        with patch(
            "src.core.quest.seed_logic.roll_seed_chance", return_value=True
        ), patch(
            "src.core.quest.seed_logic.determine_seed_tier", return_value=2
        ), patch("src.core.quest.seed_logic.select_seed_type", return_value="rumor"):
            seed = service.create_seed(
                "npc_001", current_turn=10, conversation_count=10
            )

        assert seed is not None
        assert seed.seed_type == "rumor"
        assert len(events) == 1

    def test_create_seed_cooldown_fail(self, setup):
        service, db, bus = setup
        # 먼저 시드 하나 저장 (conv_count=8)
        _save_seed_to_db(db, _make_seed(), conv_count=8)

        seed = service.create_seed("npc_001", current_turn=10, conversation_count=10)
        assert seed is None  # 10 - 8 = 2 < 5

    def test_create_seed_roll_fail(self, setup):
        service, db, bus = setup
        with patch("src.core.quest.seed_logic.roll_seed_chance", return_value=False):
            seed = service.create_seed(
                "npc_001", current_turn=10, conversation_count=10
            )
        assert seed is None

    def test_get_active_seeds_for_npc(self, setup):
        service, db, bus = setup
        _save_seed_to_db(db, _make_seed(seed_id="s1"))
        _save_seed_to_db(db, _make_seed(seed_id="s2"))

        seeds = service.get_active_seeds_for_npc("npc_001")
        assert len(seeds) == 2

    def test_process_all_seed_ttls(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_SEED_EXPIRED, lambda e: events.append(e))

        _save_seed_to_db(db, _make_seed(seed_id="s_exp", created_turn=0, ttl_turns=5))

        expired = service.process_all_seed_ttls(current_turn=10)
        assert len(expired) == 1
        assert expired[0].status == "expired"
        assert len(events) == 1


class TestQuestManagement:
    """Quest 활성화/조회/포기 테스트"""

    def _activate_quest(self, service, db):
        seed = _make_seed()
        _save_seed_to_db(db, seed)
        quest_details = {
            "title": "Test Quest",
            "description": "A test quest",
            "quest_type": "deliver",
            "objectives_hint": [
                {
                    "hint_type": "deliver_item",
                    "description": "아이템 전달",
                    "target": {},
                },
            ],
            "related_npc_ids": ["npc_001"],
        }
        return service.activate_quest(seed, quest_details, current_turn=10)

    def test_activate_quest(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_ACTIVATED, lambda e: events.append(e))

        quest = self._activate_quest(service, db)
        assert quest is not None
        assert quest.title == "Test Quest"
        assert quest.status == "active"
        assert len(events) == 1

    def test_activate_quest_objectives(self, setup):
        service, db, bus = setup
        quest = self._activate_quest(service, db)

        objs = service.get_quest_objectives(quest.quest_id)
        assert len(objs) >= 1
        assert objs[0].objective_type == "deliver"

    def test_get_active_quests(self, setup):
        service, db, bus = setup
        self._activate_quest(service, db)

        active = service.get_active_quests()
        assert len(active) == 1

    def test_abandon_quest(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_ABANDONED, lambda e: events.append(e))

        quest = self._activate_quest(service, db)
        result = service.abandon_quest(quest.quest_id, current_turn=15)
        assert result is True
        assert len(events) == 1

        reloaded = service.get_quest(quest.quest_id)
        assert reloaded is not None
        assert reloaded.status == "abandoned"


class TestResultProcessing:
    """결과 처리 테스트"""

    def _setup_quest_with_objectives(self, service, db, obj_statuses=None):
        seed = _make_seed()
        _save_seed_to_db(db, seed)
        quest_details = {
            "title": "Result Test",
            "quest_type": "deliver",
            "objectives_hint": [
                {"hint_type": "deliver_item", "description": "obj1"},
            ],
        }
        quest = service.activate_quest(seed, quest_details, current_turn=5)

        if obj_statuses:
            objs = service.get_quest_objectives(quest.quest_id)
            for obj, status in zip(objs, obj_statuses):
                orm = db.get(QuestObjectiveModel, obj.objective_id)
                if orm is not None:
                    orm.status = status
                    if status == "completed":
                        orm.completed_turn = 10
            db.commit()

        return quest

    def test_check_completion_success(self, setup):
        service, db, bus = setup
        quest = self._setup_quest_with_objectives(service, db, ["completed"])

        result = service.check_quest_completion(quest.quest_id, 10)
        assert result == "success"

    def test_check_completion_partial(self, setup):
        service, db, bus = setup
        seed = _make_seed()
        _save_seed_to_db(db, seed)
        quest_details = {
            "title": "Partial Test",
            "quest_type": "deliver",
            "objectives_hint": [
                {"hint_type": "deliver_item", "description": "obj1"},
            ],
        }
        quest = service.activate_quest(seed, quest_details, current_turn=5)
        objs = service.get_quest_objectives(quest.quest_id)

        # 원본 목표 실패
        orm = db.get(QuestObjectiveModel, objs[0].objective_id)
        if orm is not None:
            orm.status = "failed"
            orm.fail_reason = "target_dead"

        # 대체 목표 추가 + 달성
        repl_orm = QuestObjectiveModel(
            objective_id="repl_001",
            quest_id=quest.quest_id,
            description="대체 목표",
            objective_type="deliver",
            status="completed",
            completed_turn=10,
            is_replacement=True,
            replaced_objective_id=objs[0].objective_id,
            replacement_origin="auto_fallback",
        )
        db.add(repl_orm)
        db.commit()

        result = service.check_quest_completion(quest.quest_id, 10)
        assert result == "partial"

    def test_check_completion_in_progress(self, setup):
        service, db, bus = setup
        quest = self._setup_quest_with_objectives(service, db)
        # objectives still active
        result = service.check_quest_completion(quest.quest_id, 8)
        assert result is None

    def test_complete_objective_triggers_completion(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_COMPLETED, lambda e: events.append(e))

        quest = self._setup_quest_with_objectives(service, db)
        objs = service.get_quest_objectives(quest.quest_id)

        service.complete_objective(
            objs[0].objective_id, current_turn=10, trigger_data={}
        )

        assert len(events) == 1
        assert events[0].data["result"] == "success"

    def test_fail_objective_generates_replacements(self, setup):
        service, db, bus = setup
        quest = self._setup_quest_with_objectives(service, db)
        objs = service.get_quest_objectives(quest.quest_id)

        replacements = service.fail_objective(
            objs[0].objective_id,
            current_turn=10,
            fail_reason="target_dead",
            trigger_data={},
        )
        assert len(replacements) >= 1
        assert replacements[0].is_replacement is True


class TestChaining:
    """체이닝 테스트"""

    def test_find_quests_with_eligible_npc(self, setup):
        service, db, bus = setup
        # 완료 퀘스트 직접 생성
        db.add(
            QuestModel(
                quest_id="q_done",
                title="Done",
                description="",
                origin_type="conversation",
                quest_type="deliver",
                seed_tier=2,
                status="completed",
                result="success",
                activated_turn=1,
                completed_turn=5,
            )
        )
        db.flush()
        db.add(
            QuestChainEligibleModel(
                quest_id="q_done",
                npc_ref="npc_001",
                ref_type="existing",
                reason="quest_giver",
            )
        )
        db.commit()

        found = service.find_quests_with_eligible_npc("npc_001")
        assert len(found) == 1
        assert found[0].quest_id == "q_done"

    def test_finalize_quest_chain(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.QUEST_CHAIN_FORMED, lambda e: events.append(e))

        seed = _make_seed(chain_id="chain_001")
        _save_seed_to_db(db, seed)
        quest_details = {
            "title": "Chain Quest",
            "quest_type": "investigate",
            "objectives_hint": [
                {"hint_type": "investigate_area", "description": "조사"}
            ],
            "related_npc_ids": ["npc_001"],
            "tags": ["mystery"],
        }
        quest = service.activate_quest(seed, quest_details, current_turn=5)

        # 목표 달성
        objs = service.get_quest_objectives(quest.quest_id)
        for obj in objs:
            orm = db.get(QuestObjectiveModel, obj.objective_id)
            if orm is not None:
                orm.status = "completed"
                orm.completed_turn = 10
        db.commit()

        with patch(
            "src.services.quest_service.should_finalize_chain", return_value=False
        ):
            service.check_quest_completion(quest.quest_id, 10)

        # chain_formed 이벤트 확인
        chain_events = [
            e for e in events if e.event_type == EventTypes.QUEST_CHAIN_FORMED
        ]
        assert len(chain_events) >= 1

    def test_scan_unborn_eligible(self, setup):
        service, db, bus = setup
        events = []
        bus.subscribe(EventTypes.CHAIN_ELIGIBLE_MATCHED, lambda e: events.append(e))

        db.add(
            QuestModel(
                quest_id="q_unborn",
                title="Unborn",
                description="",
                origin_type="conversation",
                quest_type="investigate",
                seed_tier=1,
                status="completed",
                activated_turn=1,
            )
        )
        db.flush()
        db.add(
            QuestChainEligibleModel(
                quest_id="q_unborn",
                npc_ref="blacksmith",
                ref_type="unborn",
                reason="foreshadowed",
            )
        )
        db.commit()

        service.scan_unborn_eligible("new_npc", ["blacksmith", "craftsman"], "node_001")
        assert len(events) == 1


class TestTimeLimit:
    """시간 제한 테스트"""

    def test_check_urgent_time_limits(self, setup):
        service, db, bus = setup
        db.add(
            QuestModel(
                quest_id="q_urgent",
                title="Urgent",
                description="",
                origin_type="conversation",
                quest_type="escort",
                seed_tier=3,
                status="active",
                urgency="urgent",
                time_limit=5,
                activated_turn=1,
            )
        )
        db.add(
            QuestObjectiveModel(
                objective_id="obj_urg",
                quest_id="q_urgent",
                description="호위",
                objective_type="escort",
                status="active",
            )
        )
        db.commit()

        timed_out = service.check_urgent_time_limits(current_turn=10)
        assert len(timed_out) == 1


class TestContext:
    """LLM 컨텍스트 테스트"""

    def test_build_dialogue_quest_context_with_seed(self, setup):
        service, db, bus = setup
        _save_seed_to_db(db, _make_seed())

        ctx = service.build_dialogue_quest_context("npc_001", current_turn=10)
        assert ctx is not None
        assert "quest_seed" in ctx

    def test_build_dialogue_quest_context_expired(self, setup):
        service, db, bus = setup
        seed = _make_seed(status="expired", expiry_result="victim_found_dead")
        db.add(
            QuestSeedModel(
                seed_id=seed.seed_id,
                npc_id=seed.npc_id,
                seed_type=seed.seed_type,
                seed_tier=seed.seed_tier,
                created_turn=seed.created_turn,
                ttl_turns=seed.ttl_turns,
                status="expired",
                context_tags="[]",
                expiry_result="victim_found_dead",
                unresolved_threads="[]",
                conversation_count_at_creation=0,
            )
        )
        db.commit()

        ctx = service.build_dialogue_quest_context("npc_001", current_turn=30)
        assert ctx is not None
        assert "expired_seed" in ctx

    def test_build_quest_activation_context(self, setup):
        service, db, bus = setup
        seed = _make_seed()
        ctx = service.build_quest_activation_context(
            seed, npc_personality={"H": 0.7}, relationship_status="acquaintance"
        )
        assert "quest_generation" in ctx

    def test_get_pc_tendency(self, setup):
        service, db, bus = setup
        db.add(
            QuestModel(
                quest_id="q_done2",
                title="Done",
                description="",
                origin_type="conversation",
                quest_type="deliver",
                seed_tier=2,
                status="completed",
                result="success",
                activated_turn=1,
                completed_turn=5,
                resolution_method_tag="negotiation",
                resolution_impression_tag="impressed",
            )
        )
        db.commit()

        tendency = service.get_pc_tendency()
        assert tendency["dominant_style"] == "diplomat"
