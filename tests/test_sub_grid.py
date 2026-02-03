"""Tests for sub-grid system."""

import pytest

from src.core.axiom_system import AxiomLoader
from src.core.engine import ITWEngine, PlayerState
from src.core.navigator import Direction
from src.core.sub_grid import DepthPoint, SubGridGenerator, SubGridNode, SubGridType
from src.core.world_generator import NodeTier


@pytest.fixture()
def axiom_loader() -> AxiomLoader:
    """Create an AxiomLoader instance."""
    return AxiomLoader("src/data/itw_214_divine_axioms.json")


@pytest.fixture()
def sub_grid_generator(axiom_loader: AxiomLoader) -> SubGridGenerator:
    """Create a SubGridGenerator instance."""
    return SubGridGenerator(axiom_loader, seed=42)


@pytest.fixture()
def engine() -> ITWEngine:
    """Create an ITWEngine instance with fixed seed."""
    return ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )


@pytest.fixture()
def engine_with_player(engine: ITWEngine) -> tuple[ITWEngine, PlayerState]:
    """Create an engine with a registered player."""
    player = engine.register_player("test_player")
    return engine, player


class TestSubGridNode:
    """Tests for SubGridNode dataclass."""

    def test_sub_grid_node_creation(self):
        """Test SubGridNode creation and properties."""
        node = SubGridNode(
            parent_coordinate="5_3",
            sx=1,
            sy=2,
            sz=-1,
            tier="Uncommon",
            axiom_vector={"axiom_terra": 0.8},
            sensory_data={"visual_near": "어두운 통로"},
            required_tags=["tag_light_source"],
            is_entrance=False,
            is_exit=False,
        )

        # Check basic properties
        assert node.parent_coordinate == "5_3"
        assert node.sx == 1
        assert node.sy == 2
        assert node.sz == -1
        assert node.tier == "Uncommon"

        # Check computed properties
        assert node.id == "5_3_1_2_-1"
        assert node.coordinate == ("5_3", 1, 2, -1)

        # Check to_dict/from_dict roundtrip
        node_dict = node.to_dict()
        restored = SubGridNode.from_dict(node_dict)
        assert restored.id == node.id
        assert restored.tier == node.tier
        assert restored.axiom_vector == node.axiom_vector

    def test_depth_point_creation(self):
        """Test DepthPoint dataclass."""
        depth = DepthPoint(
            depth_name="Ancient Crypt",
            depth_tier=2,
            entry_condition="tag_holy_symbol",
            discovered=False,
            grid_type=SubGridType.DUNGEON,
        )

        assert depth.depth_name == "Ancient Crypt"
        assert depth.depth_tier == 2
        assert depth.grid_type == SubGridType.DUNGEON

        # Check to_dict/from_dict roundtrip
        depth_dict = depth.to_dict()
        restored = DepthPoint.from_dict(depth_dict)
        assert restored.depth_name == depth.depth_name
        assert restored.grid_type == depth.grid_type


class TestSubGridGenerator:
    """Tests for SubGridGenerator."""

    def test_sub_grid_generator(self, sub_grid_generator: SubGridGenerator):
        """Test node generation logic."""
        # Generate entrance node
        node = sub_grid_generator.generate_node(
            parent_x=0,
            parent_y=0,
            sx=0,
            sy=0,
            sz=0,
            depth_tier=1,
        )

        assert node is not None
        assert node.parent_coordinate == "0_0"
        assert node.sx == 0
        assert node.sy == 0
        assert node.sz == 0
        assert node.is_entrance is True  # sz=0, sx=0, sy=0

        # Node should be cached
        same_node = sub_grid_generator.get_node(0, 0, 0, 0, 0)
        assert same_node is node

    def test_effective_tier_calculation(self, sub_grid_generator: SubGridGenerator):
        """Test difficulty increases with depth."""
        # Tier increases with abs(sz)
        shallow = sub_grid_generator.generate_node(0, 0, 0, 0, -1, depth_tier=1)
        deep = sub_grid_generator.generate_node(0, 0, 0, 0, -3, depth_tier=1)

        # Deep node should have higher tier (harder)
        tier_order = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        shallow_idx = tier_order.index(shallow.tier)
        deep_idx = tier_order.index(deep.tier)

        # depth_tier=1, sz=-1 => effective=2, sz=-3 => effective=4
        assert deep_idx >= shallow_idx

    def test_generate_entrance(self, sub_grid_generator: SubGridGenerator):
        """Test entrance generation helper."""
        entrance = sub_grid_generator.generate_entrance(5, 3, depth_tier=2)

        assert entrance.parent_coordinate == "5_3"
        assert entrance.sx == 0
        assert entrance.sy == 0
        assert entrance.sz == 0
        assert entrance.is_entrance is True


class TestDirectionUpDown:
    """Tests for UP/DOWN direction support."""

    def test_direction_up_down(self):
        """Test UP/DOWN direction enum values."""
        assert Direction.UP.symbol == "UP"
        assert Direction.UP.dx == 0
        assert Direction.UP.dy == 0
        assert Direction.UP.dz == 1

        assert Direction.DOWN.symbol == "DOWN"
        assert Direction.DOWN.dx == 0
        assert Direction.DOWN.dy == 0
        assert Direction.DOWN.dz == -1

    def test_direction_nsew_unchanged(self):
        """Test N/S/E/W directions still work."""
        assert Direction.NORTH.dz == 0
        assert Direction.SOUTH.dz == 0
        assert Direction.EAST.dz == 0
        assert Direction.WEST.dz == 0


