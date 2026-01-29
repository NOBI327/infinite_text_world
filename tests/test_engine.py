"""Tests for ITWEngine class."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.echo_system import EchoCategory
from src.core.engine import ITWEngine, PlayerState
from src.db.models import Base


@pytest.fixture()
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture()
def db_session(db_engine) -> Session:
    """Provide a database session."""
    session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    sess = session_factory()
    try:
        yield sess
    finally:
        sess.close()


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


class TestPlayerManagement:
    """Tests for player management."""

    def test_register_player(self, engine: ITWEngine):
        """Test player registration."""
        player = engine.register_player("new_player")

        assert player is not None
        assert player.player_id == "new_player"
        assert player.x == 0
        assert player.y == 0
        assert player.supply == 20
        assert player.fame == 0

        # Player should be stored in engine
        assert "new_player" in engine.players
        assert engine.get_player("new_player") == player

        # Safe Haven should be discovered
        assert "0_0" in player.discovered_nodes

    def test_register_player_returns_existing(self, engine: ITWEngine):
        """Test that registering same player returns existing one."""
        player1 = engine.register_player("same_player")
        player1.fame = 100  # Modify

        player2 = engine.register_player("same_player")

        assert player1 is player2
        assert player2.fame == 100

    def test_get_player_not_found(self, engine: ITWEngine):
        """Test getting non-existent player returns None."""
        result = engine.get_player("nonexistent")
        assert result is None


class TestLookAction:
    """Tests for look action."""

    def test_look(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test looking at current location."""
        engine, player = engine_with_player

        result = engine.look(player.player_id)

        assert result.success is True
        assert result.action_type == "look"
        assert result.location_view is not None
        assert result.location_view.visual_description is not None

    def test_look_player_not_found(self, engine: ITWEngine):
        """Test look fails for non-existent player."""
        result = engine.look("nonexistent_player")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message


