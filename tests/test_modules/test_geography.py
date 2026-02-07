"""GeographyModule 테스트"""

from unittest.mock import MagicMock

from src.modules.base import GameContext
from src.modules.geography.module import GeographyModule
from src.modules.module_manager import ModuleManager


def make_mock_node(tier_value=1, tier_enum=None):
    """테스트용 Mock MapNode"""
    node = MagicMock()
    node.tier.value = tier_value
    if tier_enum:
        node.tier = tier_enum
    node.coordinate = "5_3"
    return node


def make_context(**kwargs):
    defaults = {
        "player_id": "test_player",
        "current_node_id": "0_0",
        "current_turn": 1,
        "db_session": MagicMock(),
    }
    defaults.update(kwargs)
    return GameContext(**defaults)


def make_geography():
    """테스트용 GeographyModule (Mock 의존성)"""
    return GeographyModule(
        world_generator=MagicMock(),
        navigator=MagicMock(),
        sub_grid_generator=MagicMock(),
    )


class TestGeographyBasics:
    def test_name(self):
        geo = make_geography()
        assert geo.name == "geography"

    def test_no_dependencies(self):
        geo = make_geography()
        assert geo.dependencies == []

    def test_enable_disable(self):
        geo = make_geography()
        geo.on_enable()
        geo.enabled = True
        assert geo.enabled is True
        geo.on_disable()
        geo.enabled = False
        assert geo.enabled is False

    def test_on_turn_no_error(self):
        geo = make_geography()
        ctx = make_context()
        geo.on_turn(ctx)


class TestGeographyInModuleManager:
    def test_register_and_enable(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        assert mm.enable("geography") is True
        assert mm.is_enabled("geography") is True

    def test_provides_movement_actions(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        mm.enable("geography")

        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        action_names = [a.name for a in actions]
        assert "move_north" in action_names
        assert "move_south" in action_names
        assert "move_east" in action_names
        assert "move_west" in action_names

    def test_disabled_no_actions(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        assert len(actions) == 0


class TestOnNodeEnter:
    def test_stores_geography_in_extra(self):
        mock_world = MagicMock()
        mock_node = make_mock_node(tier_value=1)
        mock_world.get_or_generate.return_value = mock_node

        mock_nav = MagicMock()
        mock_view = MagicMock()
        mock_nav.get_location_view.return_value = mock_view

        geo = GeographyModule(
            world_generator=mock_world,
            navigator=mock_nav,
            sub_grid_generator=MagicMock(),
        )

        ctx = make_context(current_node_id="5_3")
        geo.on_node_enter("5_3", ctx)

        assert "geography" in ctx.extra
        assert ctx.extra["geography"]["x"] == 5
        assert ctx.extra["geography"]["y"] == 3
        assert ctx.extra["geography"]["node"] is mock_node
        assert ctx.extra["geography"]["location_view"] is mock_view

    def test_invalid_node_id_no_crash(self):
        geo = make_geography()
        ctx = make_context()
        geo.on_node_enter("invalid", ctx)
        assert "geography" not in ctx.extra

    def test_world_get_or_generate_called(self):
        mock_world = MagicMock()
        mock_world.get_or_generate.return_value = make_mock_node()
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        ctx = make_context()
        geo.on_node_enter("10_20", ctx)
        mock_world.get_or_generate.assert_called_once_with(10, 20)


class TestGetAvailableActions:
    def test_main_grid_4_directions(self):
        geo = make_geography()
        ctx = make_context()
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "move_north" in names
        assert "move_up" not in names
        assert "enter_depth" not in names

    def test_main_grid_with_depth(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["geography"] = {"has_depth": True}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "enter_depth" in names

    def test_sub_grid_6_directions(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "move_north" in names
        assert "move_up" in names
        assert "move_down" in names
        assert "enter_depth" not in names

    def test_sub_grid_at_entrance_has_exit(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        ctx.extra["sub_position"] = {"sx": 0, "sy": 0, "sz": 0}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "exit_depth" in names

    def test_sub_grid_deep_no_exit(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        ctx.extra["sub_position"] = {"sx": 1, "sy": 0, "sz": -2}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "exit_depth" not in names


class TestGeographyAccessors:
    def test_get_node_delegates(self):
        mock_world = MagicMock()
        mock_world.get_node.return_value = "fake_node"
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        result = geo.get_node(5, 3)
        mock_world.get_node.assert_called_once_with(5, 3)
        assert result == "fake_node"

    def test_get_or_generate_delegates(self):
        mock_world = MagicMock()
        mock_world.get_or_generate.return_value = "generated_node"
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        result = geo.get_or_generate_node(7, 8)
        mock_world.get_or_generate.assert_called_once_with(7, 8)
        assert result == "generated_node"

    def test_property_accessors(self):
        mock_world = MagicMock()
        mock_nav = MagicMock()
        mock_sub = MagicMock()
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=mock_nav,
            sub_grid_generator=mock_sub,
        )
        assert geo.world is mock_world
        assert geo.navigator is mock_nav
        assert geo.sub_grid_generator is mock_sub


class TestModuleNameOnActions:
    def test_all_actions_have_correct_module_name(self):
        geo = make_geography()
        ctx = make_context()
        actions = geo.get_available_actions(ctx)
        for action in actions:
            assert action.module_name == "geography"
