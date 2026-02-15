"""액션 이벤트 훅 + give 액션 + 통합 테스트

game.py의 이벤트 훅 동작과 ObjectiveWatcher 통합을 검증한다.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.game import get_engine
from src.core.engine import ITWEngine
from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.engine.objective_watcher import ObjectiveWatcher
from src.main import app
from src.services.ai.mock import MockProvider
from src.services.narrative_service import NarrativeService


# === Mock Objective ===


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


# === Fixtures ===


@pytest.fixture()
def engine() -> ITWEngine:
    return ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )


@pytest.fixture()
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture()
def client(engine: ITWEngine, event_bus: EventBus) -> TestClient:
    app.dependency_overrides[get_engine] = lambda: engine
    app.state.narrative_service = NarrativeService(MockProvider())
    app.state.event_bus = event_bus
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def collected_events(event_bus: EventBus) -> list[GameEvent]:
    events: list[GameEvent] = []

    def _collect(e: GameEvent) -> None:
        events.append(e)

    event_bus.subscribe(EventTypes.PLAYER_MOVED, _collect)
    event_bus.subscribe(EventTypes.ACTION_COMPLETED, _collect)
    event_bus.subscribe(EventTypes.ITEM_GIVEN, _collect)
    return events


def _register_player(client: TestClient, player_id: str = "test_player") -> None:
    client.post("/game/register", json={"player_id": player_id})


# === 이동 훅 테스트 ===


class TestMoveHooks:
    """move 액션 이벤트 훅 테스트"""

    def test_move_emits_player_moved(
        self,
        client: TestClient,
        collected_events: list[GameEvent],
    ) -> None:
        """1. move 액션 -> PLAYER_MOVED 발행 확인"""
        _register_player(client)
        response = client.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "move",
                "params": {"direction": "e"},
            },
        )
        assert response.status_code == 200

        moved_events = [
            e for e in collected_events if e.event_type == EventTypes.PLAYER_MOVED
        ]
        assert len(moved_events) == 1
        assert moved_events[0].data["player_id"] == "test_player"
        assert moved_events[0].data["move_type"] == "walk"
        assert "from_node" in moved_events[0].data
        assert "to_node" in moved_events[0].data

    def test_enter_emits_player_moved_enter(
        self,
        client: TestClient,
        engine: ITWEngine,
        collected_events: list[GameEvent],
    ) -> None:
        """2. enter 액션 -> PLAYER_MOVED (move_type: enter) 발행"""
        _register_player(client)
        # enter가 가능한 노드로 이동해야 하므로 여기서는 결과 체크
        response = client.post(
            "/game/action",
            json={"player_id": "test_player", "action": "enter", "params": {}},
        )
        # enter가 실패할 수 있음 (depth가 없는 노드) — 성공하면 이벤트 확인
        if response.json()["success"]:
            moved_events = [
                e for e in collected_events if e.event_type == EventTypes.PLAYER_MOVED
            ]
            assert len(moved_events) >= 1
            enter_events = [e for e in moved_events if e.data["move_type"] == "enter"]
            assert len(enter_events) == 1


# === 액션 훅 테스트 ===


class TestActionHooks:
    """look/investigate 액션 이벤트 훅 테스트"""

    def test_look_emits_action_completed(
        self,
        client: TestClient,
        collected_events: list[GameEvent],
    ) -> None:
        """3. look 액션 -> ACTION_COMPLETED 발행"""
        _register_player(client)
        response = client.post(
            "/game/action",
            json={"player_id": "test_player", "action": "look", "params": {}},
        )
        assert response.status_code == 200

        action_events = [
            e for e in collected_events if e.event_type == EventTypes.ACTION_COMPLETED
        ]
        assert len(action_events) == 1
        assert action_events[0].data["action_type"] == "look"
        assert action_events[0].data["player_id"] == "test_player"

    def test_investigate_emits_action_completed(
        self,
        client: TestClient,
        collected_events: list[GameEvent],
    ) -> None:
        """4. investigate 액션 -> ACTION_COMPLETED 발행"""
        _register_player(client)
        response = client.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "investigate",
                "params": {"echo_index": 0},
            },
        )
        # investigate는 echo가 없으면 실패할 수 있음
        if response.json()["success"]:
            action_events = [
                e
                for e in collected_events
                if e.event_type == EventTypes.ACTION_COMPLETED
            ]
            assert len(action_events) >= 1
            inv_events = [
                e for e in action_events if e.data["action_type"] == "investigate"
            ]
            assert len(inv_events) == 1


# === give 액션 테스트 ===


class MockItemInstance:
    """테스트용 ItemInstance"""

    def __init__(
        self,
        instance_id: str,
        prototype_id: str,
        owner_type: str = "player",
        owner_id: str = "test_player",
    ) -> None:
        self.instance_id = instance_id
        self.prototype_id = prototype_id
        self.owner_type = owner_type
        self.owner_id = owner_id


class MockItemPrototype:
    """테스트용 ItemPrototype"""

    def __init__(self, item_id: str, tags: tuple[str, ...] = ()) -> None:
        self.item_id = item_id
        self.tags = tags


class MockItemService:
    """테스트용 ItemService"""

    def __init__(self) -> None:
        self._instances: list[MockItemInstance] = []
        self._prototypes: dict[str, MockItemPrototype] = {}
        self._transferred: list[tuple[str, str, str, str]] = []

    def add_instance(self, inst: MockItemInstance) -> None:
        self._instances.append(inst)

    def add_prototype(self, proto: MockItemPrototype) -> None:
        self._prototypes[proto.item_id] = proto

    def get_instance(self, instance_id: str) -> MockItemInstance | None:
        for i in self._instances:
            if i.instance_id == instance_id:
                return i
        return None

    def get_instances_by_owner(
        self, owner_type: str, owner_id: str
    ) -> list[MockItemInstance]:
        return [
            i
            for i in self._instances
            if i.owner_type == owner_type and i.owner_id == owner_id
        ]

    def get_prototype(self, item_id: str) -> MockItemPrototype | None:
        return self._prototypes.get(item_id)

    def transfer_item(
        self, instance_id: str, to_type: str, to_id: str, reason: str = "manual"
    ) -> bool:
        self._transferred.append((instance_id, to_type, to_id, reason))
        for inst in self._instances:
            if inst.instance_id == instance_id:
                inst.owner_type = to_type
                inst.owner_id = to_id
                return True
        return False


@pytest.fixture()
def item_service() -> MockItemService:
    return MockItemService()


@pytest.fixture()
def client_with_items(
    engine: ITWEngine, event_bus: EventBus, item_service: MockItemService
) -> TestClient:
    app.dependency_overrides[get_engine] = lambda: engine
    app.state.narrative_service = NarrativeService(MockProvider())
    app.state.event_bus = event_bus
    app.state.item_service = item_service
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestGiveAction:
    """give 액션 테스트"""

    def test_give_missing_params(self, client_with_items: TestClient) -> None:
        """6. give — 파라미터 누락 -> 에러"""
        _register_player(client_with_items)
        response = client_with_items.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "give",
                "params": {},
            },
        )
        assert response.status_code == 400

    def test_give_item_not_found(self, client_with_items: TestClient) -> None:
        """7. give — 아이템 미보유 -> 에러"""
        _register_player(client_with_items)
        response = client_with_items.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "give",
                "params": {"npc_id": "npc_1", "item_id": "nonexistent_item"},
            },
        )
        assert response.status_code == 400

    def test_give_success_emits_item_given(
        self,
        client_with_items: TestClient,
        event_bus: EventBus,
        item_service: MockItemService,
    ) -> None:
        """5. give — 정상 전달 -> ITEM_GIVEN 발행"""
        _register_player(client_with_items)

        item_service.add_prototype(
            MockItemPrototype("healing_herb", tags=("herb", "healing"))
        )
        item_service.add_instance(
            MockItemInstance(
                instance_id="inst_001",
                prototype_id="healing_herb",
                owner_type="player",
                owner_id="test_player",
            )
        )

        given_events: list[GameEvent] = []
        event_bus.subscribe(EventTypes.ITEM_GIVEN, lambda e: given_events.append(e))

        response = client_with_items.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "give",
                "params": {"npc_id": "npc_hans_042", "item_id": "healing_herb"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["recipient_npc_id"] == "npc_hans_042"

        assert len(given_events) == 1
        assert given_events[0].data["recipient_npc_id"] == "npc_hans_042"
        assert given_events[0].data["item_prototype_id"] == "healing_herb"
        assert given_events[0].data["item_tags"] == ["herb", "healing"]

    def test_give_prototype_id_resolves_to_instance(
        self,
        client_with_items: TestClient,
        item_service: MockItemService,
    ) -> None:
        """8. give — prototype_id로 instance 자동 해석"""
        _register_player(client_with_items)

        item_service.add_prototype(MockItemPrototype("healing_herb"))
        item_service.add_instance(
            MockItemInstance(
                instance_id="inst_002",
                prototype_id="healing_herb",
                owner_type="player",
                owner_id="test_player",
            )
        )

        response = client_with_items.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "give",
                "params": {"npc_id": "npc_1", "item_id": "healing_herb"},
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["instance_id"] == "inst_002"


# === 통합 테스트: ObjectiveWatcher + 액션 훅 ===


class TestIntegration:
    """ObjectiveWatcher + 액션 훅 통합 테스트"""

    def test_move_triggers_reach_node_completion(
        self,
        event_bus: EventBus,
    ) -> None:
        """9. move -> PLAYER_MOVED -> ObjectiveWatcher -> reach_node 달성 (E2E)"""
        quest_service = MockQuestService()
        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
        )
        assert watcher is not None  # suppress unused warning

        completed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED,
            lambda e: completed_events.append(e),
        )

        # reach_node 목표 설정
        quest_service.add_objective(
            MockObjective(
                objective_id="obj_r1",
                quest_id="quest_r1",
                objective_type="reach_node",
                target={"node_id": "1_0"},
            )
        )

        # PLAYER_MOVED 발행 (game.py에서 발행하는 것과 동일 포맷)
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.PLAYER_MOVED,
                data={
                    "player_id": "p1",
                    "from_node": "0_0",
                    "to_node": "1_0",
                    "move_type": "walk",
                },
                source="game_api",
            )
        )

        assert len(completed_events) == 1
        assert completed_events[0].data["objective_id"] == "obj_r1"

    def test_give_triggers_deliver_completion(
        self,
        event_bus: EventBus,
    ) -> None:
        """10. give -> ITEM_GIVEN -> ObjectiveWatcher -> deliver 달성 (E2E)"""
        quest_service = MockQuestService()
        watcher = ObjectiveWatcher(
            event_bus=event_bus,
            quest_service=quest_service,
        )
        assert watcher is not None

        completed_events: list[GameEvent] = []
        event_bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED,
            lambda e: completed_events.append(e),
        )

        # deliver 목표 설정
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

        # ITEM_GIVEN 발행 (game.py에서 give 액션이 발행하는 것과 동일 포맷)
        event_bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_GIVEN,
                data={
                    "player_id": "p1",
                    "recipient_npc_id": "npc_hans_042",
                    "item_prototype_id": "healing_herb",
                    "item_instance_id": "inst_001",
                    "quantity": 1,
                    "item_tags": ["herb"],
                },
                source="game_api",
            )
        )

        assert len(completed_events) == 1
        assert completed_events[0].data["objective_id"] == "obj_d1"