class TestEnterDepth:
    """Tests for entering sub-grid."""

    def test_enter_depth_success(self, engine_with_player):
        """Test successful entry into sub-grid."""
        engine, player = engine_with_player

        # Move to a node with depth (Uncommon or Rare)
        # Generate area and find suitable node
        engine.debug_generate_area(0, 0, radius=5)

        # Find an Uncommon/Rare node
        suitable_coord = None
        for coord, node in engine.world.nodes.items():
            if node.tier in [NodeTier.UNCOMMON, NodeTier.RARE]:
                suitable_coord = coord
                break

        if suitable_coord:
            # Teleport player there
            coords = suitable_coord.split("_")
            player.x = int(coords[0])
            player.y = int(coords[1])

            # Enter depth
            result = engine.enter_depth(player.player_id)

            assert result.success is True
            assert result.action_type == "enter"
            assert player.in_sub_grid is True
            assert player.sub_grid_parent == suitable_coord
            assert player.sub_x == 0
            assert player.sub_y == 0
            assert player.sub_z == 0

    def test_enter_depth_no_depth(self, engine_with_player):
        """Test entry fails when no depth exists."""
        engine, player = engine_with_player

        # Safe Haven (0,0) is Common tier, no depth
        assert player.x == 0
        assert player.y == 0

        result = engine.enter_depth(player.player_id)

        assert result.success is False
        assert "깊은 곳이 없습니다" in result.message
        assert player.in_sub_grid is False

    def test_enter_depth_already_in_sub_grid(self, engine_with_player):
        """Test entry fails when already in sub-grid."""
        engine, player = engine_with_player

        # Manually set player in sub-grid
        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"

        result = engine.enter_depth(player.player_id)

        assert result.success is False
        assert "이미 서브 그리드 안에" in result.message


class TestExitDepth:
    """Tests for exiting sub-grid."""

    def test_exit_depth_success(self, engine_with_player):
        """Test successful exit from sub-grid."""
        engine, player = engine_with_player

        # Manually set player in sub-grid at entrance
        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = 0

        result = engine.exit_depth(player.player_id)

        assert result.success is True
        assert result.action_type == "exit"
        assert player.in_sub_grid is False
        assert player.sub_grid_parent is None

    def test_exit_depth_not_at_entrance(self, engine_with_player):
        """Test exit fails when not at entrance (sz != 0)."""
        engine, player = engine_with_player

        # Set player deep in sub-grid
        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = -2  # Not at entrance

        result = engine.exit_depth(player.player_id)

        assert result.success is False
        assert "입구까지 올라가야" in result.message
        assert player.in_sub_grid is True  # Still in sub-grid

    def test_exit_depth_not_at_entrance_position(self, engine_with_player):
        """Test exit fails when not at entrance position (sx/sy != 0)."""
        engine, player = engine_with_player

        # Set player at sz=0 but not at entrance position
        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 1  # Not at entrance position
        player.sub_y = 0
        player.sub_z = 0

        result = engine.exit_depth(player.player_id)

        assert result.success is False
        assert "입구 위치로 이동" in result.message

    def test_exit_depth_not_in_sub_grid(self, engine_with_player):
        """Test exit fails when not in sub-grid."""
        engine, player = engine_with_player

        assert player.in_sub_grid is False

        result = engine.exit_depth(player.player_id)

        assert result.success is False
        assert "서브 그리드 안에 있지 않습니다" in result.message


class TestMoveInSubGrid:
    """Tests for movement within sub-grid."""

    def test_move_in_sub_grid(self, engine_with_player):
        """Test movement within sub-grid."""
        engine, player = engine_with_player

        # Set player in sub-grid
        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = 0

        # Move down
        result = engine.move(player.player_id, "down")

        assert result.success is True
        assert player.sub_z == -1
        assert player.sub_x == 0
        assert player.sub_y == 0

    def test_move_in_sub_grid_horizontal(self, engine_with_player):
        """Test horizontal movement in sub-grid."""
        engine, player = engine_with_player

        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = -1  # Not at entrance to allow movement

        # Move north
        result = engine.move(player.player_id, "n")

        assert result.success is True
        assert player.sub_y == 1
        assert player.sub_x == 0
        assert player.sub_z == -1

    def test_move_up_at_entrance_blocked(self, engine_with_player):
        """Test moving up at entrance is blocked (use exit instead)."""
        engine, player = engine_with_player

        player.in_sub_grid = True
        player.sub_grid_parent = "0_0"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = 0  # At entrance

        # Try to move up
        result = engine.move(player.player_id, "up")

        assert result.success is False
        assert "exit" in result.message.lower()

    def test_move_in_main_grid_no_up_down(self, engine_with_player):
        """Test UP/DOWN not valid in main grid."""
        engine, player = engine_with_player

        assert player.in_sub_grid is False

        # Try to move up in main grid
        result = engine.move(player.player_id, "up")

        assert result.success is False
        assert "알 수 없는 방향" in result.message