class TestMoveAction:
    """Tests for move action."""

    def test_move_success(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test successful movement."""
        engine, player = engine_with_player
        initial_supply = player.supply
        initial_x, initial_y = player.x, player.y

        result = engine.move(player.player_id, "n")

        assert result.success is True
        assert result.action_type == "move"
        assert "이동했습니다" in result.message
        assert result.location_view is not None

        # Player position should update
        assert player.y == initial_y + 1
        assert player.x == initial_x

        # Supply should decrease
        assert player.supply < initial_supply
        assert result.data["supply_consumed"] > 0

        # New location should be discovered
        new_coord = f"{player.x}_{player.y}"
        assert new_coord in player.discovered_nodes

    def test_move_all_directions(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test movement in all directions."""
        engine, player = engine_with_player

        directions = {
            "n": (0, 1),
            "s": (0, -1),
            "e": (1, 0),
            "w": (-1, 0),
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
            "북": (0, 1),
            "남": (0, -1),
            "동": (1, 0),
            "서": (-1, 0),
        }

        for direction, (dx, dy) in directions.items():
            # Reset player position
            player.x = 0
            player.y = 0
            player.supply = 20

            result = engine.move(player.player_id, direction)

            assert result.success is True, f"Move {direction} failed"
            assert player.x == dx, f"X mismatch for {direction}"
            assert player.y == dy, f"Y mismatch for {direction}"

    def test_move_insufficient_supply(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test move fails when supply is insufficient."""
        engine, player = engine_with_player
        player.supply = 0

        result = engine.move(player.player_id, "n")

        assert result.success is False
        assert "Supply" in result.message

        # Player position should not change
        assert player.x == 0
        assert player.y == 0

    def test_move_invalid_direction(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test move fails with invalid direction."""
        engine, player = engine_with_player

        result = engine.move(player.player_id, "invalid_direction")

        assert result.success is False
        assert "알 수 없는 방향" in result.message

        # Player position should not change
        assert player.x == 0
        assert player.y == 0

    def test_move_player_not_found(self, engine: ITWEngine):
        """Test move fails for non-existent player."""
        result = engine.move("nonexistent_player", "n")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message


class TestRestAction:
    """Tests for rest action."""

    def test_rest_at_safe_haven(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test full recovery at Safe Haven."""
        engine, player = engine_with_player
        player.supply = 5  # Low supply
        player.investigation_penalty = 2

        result = engine.rest(player.player_id)

        assert result.success is True
        assert result.action_type == "rest"
        assert "완전히 회복" in result.message

        # Full recovery at Safe Haven
        assert player.supply == 20
        assert result.data["current_supply"] == 20
        assert result.data["recovery"] == 15

        # Penalty should be cleared
        assert player.investigation_penalty == 0

    def test_rest_at_normal_node(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test partial recovery at normal node."""
        engine, player = engine_with_player

        # Move to a non-safe-haven node
        engine.move(player.player_id, "n")
        player.supply = 5  # Low supply after moving

        result = engine.rest(player.player_id)

        assert result.success is True
        assert result.action_type == "rest"
        assert "휴식을 취했습니다" in result.message

        # Partial recovery (+5, max 20)
        assert player.supply == 10  # 5 + 5
        assert result.data["recovery"] == 5

    def test_rest_at_normal_node_caps_at_max(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test that rest at normal node doesn't exceed max supply."""
        engine, player = engine_with_player

        # Move to a non-safe-haven node
        engine.move(player.player_id, "n")
        player.supply = 18  # High supply

        result = engine.rest(player.player_id)

        # Should cap at 20
        assert player.supply == 20
        assert result.data["recovery"] == 2

    def test_rest_clears_investigation_penalty(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test that rest clears investigation penalty."""
        engine, player = engine_with_player
        player.investigation_penalty = 5

        engine.rest(player.player_id)

        assert player.investigation_penalty == 0

    def test_rest_player_not_found(self, engine: ITWEngine):
        """Test rest fails for non-existent player."""
        result = engine.rest("nonexistent_player")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message


class TestActionResult:
    """Tests for ActionResult structure."""

    def test_action_result_to_dict(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test ActionResult serialization."""
        engine, player = engine_with_player

        result = engine.look(player.player_id)
        result_dict = result.to_dict()

        assert "success" in result_dict
        assert "action" in result_dict
        assert "message" in result_dict
        assert result_dict["success"] is True
        assert result_dict["action"] == "look"


class TestEngineInitialization:
    """Tests for engine initialization."""

    def test_engine_initialization(self, engine: ITWEngine):
        """Test engine initializes correctly."""
        assert engine.axiom_loader is not None
        assert engine.world is not None
        assert engine.navigator is not None
        assert engine.echo_manager is not None
        assert engine.resolution_engine is not None

        # Safe Haven should exist
        safe_haven = engine.world.get_node(0, 0)
        assert safe_haven is not None
        assert safe_haven.is_safe_haven is True

    def test_engine_version(self, engine: ITWEngine):
        """Test engine has version."""
        assert engine.VERSION is not None
        assert isinstance(engine.VERSION, str)


class TestHarvestAction:
    """Tests for harvest action."""

    def test_harvest_success(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test successful resource harvesting."""
        engine, player = engine_with_player

        # Safe Haven has resources: res_basic_supply, res_healing_herb
        safe_haven = engine.world.get_node(0, 0)
        assert len(safe_haven.resources) > 0

        resource_id = safe_haven.resources[0].id
        initial_amount = safe_haven.resources[0].current_amount

        result = engine.harvest(player.player_id, resource_id, amount=5)

        assert result.success is True
        assert result.action_type == "harvest"
        assert "채취했습니다" in result.message
        assert result.data["resource"] == resource_id
        assert result.data["harvested"] == 5
        assert result.data["remaining"] == initial_amount - 5

        # Player inventory should be updated
        assert player.inventory[resource_id] == 5

    def test_harvest_adds_to_inventory(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test that harvesting adds to existing inventory."""
        engine, player = engine_with_player

        safe_haven = engine.world.get_node(0, 0)
        resource_id = safe_haven.resources[0].id

        # Pre-existing inventory
        player.inventory[resource_id] = 10

        engine.harvest(player.player_id, resource_id, amount=5)

        assert player.inventory[resource_id] == 15

    def test_harvest_no_resource(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test harvest fails when resource doesn't exist."""
        engine, player = engine_with_player

        result = engine.harvest(player.player_id, "nonexistent_resource")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message

    def test_harvest_depleted(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test harvest fails when resource is depleted."""
        engine, player = engine_with_player

        safe_haven = engine.world.get_node(0, 0)
        resource = safe_haven.resources[0]
        resource_id = resource.id

        # Deplete the resource
        resource.current_amount = 0

        result = engine.harvest(player.player_id, resource_id)

        assert result.success is False
        assert "고갈" in result.message

    def test_harvest_player_not_found(self, engine: ITWEngine):
        """Test harvest fails for non-existent player."""
        result = engine.harvest("nonexistent_player", "some_resource")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message


class TestInvestigateAction:
    """Tests for investigate action."""

    def test_investigate_no_hidden_echoes(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test investigate when no hidden echoes exist."""
        engine, player = engine_with_player

        # Safe Haven initially has no hidden echoes
        result = engine.investigate(player.player_id)

        assert result.success is False
        assert "숨겨진 흔적이 없습니다" in result.message

    def test_investigate_with_echo(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test investigating a hidden echo."""
        engine, player = engine_with_player

        # Create a hidden echo at player's location
        node = engine.world.get_node(player.x, player.y)
        engine.echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,  # Hidden visibility
            node=node,
            source_player_id="other_player",
        )

        # Verify hidden echo exists
        hidden = engine.echo_manager.get_hidden_echoes(node)
        assert len(hidden) > 0

        # Investigate
        result = engine.investigate(player.player_id)

        assert result.action_type == "investigate"
        # Result depends on dice roll, so we just check structure
        assert "success" in result.data
        assert "roll" in result.data
        assert "dc" in result.data

    def test_investigate_invalid_index(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test investigate with invalid echo index."""
        engine, player = engine_with_player

        # Create one hidden echo
        node = engine.world.get_node(player.x, player.y)
        engine.echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,
            node=node,
        )

        # Try to investigate with invalid index
        result = engine.investigate(player.player_id, echo_index=99)

        assert result.success is False
        assert "유효하지 않은" in result.message

    def test_investigate_player_not_found(self, engine: ITWEngine):
        """Test investigate fails for non-existent player."""
        result = engine.investigate("nonexistent_player")

        assert result.success is False
        assert "찾을 수 없습니다" in result.message


class TestCompassAction:
    """Tests for compass action."""

    def test_get_compass(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test compass output."""
        engine, player = engine_with_player

        compass = engine.get_compass(player.player_id)

        assert compass is not None
        assert isinstance(compass, str)
        # Compass should contain direction indicators
        assert "N" in compass or "북" in compass or "───" in compass

    def test_get_compass_player_not_found(self, engine: ITWEngine):
        """Test compass fails for non-existent player."""
        result = engine.get_compass("nonexistent_player")

        assert "찾을 수 없습니다" in result


class TestDebugActions:
    """Tests for debug actions."""

    def test_debug_teleport(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test debug teleport functionality."""
        engine, player = engine_with_player

        # Teleport to (10, 10)
        result = engine.debug_teleport(player.player_id, 10, 10)

        assert result.success is True
        assert result.action_type == "debug_teleport"
        assert "텔레포트 완료" in result.message
        assert result.location_view is not None

        # Player position should be updated
        assert player.x == 10
        assert player.y == 10

    def test_debug_teleport_generates_node(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test that teleport generates node if it doesn't exist."""
        engine, player = engine_with_player

        # Teleport to a location that doesn't exist yet
        result = engine.debug_teleport(player.player_id, 100, 100)

        assert result.success is True

        # Node should now exist
        node = engine.world.get_node(100, 100)
        assert node is not None

    def test_debug_teleport_player_not_found(self, engine: ITWEngine):
        """Test teleport fails for non-existent player."""
        result = engine.debug_teleport("nonexistent_player", 5, 5)

        assert result.success is False
        assert "찾을 수 없습니다" in result.message

    def test_debug_generate_area(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test debug area generation."""
        engine, player = engine_with_player

        initial_nodes = len(engine.world.nodes)

        nodes = engine.debug_generate_area(50, 50, radius=2)

        # Should generate (2*2+1)^2 = 25 nodes
        assert len(nodes) == 25
        assert len(engine.world.nodes) > initial_nodes


class TestDatabasePersistence:
    """Tests for database save/load functionality."""

    def test_save_world_to_db(
        self,
        engine_with_player: tuple[ITWEngine, PlayerState],
        db_session: Session,
    ):
        """Test saving world nodes to database."""
        engine, player = engine_with_player

        # Generate some nodes
        engine.debug_generate_area(0, 0, radius=2)
        initial_node_count = len(engine.world.nodes)

        # Save to DB
        saved_count = engine.save_world_to_db(db_session)

        assert saved_count == initial_node_count
        assert saved_count > 0

    def test_load_world_from_db(
        self,
        engine_with_player: tuple[ITWEngine, PlayerState],
        db_session: Session,
    ):
        """Test loading world nodes from database."""
        engine, player = engine_with_player

        # Generate and save nodes
        engine.debug_generate_area(0, 0, radius=2)
        original_nodes = dict(engine.world.nodes)
        engine.save_world_to_db(db_session)

        # Clear engine's world nodes (except Safe Haven regenerated)
        engine.world.nodes.clear()

        # Load from DB
        loaded_count = engine.load_world_from_db(db_session)

        assert loaded_count == len(original_nodes)

        # Verify a node was loaded correctly
        for coord, original_node in original_nodes.items():
            loaded_node = engine.world.nodes.get(coord)
            assert loaded_node is not None
            assert loaded_node.x == original_node.x
            assert loaded_node.y == original_node.y
            assert loaded_node.tier == original_node.tier

    def test_save_players_to_db(
        self,
        engine_with_player: tuple[ITWEngine, PlayerState],
        db_session: Session,
    ):
        """Test saving players to database."""
        engine, player = engine_with_player

        # Modify player state
        player.fame = 100
        player.supply = 15
        player.inventory["test_item"] = 5

        # Register another player
        player2 = engine.register_player("player_two")
        player2.x = 5
        player2.y = 5

        # Save to DB
        saved_count = engine.save_players_to_db(db_session)

        assert saved_count == 2

    def test_load_players_from_db(
        self,
        engine_with_player: tuple[ITWEngine, PlayerState],
        db_session: Session,
    ):
        """Test loading players from database."""
        engine, player = engine_with_player

        # Modify player state
        player.fame = 150
        player.supply = 12
        player.inventory["special_item"] = 10
        player.x = 3
        player.y = 7

        # Save to DB
        engine.save_players_to_db(db_session)

        # Clear engine's players
        original_player_id = player.player_id
        engine.players.clear()

        # Load from DB
        loaded_count = engine.load_players_from_db(db_session)

        assert loaded_count == 1

        # Verify player was loaded correctly
        loaded_player = engine.get_player(original_player_id)
        assert loaded_player is not None
        assert loaded_player.fame == 150
        assert loaded_player.supply == 12
        assert loaded_player.inventory.get("special_item") == 10
        assert loaded_player.x == 3
        assert loaded_player.y == 7


class TestGlobalEvents:
    """Tests for global event functionality."""

    def test_trigger_global_event(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test triggering a global event."""
        engine, player = engine_with_player

        initial_hooks = len(engine.global_hooks)

        engine.trigger_global_event(
            player_id=player.player_id,
            event_type="boss_kill",
            description="A mighty dragon has been slain!",
        )

        # Hook should be added
        assert len(engine.global_hooks) == initial_hooks + 1

        # Verify hook structure
        hook = engine.global_hooks[-1]
        assert hook["event"] == "boss_kill"
        assert "dragon" in hook["description"]
        assert "timestamp" in hook

    def test_trigger_global_event_boss_adds_fame(
        self, engine_with_player: tuple[ITWEngine, PlayerState]
    ):
        """Test that boss_kill event increases player fame."""
        engine, player = engine_with_player
        initial_fame = player.fame

        engine.trigger_global_event(
            player_id=player.player_id,
            event_type="boss_kill",
            description="Epic boss defeated!",
        )

        # Boss kill should add 100 fame
        assert player.fame == initial_fame + 100

    def test_trigger_global_event_player_not_found(self, engine: ITWEngine):
        """Test that event does nothing for non-existent player."""
        initial_hooks = len(engine.global_hooks)

        engine.trigger_global_event(
            player_id="nonexistent",
            event_type="test_event",
            description="Test description",
        )

        # No hook should be added
        assert len(engine.global_hooks) == initial_hooks

    def test_get_active_hooks(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test getting active global hooks."""
        engine, player = engine_with_player

        # Trigger some events
        engine.trigger_global_event(player.player_id, "event_1", "Description 1")
        engine.trigger_global_event(player.player_id, "event_2", "Description 2")

        active_hooks = engine.get_active_hooks()

        # Both hooks should be active (within 24 hours)
        assert len(active_hooks) >= 2

    def test_get_world_stats(self, engine_with_player: tuple[ITWEngine, PlayerState]):
        """Test getting world statistics."""
        engine, player = engine_with_player

        # Generate some nodes and trigger events
        engine.debug_generate_area(0, 0, radius=3)
        engine.trigger_global_event(player.player_id, "test", "Test event")

        stats = engine.get_world_stats()

        assert "engine_version" in stats
        assert "world" in stats
        assert "axioms" in stats
        assert "active_players" in stats
        assert "global_hooks" in stats

        assert stats["engine_version"] == engine.VERSION
        assert stats["active_players"] == 1
        assert stats["global_hooks"] >= 1
        assert stats["world"]["total_nodes"] > 0
