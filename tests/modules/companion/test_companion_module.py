"""CompanionModule 테스트

#13-C-7 검증: 4개 테스트 케이스.
"""

from unittest.mock import MagicMock

import pytest

from src.core.companion.models import CompanionState
from src.modules.base import GameContext
from src.modules.companion.module import CompanionModule


@pytest.fixture()
def mock_service():
    return MagicMock()


@pytest.fixture()
def module(mock_service):
    return CompanionModule(mock_service)


@pytest.fixture()
def context():
    return GameContext(
        player_id="p1",
        current_node_id="1_1",
        current_turn=10,
    )


class TestCompanionModule:
    def test_name_and_dependencies(self, module) -> None:
        assert module.name == "companion"
        assert "npc_core" in module.dependencies
        assert "relationship" in module.dependencies
        assert "dialogue" in module.dependencies

    def test_get_actions_no_companion(self, module, mock_service, context) -> None:
        mock_service.get_active_companion.return_value = None
        actions = module.get_available_actions(context)
        assert len(actions) == 1
        assert actions[0].name == "recruit"

    def test_get_actions_with_companion(self, module, mock_service, context) -> None:
        mock_service.get_active_companion.return_value = CompanionState(
            companion_id="c1", player_id="p1", npc_id="npc1"
        )
        actions = module.get_available_actions(context)
        assert len(actions) == 1
        assert actions[0].name == "dismiss"

    def test_on_node_enter_sets_extra(self, module, mock_service, context) -> None:
        mock_service.get_active_companion.return_value = CompanionState(
            companion_id="c1",
            player_id="p1",
            npc_id="npc1",
            companion_type="voluntary",
        )
        module.on_node_enter("1_1", context)
        assert "companion" in context.extra
        assert context.extra["companion"]["npc_id"] == "npc1"
        assert context.extra["companion"]["companion_type"] == "voluntary"

    def test_on_node_enter_no_companion(self, module, mock_service, context) -> None:
        mock_service.get_active_companion.return_value = None
        module.on_node_enter("1_1", context)
        assert "companion" not in context.extra
