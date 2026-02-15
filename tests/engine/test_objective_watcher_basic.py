"""ObjectiveWatcher 기본 테스트 — reach_node, talk_to_npc, resolve_check

in-memory EventBus + mock quest_service.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.engine.objective_watcher import ObjectiveWatcher


# === Mock Objective ===


@dataclass
class MockObjective:
    """테스트용 Objective"""

    objective_id: str
    quest_id: str
    objective_type: str
    target: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: str = "active"


# === Mock QuestService ===


class MockQuestService:
    """테스트용 QuestService — get_active_objectives_by_type() 제공"""

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


# === Fixtures ===


@pytest.fixture()
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def quest_service() -> MockQuestService:
    return MockQuestService()


@pytest.fixture()
def watcher(event_bus: EventBus, quest_service: MockQuestService) -> ObjectiveWatcher:
    return ObjectiveWatcher(
        event_bus=event_bus,
        quest_service=quest_service,
    )


@pytest.fixture()
def collected_events(event_bus: EventBus) -> list[GameEvent]:
    """발행된 objective_completed / objective_failed 이벤트를 수집."""
    events: list[GameEvent] = []

    def _collect_completed(e: GameEvent) -> None:
        events.append(e)

    def _collect_failed(e: GameEvent) -> None:
        events.append(e)

    event_bus.subscribe(EventTypes.OBJECTIVE_COMPLETED, _collect_completed)
    event_bus.subscribe(EventTypes.OBJECTIVE_FAILED, _collect_failed)
    return events


# === reach_node 테스트 ===


class TestReachNode:
    """reach_node 달성 판정 테스트"""

    def test_player_moved_node_match_completes(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """1. player_moved -> node 매칭 -> objective_completed 발행"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_1",
                quest_id="quest_1",
                objective_type="reach_node",
                target={"node_id": "5_3"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "4_3",
                    "to_node": "5_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].event_type == EventTypes.OBJECTIVE_COMPLETED
        assert collected_events[0].data["objective_id"] == "obj_1"
        assert collected_events[0].data["trigger_action"] == "move"

    def test_player_moved_node_mismatch_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """2. player_moved -> node 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_1",
                quest_id="quest_1",
                objective_type="reach_node",
                target={"node_id": "5_3"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "4_3",
                    "to_node": "6_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_player_moved_require_action_not_completed(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """3. player_moved -> require_action 있음 -> 도착만으로 미달성"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_1",
                quest_id="quest_1",
                objective_type="reach_node",
                target={"node_id": "5_3", "require_action": "investigate"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "4_3",
                    "to_node": "5_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_action_completed_require_action_match(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """4. action_completed -> require_action 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_1",
                quest_id="quest_1",
                objective_type="reach_node",
                target={"node_id": "5_3", "require_action": "investigate"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ACTION_COMPLETED,
                data={
                    "player_id": "p1",
                    "action_type": "investigate",
                    "node_id": "5_3",
                    "result_data": {},
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_1"
        assert collected_events[0].data["trigger_action"] == "investigate"

    def test_action_completed_action_type_mismatch(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """5. action_completed -> action_type 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_1",
                quest_id="quest_1",
                objective_type="reach_node",
                target={"node_id": "5_3", "require_action": "investigate"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ACTION_COMPLETED,
                data={
                    "player_id": "p1",
                    "action_type": "look",
                    "node_id": "5_3",
                    "result_data": {},
                },
                source="test",
            )
        )

        assert len(collected_events) == 0


# === talk_to_npc 테스트 ===


class TestTalkToNpc:
    """talk_to_npc 달성 판정 테스트"""

    def test_dialogue_started_simple_contact_match(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """6. dialogue_started -> 단순 접촉 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={"npc_id": "npc_fritz_043"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={"npc_id": "npc_fritz_043"},
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_2"
        assert collected_events[0].data["trigger_action"] == "talk"

    def test_dialogue_started_npc_mismatch_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """7. dialogue_started -> npc 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={"npc_id": "npc_fritz_043"},
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={"npc_id": "npc_hans_042"},
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_dialogue_started_require_topic_not_processed(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """8. dialogue_started -> require_topic 있음 -> 미처리 (dialogue_ended 대기)"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={
                    "npc_id": "npc_fritz_043",
                    "require_topic": "dispute_resolution",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={"npc_id": "npc_fritz_043"},
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_dialogue_ended_topic_match(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """9. dialogue_ended -> 주제 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={
                    "npc_id": "npc_merchant_012",
                    "require_topic": "dispute_resolution",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_ENDED,
                data={
                    "npc_id": "npc_merchant_012",
                    "topic_tags": ["trade", "dispute_resolution"],
                    "memory_tags": [],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_2"

    def test_dialogue_ended_topic_mismatch_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """10. dialogue_ended -> 주제 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={
                    "npc_id": "npc_merchant_012",
                    "require_topic": "dispute_resolution",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_ENDED,
                data={
                    "npc_id": "npc_merchant_012",
                    "topic_tags": ["trade", "weather"],
                    "memory_tags": ["greeting"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_dialogue_ended_topic_in_memory_tags(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """9b. dialogue_ended -> memory_tags에 주제 포함 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_2b",
                quest_id="quest_2",
                objective_type="talk_to_npc",
                target={
                    "npc_id": "npc_merchant_012",
                    "require_topic": "dispute_resolution",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_ENDED,
                data={
                    "npc_id": "npc_merchant_012",
                    "topic_tags": ["trade"],
                    "memory_tags": ["dispute_resolution"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_2b"


# === resolve_check 테스트 ===


class TestResolveCheck:
    """resolve_check 달성 판정 테스트"""

    def test_check_result_full_match_completes(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """11. check_result -> 등급+스탯+컨텍스트 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "check_type": "EXEC",
                    "context_tag": "bridge_repair",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "success",
                    "stat": "EXEC",
                    "context_tags": ["bridge_repair"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_3"
        assert collected_events[0].data["trigger_action"] == "check"

    def test_check_result_tier_insufficient_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """12. check_result -> 등급 미달 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "check_type": "EXEC",
                    "context_tag": "bridge_repair",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "partial",
                    "stat": "EXEC",
                    "context_tags": ["bridge_repair"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_check_result_stat_mismatch_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """13. check_result -> 스탯 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "check_type": "EXEC",
                    "context_tag": "bridge_repair",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "success",
                    "stat": "READ",
                    "context_tags": ["bridge_repair"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_check_result_context_mismatch_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """14. check_result -> 컨텍스트 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "check_type": "EXEC",
                    "context_tag": "bridge_repair",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "success",
                    "stat": "EXEC",
                    "context_tags": ["combat_bandit"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_check_result_no_check_type_any_stat(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """15. check_result -> check_type None (어떤 스탯이든) -> 등급만 확인"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "success",
                    "context_tag": "bridge_repair",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "critical",
                    "stat": "SUDO",
                    "context_tags": ["bridge_repair"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_3"

    def test_check_result_no_context_tag_tier_and_stat_only(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """16. check_result -> context_tag None -> 등급+스탯만 확인"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_3",
                quest_id="quest_3",
                objective_type="resolve_check",
                target={
                    "min_result_tier": "partial",
                    "check_type": "WRITE",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.CHECK_RESULT,
                data={
                    "result_tier": "success",
                    "stat": "WRITE",
                    "context_tags": [],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_3"
