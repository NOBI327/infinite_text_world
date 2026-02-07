"""ModuleManager 테스트"""

from unittest.mock import MagicMock

from src.modules.base import GameModule, GameContext, Action
from src.modules.module_manager import ModuleManager
from src.core.event_bus import GameEvent


# --- 테스트용 모듈 ---


class AlphaModule(GameModule):
    def __init__(self):
        super().__init__()
        self.enable_called = False
        self.disable_called = False
        self.turns_processed = 0
        self.nodes_entered = []

    @property
    def name(self):
        return "alpha"

    def on_enable(self):
        self.enable_called = True

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        self.turns_processed += 1

    def on_node_enter(self, node_id, context):
        self.nodes_entered.append(node_id)

    def get_available_actions(self, context):
        return [Action(name="alpha_act", display_name="Alpha", module_name="alpha")]


class BetaModule(GameModule):
    """alpha에 의존하는 모듈"""

    def __init__(self):
        super().__init__()
        self.enable_called = False
        self.disable_called = False

    @property
    def name(self):
        return "beta"

    @property
    def dependencies(self):
        return ["alpha"]

    def on_enable(self):
        self.enable_called = True

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        pass

    def on_node_enter(self, node_id, context):
        pass

    def get_available_actions(self, context):
        return [Action(name="beta_act", display_name="Beta", module_name="beta")]


class GammaModule(GameModule):
    """beta에 의존 (alpha → beta → gamma 체인)"""

    def __init__(self):
        super().__init__()
        self.disable_called = False

    @property
    def name(self):
        return "gamma"

    @property
    def dependencies(self):
        return ["beta"]

    def on_enable(self):
        pass

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        pass

    def on_node_enter(self, node_id, context):
        pass

    def get_available_actions(self, context):
        return []


def make_context():
    return GameContext(
        player_id="p1",
        current_node_id="n1",
        current_turn=1,
        db_session=MagicMock(),
    )


class TestRegister:
    def test_register_module(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert "alpha" in mm.modules

    def test_register_overwrites(self):
        mm = ModuleManager()
        m1 = AlphaModule()
        m2 = AlphaModule()
        mm.register(m1)
        mm.register(m2)
        assert mm.modules["alpha"] is m2


class TestEnable:
    def test_enable_success(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.enable("alpha") is True
        assert mm.is_enabled("alpha") is True

    def test_enable_calls_on_enable(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        assert m.enable_called is True

    def test_enable_nonexistent(self):
        mm = ModuleManager()
        assert mm.enable("nonexistent") is False

    def test_enable_already_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")
        assert mm.enable("alpha") is True  # 중복 활성화 OK

    def test_enable_with_dependency_met(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        mm.enable("alpha")
        assert mm.enable("beta") is True

    def test_enable_with_dependency_not_met(self):
        mm = ModuleManager()
        mm.register(BetaModule())  # alpha 미등록
        assert mm.enable("beta") is False

    def test_enable_with_dependency_not_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())  # 등록만, 활성화 안 함
        mm.register(BetaModule())
        assert mm.enable("beta") is False


class TestDisable:
    def test_disable_success(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        assert mm.disable("alpha") is True
        assert mm.is_enabled("alpha") is False
        assert m.disable_called is True

    def test_disable_nonexistent(self):
        mm = ModuleManager()
        assert mm.disable("nonexistent") is False

    def test_disable_already_disabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.disable("alpha") is True

    def test_cascade_disable(self):
        """alpha 비활성화 시 beta도 비활성화"""
        mm = ModuleManager()
        mm.register(AlphaModule())
        b = BetaModule()
        mm.register(b)
        mm.enable("alpha")
        mm.enable("beta")
        mm.disable("alpha")
        assert mm.is_enabled("alpha") is False
        assert mm.is_enabled("beta") is False
        assert b.disable_called is True

    def test_deep_cascade_disable(self):
        """alpha → beta → gamma 체인 cascade"""
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        g = GammaModule()
        mm.register(g)
        mm.enable("alpha")
        mm.enable("beta")
        mm.enable("gamma")
        mm.disable("alpha")
        assert mm.is_enabled("gamma") is False
        assert g.disable_called is True


class TestProcessTurn:
    def test_only_enabled_modules_process(self):
        mm = ModuleManager()
        m1 = AlphaModule()
        b = BetaModule()
        mm.register(m1)
        mm.register(b)
        mm.enable("alpha")
        # beta는 비활성 (의존성 때문이 아니라 enable 안 해서)

        ctx = make_context()
        mm.process_turn(ctx)
        assert m1.turns_processed == 1


class TestProcessNodeEnter:
    def test_node_enter_called(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        ctx = make_context()
        mm.process_node_enter("node_5_3", ctx)
        assert "node_5_3" in m.nodes_entered


class TestGetAllActions:
    def test_collect_actions_from_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        mm.enable("alpha")
        mm.enable("beta")
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        names = [a.name for a in actions]
        assert "alpha_act" in names
        assert "beta_act" in names

    def test_disabled_module_no_actions(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        assert len(actions) == 0  # alpha 미활성화


class TestIsEnabled:
    def test_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")
        assert mm.is_enabled("alpha") is True

    def test_not_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.is_enabled("alpha") is False

    def test_not_registered(self):
        mm = ModuleManager()
        assert mm.is_enabled("unknown") is False


class TestModuleManagerEventBus:
    def test_has_event_bus(self):
        mm = ModuleManager()
        assert mm.event_bus is not None

    def test_process_turn_resets_chain(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")

        # 이벤트 발행으로 chain에 기록 남기기
        mm.event_bus.emit(GameEvent(event_type="test", data={}, source="test"))
        assert len(mm.event_bus._emitted_in_chain) == 1

        ctx = make_context()
        mm.process_turn(ctx)

        # process_turn 후 chain 초기화됨
        assert len(mm.event_bus._emitted_in_chain) == 0
