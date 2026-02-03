"""Tests for navigator module."""

import pytest

from src.core.axiom_system import AxiomLoader
from src.core.navigator import Direction, Navigator
from src.core.world_generator import WorldGenerator


@pytest.fixture()
def axiom_loader() -> AxiomLoader:
    """Load axioms from the data file."""
    return AxiomLoader("src/data/itw_214_divine_axioms.json")


@pytest.fixture()
def world(axiom_loader: AxiomLoader) -> WorldGenerator:
    """Create a WorldGenerator with fixed seed."""
    return WorldGenerator(axiom_loader, seed=42)


@pytest.fixture()
def navigator(world: WorldGenerator, axiom_loader: AxiomLoader) -> Navigator:
    """Create a Navigator instance."""
    return Navigator(world, axiom_loader)


class TestNavigator:
    """Tests for Navigator class."""

    def test_get_location_view(self, navigator: Navigator):
        """Test generating location view for current position."""
        player_id = "test_player"

        # Get view for Safe Haven (0, 0)
        view = navigator.get_location_view(0, 0, player_id)

        assert view is not None
        assert view.coordinate_hash is not None
        assert len(view.coordinate_hash) == 8  # MD5 hash prefix
        assert view.visual_description is not None
        assert view.atmosphere is not None
        assert view.sound is not None
        assert view.smell is not None

        # Should have direction hints for all 6 directions (N, S, E, W, UP, DOWN)
        assert len(view.direction_hints) == 6

        # Safe Haven should have special features
        assert len(view.special_features) > 0
        assert any("안전 지대" in f for f in view.special_features)

        # Safe Haven should have resources
        assert len(view.available_resources) > 0

    def test_get_location_view_marks_discovered(
        self, navigator: Navigator, world: WorldGenerator
    ):
        """Test that viewing a location marks it as discovered."""
        player_id = "test_player"

        # Generate a node first
        node = world.generate_node(5, 5)
        assert player_id not in node.discovered_by

        # Get location view
        navigator.get_location_view(5, 5, player_id)

        # Should now be discovered
        assert player_id in node.discovered_by

    def test_travel_success(self, navigator: Navigator):
        """Test successful travel with sufficient supply."""
        player_id = "test_player"
        current_supply = 10

        # Travel from Safe Haven (0, 0) to North (0, 1)
        result = navigator.travel(
            current_x=0,
            current_y=0,
            direction=Direction.NORTH,
            player_id=player_id,
            current_supply=current_supply,
        )

        assert result.success is True
        assert result.new_location is not None
        assert result.supply_consumed >= 1
        assert result.supply_consumed <= current_supply
        assert "이동했습니다" in result.message

    def test_travel_all_directions(self, navigator: Navigator):
        """Test travel in all four horizontal directions (UP/DOWN not valid in main grid)."""
        player_id = "test_player"

        # Only test N, S, E, W for main grid travel
        horizontal_directions = [
            Direction.NORTH,
            Direction.SOUTH,
            Direction.EAST,
            Direction.WEST,
        ]

        for direction in horizontal_directions:
            result = navigator.travel(
                current_x=0,
                current_y=0,
                direction=direction,
                player_id=player_id,
                current_supply=20,
            )

            assert result.success is True
            assert result.new_location is not None

    def test_travel_insufficient_supply(self, navigator: Navigator):
        """Test travel fails when supply is insufficient."""
        player_id = "test_player"
        current_supply = 0  # No supply

        result = navigator.travel(
            current_x=0,
            current_y=0,
            direction=Direction.NORTH,
            player_id=player_id,
            current_supply=current_supply,
        )

        assert result.success is False
        assert result.new_location is None
        assert result.supply_consumed == 0
        assert "Supply가 부족합니다" in result.message

    def test_travel_missing_tags(self, navigator: Navigator, world: WorldGenerator):
        """Test travel fails when required tags are missing."""
        player_id = "test_player"

        # Create a node with required tags
        node = world.generate_node(1, 0)
        node.required_tags = ["special_key", "fire_resist"]

        # Try to travel without required tags
        result = navigator.travel(
            current_x=0,
            current_y=0,
            direction=Direction.EAST,
            player_id=player_id,
            current_supply=20,
            player_inventory=[],
        )

        assert result.success is False
        assert result.new_location is None
        assert result.supply_consumed == 0
        assert "필요한 장비가 없습니다" in result.message

    def test_travel_with_required_tags(
        self, navigator: Navigator, world: WorldGenerator
    ):
        """Test travel succeeds when required tags are provided."""
        player_id = "test_player"

        # Create a node with required tags
        node = world.generate_node(1, 0)
        node.required_tags = ["special_key"]

        # Travel with required tags
        result = navigator.travel(
            current_x=0,
            current_y=0,
            direction=Direction.EAST,
            player_id=player_id,
            current_supply=20,
            player_inventory=["special_key", "other_item"],
        )

        assert result.success is True
        assert result.new_location is not None

    def test_direction_hints(self, navigator: Navigator):
        """Test that direction hints are generated for all directions."""
        player_id = "test_player"

        view = navigator.get_location_view(0, 0, player_id)

        # Should have 6 direction hints (N, S, E, W, UP, DOWN)
        assert len(view.direction_hints) == 6

        # Check each direction hint
        directions_found = set()
        for hint in view.direction_hints:
            directions_found.add(hint.direction)
            assert hint.visual_hint is not None
            assert hint.atmosphere_hint is not None
            assert hint.danger_level in ["Safe", "Mild", "Caution", "Danger"]
            assert hint.distance_hint is not None
            assert isinstance(hint.discovered, bool)

        # All six directions should be present
        assert Direction.NORTH in directions_found
        assert Direction.SOUTH in directions_found
        assert Direction.EAST in directions_found
        assert Direction.WEST in directions_found
        assert Direction.UP in directions_found
        assert Direction.DOWN in directions_found

    def test_direction_hints_discovered_vs_undiscovered(
        self, navigator: Navigator, world: WorldGenerator
    ):
        """Test that discovered nodes have more detailed hints."""
        player_id = "test_player"

        # First, discover the node to the north
        navigator.get_location_view(0, 1, player_id)

        # Now get view from Safe Haven
        view = navigator.get_location_view(0, 0, player_id)

        # Find north hint
        north_hint = next(
            h for h in view.direction_hints if h.direction == Direction.NORTH
        )
        assert north_hint.discovered is True

        # Find an undiscovered direction (e.g., south if not visited)
        south_node = world.get_node(0, -1)
        if south_node is None or player_id not in south_node.discovered_by:
            south_hint = next(
                h for h in view.direction_hints if h.direction == Direction.SOUTH
            )
            assert south_hint.discovered is False

    def test_calculate_travel_cost(self, navigator: Navigator, world: WorldGenerator):
        """Test travel cost calculation."""
        # Get Safe Haven
        safe_haven = world.get_node(0, 0)

        # Generate adjacent node
        adjacent = world.generate_node(1, 0)

        cost = navigator.calculate_travel_cost(safe_haven, adjacent)

        # Cost should be at least 1
        assert cost >= 1

    def test_safe_haven_danger_level(self, navigator: Navigator):
        """Test that Safe Haven is marked as Safe."""
        player_id = "test_player"

        view = navigator.get_location_view(0, 0, player_id)

        # Get hint pointing back to Safe Haven from adjacent node
        # First travel away
        navigator.travel(0, 0, Direction.NORTH, player_id, 20)

        # Get view from new location
        view = navigator.get_location_view(0, 1, player_id)

        # Find south hint (pointing back to Safe Haven)
        south_hint = next(
            h for h in view.direction_hints if h.direction == Direction.SOUTH
        )

        assert south_hint.danger_level == "Safe"

    def test_location_view_to_dict(self, navigator: Navigator):
        """Test LocationView serialization."""
        player_id = "test_player"

        view = navigator.get_location_view(0, 0, player_id)
        view_dict = view.to_dict()

        assert "location_id" in view_dict
        assert "description" in view_dict
        assert "directions" in view_dict
        assert "resources" in view_dict
        assert "echoes" in view_dict
        assert "special" in view_dict

        # Check description structure
        assert "visual" in view_dict["description"]
        assert "atmosphere" in view_dict["description"]
        assert "sound" in view_dict["description"]
        assert "smell" in view_dict["description"]
