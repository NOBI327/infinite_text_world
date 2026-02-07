"""GameModule, GameContext, Action 테스트"""

from unittest.mock import MagicMock

from src.modules.base import GameModule, GameContext, Action


class DummyModule(GameModule):
    """테스트용 더미 모듈"""

    @property
    def name(self) -> str:
        return "dummy"

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        pass

    def get_available_actions(self, context: GameContext) -> list:
        return []


class DependentModule(GameModule):
    """의존성 있는 테스트용 모듈"""

    @property
    def name(self) -> str:
        return "dependent"

    @property
    def dependencies(self) -> list:
        return ["dummy"]

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        pass

    def get_available_actions(self, context: GameContext) -> list:
        return [Action(name="dep_action", display_name="Dep", module_name="dependent")]


def make_context(**kwargs):
    defaults = {
        "player_id": "test_player",
        "current_node_id": "node_0_0",
        "current_turn": 1,
        "db_session": MagicMock(),
    }
    defaults.update(kwargs)
    return GameContext(**defaults)


class TestGameContext:
    def test_create_context(self):
        ctx = make_context()
        assert ctx.player_id == "test_player"
        assert ctx.current_node_id == "node_0_0"
        assert ctx.current_turn == 1
        assert ctx.extra == {}

    def test_extra_slot(self):
        ctx = make_context()
        ctx.extra["weather"] = "rain"
        assert ctx.extra["weather"] == "rain"


class TestGameModule:
    def test_dummy_module_defaults(self):
        m = DummyModule()
        assert m.name == "dummy"
        assert m.enabled is False
        assert m.dependencies == []

    def test_dependent_module_dependencies(self):
        m = DependentModule()
        assert m.dependencies == ["dummy"]

    def test_enable_disable_flag(self):
        m = DummyModule()
        m.enabled = True
        assert m.enabled is True
        m.enabled = False
        assert m.enabled is False


class TestAction:
    def test_create_action(self):
        a = Action(name="talk", display_name="대화하기", module_name="npc_core")
        assert a.name == "talk"
        assert a.module_name == "npc_core"
        assert a.params == {}
