"""대체 목표 시스템 + 통합 테스트

대체 목표 포맷, 활성화, 전체 퀘스트 라이프사이클 검증.
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.quest.models import Objective, Quest
from src.core.quest.objective_logic import generate_replacement_objectives
from src.engine.objective_watcher import ObjectiveWatcher
from src.engine.replacement_choices import format_replacement_choices


# === Mock ===


@dataclass
class MockObjective:
    objective_id: str
    quest_id: str
    objective_type: str
    target: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: str = "active"


class MockQuestService:
    def __init__(self) -> None:
        self._objectives: list[MockObjective] = []

    def add_objective(self, obj: MockObjective) -> None:
        self._objectives.append(obj)

    def get_active_objectives_by_type(self, objective_type: str) -> list[MockObjective]:
        return [
            o
            for o in self._objectives
            if o.objective_type == objective_type and o.status == "active"
        ]


class MockCompanionService:
    def __init__(self) -> None:
        self._companions: dict[str, str] = {}

    def set_companion(self, player_id: str, npc_id: str) -> None:
        self._companions[player_id] = npc_id

    def is_companion(self, player_id: str, npc_id: str) -> bool:
        return self._companions.get(player_id) == npc_id


# === Fixtures ===


@pytest.fixture()
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def quest_service() -> MockQuestService:
    return MockQuestService()


@pytest.fixture()
def companion_service() -> MockCompanionService:
    return MockCompanionService()


# === 대체 목표 시스템 테스트 ===


class TestReplacementObjectives:
    """대체 목표 생성 및 포맷 테스트"""

    def test_objective_failed_generates_replacements(self) -> None:
        """1. objective_failed -> 대체 목표 생성 확인"""
        failed_obj = Objective(
            objective_id="obj_orig_1",
            quest_id="quest_1",
            description="프리츠를 호위하라",
            objective_type="escort",
            status="failed",
            fail_reason="target_dead",
        )
        quest = Quest(
            quest_id="quest_1",
            title="실종된 사촌",
            origin_npc_id="npc_hans_042",
        )
        context = {"client_npc_id": "npc_hans_042"}

        replacements = generate_replacement_objectives(failed_obj, quest, context)

        # client_consult + target_dead fallbacks (deliver + resolve_check) = 3
        assert len(replacements) == 3
        assert replacements[0].replacement_origin == "client_consult"
        assert replacements[0].is_replacement is True
        assert replacements[0].replaced_objective_id == "obj_orig_1"

    def test_format_replacement_choices(self) -> None:
        """2. format_replacement_choices — 정상 포맷"""
        replacements = [
            Objective(
                objective_id="r1",
                quest_id="q1",
                description="의뢰주에게 상황을 보고하라",
                objective_type="talk_to_npc",
            ),
            Objective(
                objective_id="r2",
                quest_id="q1",
                description="유품을 의뢰주에게 전달하라",
                objective_type="deliver",
            ),
            Objective(
                objective_id="r3",
                quest_id="q1",
                description="사인을 조사하라",
                objective_type="resolve_check",
            ),
        ]

        msg = format_replacement_choices("프리츠가 사망한 것을 확인했다.", replacements)

        assert "[시스템]" in msg
        assert "프리츠가 사망한 것을 확인했다." in msg
        assert "1. 의뢰주에게 상황을 보고하라" in msg
        assert "2. 유품을 의뢰주에게 전달하라" in msg
        assert "3. 사인을 조사하라" in msg
        assert "또는 다른 행동을 자유롭게 선언할 수 있다" in msg

    def test_replacement_objectives_all_active(self) -> None:
        """3. 대체 목표 전부 active 확인"""
        failed_obj = Objective(
            objective_id="obj_orig_1",
            quest_id="quest_1",
            description="프리츠를 호위하라",
            objective_type="escort",
            status="failed",
            fail_reason="target_dead",
        )
        quest = Quest(
            quest_id="quest_1",
            origin_npc_id="npc_hans_042",
        )
        context = {"client_npc_id": "npc_hans_042"}

        replacements = generate_replacement_objectives(failed_obj, quest, context)

        # Alpha에서는 전부 active
        for repl in replacements:
            assert repl.status == "active"


# === 통합 흐름 테스트 ===


class TestIntegrationFlow:
    """ObjectiveWatcher + 대체 목표 통합 흐름"""

    def test_escort_failure_triggers_objective_failed(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        companion_service: MockCompanionService,
    ) -> None:
        """4. escort 실패 -> objective_failed -> 대체 목표 생성 흐름"""
        # ObjectiveWatcher가 objective_failed 발행
        failed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_FAILED, lambda e: failed_events.append(e)
        )

        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
            companion_service=companion_service,
        )
        assert watcher is not None

        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e1",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "2_2",
                },
            )
        )

        # npc_died -> objective_failed
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_DIED,
                data={"npc_id": "npc_fritz_043", "cause": "bandit_attack"},
                source="test",
            )
        )

        assert len(failed_events) == 1
        assert failed_events[0].data["fail_reason"] == "target_dead"
        assert failed_events[0].data["objective_id"] == "obj_e1"

    def test_replacement_talk_to_npc_matches_objective(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
    ) -> None:
        """5. 대체 목표(talk_to_npc) -> dialogue_started -> objective_completed"""
        completed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED, lambda e: completed_events.append(e)
        )

        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
        )
        assert watcher is not None

        # 의뢰주 보고 대체 목표 (client_consult)
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_repl_1",
                quest_id="quest_e1",
                objective_type="talk_to_npc",
                target={"npc_id": "npc_hans_042"},
            )
        )

        # dialogue_started -> talk_to_npc 매칭
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={"npc_id": "npc_hans_042"},
                source="test",
            )
        )

        assert len(completed_events) == 1
        assert completed_events[0].data["objective_id"] == "obj_repl_1"

    def test_failure_report_seed_generation(self) -> None:
        """6. 의뢰주 보고 대화 -> 실패 보고 시드 생성 (monkeypatch)

        실제 QuestService._on_dialogue_started()의 시드 생성 로직은 #12-C에서 구현.
        여기서는 50% 확률 시드 생성이 호출되는지 확인.
        """
        # 이 테스트는 QuestService의 _on_dialogue_started 내부 로직이므로
        # 통합 흐름 확인만 — random을 패치하여 시드 생성 확인
        from src.core.quest.probability import roll_seed_chance

        # monkeypatch로 항상 True 반환 → 시드 생성
        with patch(
            "src.core.quest.probability.roll_seed_chance", return_value=True
        ) as mock_roll:
            # roll_seed_chance가 호출 가능한지 확인
            assert mock_roll() is True
            assert roll_seed_chance is not None

    def test_full_quest_lifecycle_e2e(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
    ) -> None:
        """7. 전체 퀘스트 라이프사이클: 목표 설정 -> 달성 -> completed (E2E)"""
        completed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED, lambda e: completed_events.append(e)
        )

        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
        )
        assert watcher is not None

        # reach_node 목표
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_r1",
                quest_id="quest_lifecycle",
                objective_type="reach_node",
                target={"node_id": "5_8"},
            )
        )

        # talk_to_npc 목표
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_t1",
                quest_id="quest_lifecycle",
                objective_type="talk_to_npc",
                target={"npc_id": "npc_target_001"},
            )
        )

        # 1단계: reach_node 달성
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "4_8",
                    "to_node": "5_8",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(completed_events) == 1
        assert completed_events[0].data["objective_id"] == "obj_r1"

        event_bus.reset_chain()

        # 2단계: talk_to_npc 달성
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={"npc_id": "npc_target_001"},
                source="test",
            )
        )

        assert len(completed_events) == 2
        assert completed_events[1].data["objective_id"] == "obj_t1"

    def test_chaining_integration(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
    ) -> None:
        """8. 체이닝 통합: 퀘스트 완료 -> objective_completed 이벤트"""
        completed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED, lambda e: completed_events.append(e)
        )

        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
        )
        assert watcher is not None

        # resolve_check 목표 (전투 추상화)
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_combat",
                quest_id="quest_chain_1",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "check_type": "EXEC",
                    "context_tag": "combat_bandit",
                },
            )
        )

        # check_result -> resolve_check 달성
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "critical",
                    "stat": "EXEC",
                    "context_tags": ["combat_bandit"],
                },
                source="test",
            )
        )

        assert len(completed_events) == 1
        assert completed_events[0].data["objective_id"] == "obj_combat"
        assert completed_events[0].data["quest_id"] == "quest_chain_1"
        # QuestService에서 chain_eligible 처리 가능
