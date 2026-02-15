"""QuestModule 테스트 (#12-D)"""

from unittest.mock import MagicMock

from src.core.quest.models import Quest
from src.modules.base import GameContext
from src.modules.quest.module import QuestModule


def _make_service_mock():
    service = MagicMock()
    service.get_active_quests.return_value = []
    return service


def _make_context(node_id: str = "node_001") -> GameContext:
    return GameContext(
        player_id="p1",
        current_node_id=node_id,
        current_turn=10,
        extra={},
    )


class TestQuestModule:
    """QuestModule 테스트"""

    def test_module_creation_and_dependencies(self):
        service = _make_service_mock()
        module = QuestModule(service)
        assert module.name == "quest"
        assert "npc_core" in module.dependencies
        assert "relationship" in module.dependencies
        assert "dialogue" in module.dependencies

    def test_get_available_actions(self):
        service = _make_service_mock()
        module = QuestModule(service)
        ctx = _make_context()
        actions = module.get_available_actions(ctx)
        assert len(actions) == 3
        names = {a.name for a in actions}
        assert names == {"quest_list", "quest_detail", "quest_abandon"}

    def test_on_node_enter_sets_context(self):
        service = _make_service_mock()
        service.get_active_quests.return_value = [
            Quest(
                quest_id="q1",
                title="Test",
                quest_type="deliver",
                target_node_ids=["node_001"],
            ),
            Quest(
                quest_id="q2",
                title="Other",
                quest_type="escort",
                target_node_ids=["node_002"],
            ),
        ]
        module = QuestModule(service)
        ctx = _make_context("node_001")
        module.on_node_enter("node_001", ctx)

        assert "quest" in ctx.extra
        assert ctx.extra["quest"]["active_count"] == 2
        assert len(ctx.extra["quest"]["relevant_quests"]) == 1
        assert ctx.extra["quest"]["relevant_quests"][0]["quest_id"] == "q1"

    def test_on_node_enter_no_relevant_quests(self):
        service = _make_service_mock()
        service.get_active_quests.return_value = [
            Quest(
                quest_id="q1",
                title="Test",
                quest_type="deliver",
                target_node_ids=["node_999"],
            ),
        ]
        module = QuestModule(service)
        ctx = _make_context("node_001")
        module.on_node_enter("node_001", ctx)

        assert ctx.extra["quest"]["active_count"] == 1
        assert len(ctx.extra["quest"]["relevant_quests"]) == 0
