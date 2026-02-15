"""ObjectiveWatcher deliver + escort 테스트

in-memory EventBus + mock quest_service + mock companion_service.
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


# === Mock Services ===


class MockQuestService:
    """테스트용 QuestService"""

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
    """테스트용 CompanionService — is_companion() 제공"""

    def __init__(self) -> None:
        self._companions: dict[str, str] = {}  # player_id -> npc_id

    def set_companion(self, player_id: str, npc_id: str) -> None:
        self._companions[player_id] = npc_id

    def clear_companion(self, player_id: str) -> None:
        self._companions.pop(player_id, None)

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


@pytest.fixture()
def watcher(
    event_bus: EventBus,
    quest_service: MockQuestService,
    companion_service: MockCompanionService,
) -> ObjectiveWatcher:
    return ObjectiveWatcher(
        event_bus=event_bus,
        quest_service=quest_service,
        companion_service=companion_service,
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


# === deliver 테스트 ===


class TestDeliver:
    """deliver 달성 판정 테스트"""

    def test_item_given_recipient_and_prototype_match(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """1. item_given -> recipient + prototype_id 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d1",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "item_instance_id": "inst_001",
                    "quantity": 1,
                    "item_tags": ["herb", "healing"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].event_type == EventTypes.OBJECTIVE_COMPLETED
        assert collected_events[0].data["objective_id"] == "obj_d1"
        assert collected_events[0].data["trigger_action"] == "give"

    def test_item_given_recipient_mismatch(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """2. item_given -> recipient 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d1",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_other_099",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_item_given_prototype_mismatch(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """3. item_given -> item_prototype_id 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d1",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "poison_mushroom",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_item_given_tag_match(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """4. item_given -> item_tag 매칭 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d2",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_tag": "herb",
                    "quantity": 1,
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "wild_herb",
                    "quantity": 1,
                    "item_tags": ["herb", "wild"],
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_d2"

    def test_item_given_quantity_insufficient(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """5. item_given -> 수량 부족 (1/3) -> 미완료"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d3",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 3,
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_item_given_cumulative_quantity_fulfilled(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """6. item_given -> 누적 수량 충족 (3/3) -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_d4",
                quest_id="quest_d1",
                objective_type="deliver",
                target={
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 3,
                },
            )
        )

        # 1차 전달 (1/3)
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test_deliver_1",
            )
        )
        assert len(collected_events) == 0

        # EventBus chain reset for next emit
        event_bus.reset_chain()

        # 2차 전달 (2/3)
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test_deliver_2",
            )
        )
        assert len(collected_events) == 0

        event_bus.reset_chain()

        # 3차 전달 (3/3)
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "quantity": 1,
                    "item_tags": [],
                },
                source="test_deliver_3",
            )
        )
        assert len(collected_events) == 1
        assert collected_events[0].data["objective_id"] == "obj_d4"


# === escort 테스트 ===


class TestEscort:
    """escort 달성 판정 테스트"""

    def test_player_moved_destination_match_with_companion(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        companion_service: MockCompanionService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """7. player_moved -> destination 매칭 + 동행 확인 -> objective_completed"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e1",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "7_3",
                },
            )
        )
        companion_service.set_companion("p1", "npc_fritz_043")

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "6_3",
                    "to_node": "7_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].event_type == EventTypes.OBJECTIVE_COMPLETED
        assert collected_events[0].data["objective_id"] == "obj_e1"

    def test_player_moved_destination_match_not_companion(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        companion_service: MockCompanionService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """8. player_moved -> destination 매칭 + 동행 아님 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e1",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "7_3",
                },
            )
        )
        # 동행 설정하지 않음

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "6_3",
                    "to_node": "7_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_player_moved_destination_mismatch(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        companion_service: MockCompanionService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """9. player_moved -> destination 불일치 -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e1",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "7_3",
                },
            )
        )
        companion_service.set_companion("p1", "npc_fritz_043")

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "6_3",
                    "to_node": "8_3",
                    "move_type": "walk",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0


# === escort 실패 테스트 ===


class TestEscortFailure:
    """escort 실패 감지 테스트"""

    def test_npc_died_escort_target_fails(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """10. npc_died -> escort 대상 -> objective_failed (target_dead)"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e2",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "7_3",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_DIED,
                data={
                    "npc_id": "npc_fritz_043",
                    "cause": "bandit_attack",
                },
                source="test",
            )
        )

        assert len(collected_events) == 1
        assert collected_events[0].event_type == EventTypes.OBJECTIVE_FAILED
        assert collected_events[0].data["objective_id"] == "obj_e2"
        assert collected_events[0].data["fail_reason"] == "target_dead"

    def test_npc_died_unrelated_npc_no_action(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """11. npc_died -> escort 무관 NPC -> 무동작"""
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_e2",
                quest_id="quest_e1",
                objective_type="escort",
                target={
                    "target_npc_id": "npc_fritz_043",
                    "destination_node_id": "7_3",
                },
            )
        )

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_DIED,
                data={
                    "npc_id": "npc_random_099",
                    "cause": "natural",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0

    def test_npc_died_no_escort_objectives(
        self,
        event_bus: EventBus,
        quest_service: MockQuestService,
        watcher: ObjectiveWatcher,
        collected_events: list[GameEvent],
    ) -> None:
        """12. npc_died -> escort 목표 없음 -> 무동작"""
        # 아무 목표도 추가하지 않음

        event_bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_DIED,
                data={
                    "npc_id": "npc_fritz_043",
                    "cause": "bandit_attack",
                },
                source="test",
            )
        )

        assert len(collected_events) == 0
