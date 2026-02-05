"""Tests for echo_system module (d6 Dice Pool system)."""

from datetime import datetime, timedelta

import pytest

from src.core.axiom_system import AxiomLoader
from src.core.echo_system import (
    EchoCategory,
    EchoManager,
    EchoType,
    EchoVisibility,
)
from src.core.world_generator import Echo, MapNode, WorldGenerator


@pytest.fixture()
def axiom_loader() -> AxiomLoader:
    """Load axioms from the data file."""
    return AxiomLoader("src/data/itw_214_divine_axioms.json")


@pytest.fixture()
def world(axiom_loader: AxiomLoader) -> WorldGenerator:
    """Create a WorldGenerator with fixed seed."""
    return WorldGenerator(axiom_loader, seed=42)


@pytest.fixture()
def echo_manager(axiom_loader: AxiomLoader) -> EchoManager:
    """Create an EchoManager instance."""
    return EchoManager(axiom_loader)


@pytest.fixture()
def test_node(world: WorldGenerator) -> MapNode:
    """Create a test node."""
    return world.generate_node(5, 5)


class TestEchoManager:
    """Tests for EchoManager class."""

    def test_create_echo(self, echo_manager: EchoManager, test_node: MapNode):
        """Test Echo creation and node addition."""
        initial_echo_count = len(test_node.echoes)

        # Create a combat echo
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,
            node=test_node,
            source_player_id="player_001",
        )

        assert echo is not None
        assert echo.echo_type == EchoType.SHORT.value
        assert echo.visibility == EchoVisibility.PUBLIC.value
        assert echo.base_difficulty == 2  # Combat base_difficulty
        assert echo.source_player_id == "player_001"
        assert echo.flavor_text is not None
        assert echo.timestamp is not None

        # Echo should be added to node
        assert len(test_node.echoes) == initial_echo_count + 1
        assert echo in test_node.echoes

    def test_create_echo_with_custom_flavor(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test Echo creation with custom flavor text."""
        custom_text = "A legendary battle took place here..."

        echo = echo_manager.create_echo(
            category=EchoCategory.BOSS,
            node=test_node,
            custom_flavor=custom_text,
        )

        assert custom_text in echo.flavor_text

    def test_create_echo_with_difficulty_modifier(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test Echo creation with difficulty modifier."""
        # Mystery has base_difficulty 4
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,
            node=test_node,
            difficulty_modifier=1,
        )

        assert echo.base_difficulty == 5  # 4 + 1

    def test_investigation_difficulty_calculation(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test difficulty calculation for d6 Dice Pool system."""
        echo = echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,
            node=test_node,
        )

        diff_info = echo_manager.calculate_investigation_difficulty(echo)

        assert "base_difficulty" in diff_info
        assert "time_modifier" in diff_info
        assert "final_difficulty" in diff_info
        assert "days_passed" in diff_info

        # Base difficulty for exploration is 2
        assert diff_info["base_difficulty"] == 2

        # Fresh echo has no time modifier
        assert diff_info["time_modifier"] == 0
        assert diff_info["final_difficulty"] == 2

    def test_investigation_time_modifier(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test that time increases difficulty (7 days = +1, max +2)."""
        # Create echo with 14 days old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(days=14)).isoformat()
        echo = Echo(
            echo_type=EchoType.SHORT.value,
            visibility=EchoVisibility.HIDDEN.value,
            base_difficulty=2,
            timestamp=old_timestamp,
            flavor_text="Old echo",
            source_player_id=None,
        )

        diff_info = echo_manager.calculate_investigation_difficulty(echo)

        # 14 days = +2 time modifier (7 days per +1, max +2)
        assert diff_info["days_passed"] == 14
        assert diff_info["time_modifier"] == 2
        assert diff_info["final_difficulty"] == 4  # 2 + 2

    def test_investigation_time_modifier_max_cap(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test that time modifier is capped at +2."""
        # Create echo with 30 days old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()
        echo = Echo(
            echo_type=EchoType.SHORT.value,
            visibility=EchoVisibility.HIDDEN.value,
            base_difficulty=2,
            timestamp=old_timestamp,
            flavor_text="Very old echo",
            source_player_id=None,
        )

        diff_info = echo_manager.calculate_investigation_difficulty(echo)

        # Time modifier capped at +2
        assert diff_info["time_modifier"] == 2
        assert diff_info["final_difficulty"] == 4  # 2 + 2 (capped)

    def test_investigation_with_dice_pool_success(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test successful investigation with d6 Dice Pool (hits >= difficulty)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,  # base_difficulty=2
            node=test_node,
            source_player_id="player_xyz",
        )

        # hits=3 >= difficulty=2 should succeed
        result = echo_manager.investigate(echo=echo, hits=3)

        assert result["success"] is True
        assert "discovered_info" in result
        assert result["discovered_info"]["flavor"] == echo.flavor_text
        assert result["hits"] == 3
        assert result["difficulty"] == 2
        assert result["margin"] == 1

    def test_investigation_with_dice_pool_failure(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test failed investigation with d6 Dice Pool (hits < difficulty)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,  # base_difficulty=4
            node=test_node,
        )

        # hits=2 < difficulty=4 should fail
        result = echo_manager.investigate(echo=echo, hits=2)

        assert result["success"] is False
        assert "message" in result
        assert "discovered_info" not in result
        assert result["hits"] == 2
        assert result["difficulty"] == 4
        assert result["margin"] == -2

    def test_investigate_critical_failure(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test critical failure with penalty (hits=0)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,
            node=test_node,
        )

        # hits=0 should trigger penalty
        result = echo_manager.investigate(echo=echo, hits=0)

        assert result["success"] is False
        assert "penalty" in result

    def test_investigate_critical_success(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test critical success with bonus info (hits >= difficulty + 2)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,  # base_difficulty=2
            node=test_node,
            source_player_id="player_abc",
        )

        # hits=4 >= difficulty=2 + 2 -> critical success
        result = echo_manager.investigate(echo=echo, hits=4)

        assert result["success"] is True
        assert result["margin"] >= 2
        assert "bonus_info" in result
        # Should reveal partial player ID
        assert "source_player_hint" in result

    def test_investigate_exact_difficulty(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test success when hits exactly equals difficulty."""
        echo = echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,  # base_difficulty=2
            node=test_node,
        )

        # hits=2 == difficulty=2 should succeed
        result = echo_manager.investigate(echo=echo, hits=2)

        assert result["success"] is True
        assert result["margin"] == 0

    def test_decay_echoes(self, echo_manager: EchoManager, test_node: MapNode):
        """Test Short Echo decay over time."""
        # Create a short echo with old timestamp (beyond decay days)
        old_timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()
        short_echo = Echo(
            echo_type=EchoType.SHORT.value,
            visibility=EchoVisibility.PUBLIC.value,
            base_difficulty=2,
            timestamp=old_timestamp,
            flavor_text="Old short echo",
            source_player_id=None,
        )
        test_node.echoes.append(short_echo)

        # Create a long echo (should not decay)
        long_echo = Echo(
            echo_type=EchoType.LONG.value,
            visibility=EchoVisibility.PUBLIC.value,
            base_difficulty=1,
            timestamp=old_timestamp,
            flavor_text="Old long echo",
            source_player_id=None,
        )
        test_node.echoes.append(long_echo)

        initial_count = len(test_node.echoes)

        # Decay echoes
        removed = echo_manager.decay_echoes(test_node)

        # Short echo should be removed, long echo should remain
        assert removed >= 1
        assert len(test_node.echoes) < initial_count
        assert long_echo in test_node.echoes

    def test_decay_echoes_preserves_recent(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test that recent Short Echoes are preserved."""
        # Create a recent short echo
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,
            node=test_node,
        )

        initial_count = len(test_node.echoes)

        # Decay should not remove recent echo
        removed = echo_manager.decay_echoes(test_node)

        assert echo in test_node.echoes
        assert len(test_node.echoes) == initial_count - removed

    def test_get_visible_hidden_echoes(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test Public/Hidden Echo filtering."""
        # Clear existing echoes
        test_node.echoes = []

        # Create public echo (Combat is public)
        echo_manager.create_echo(
            category=EchoCategory.COMBAT,
            node=test_node,
        )

        # Create hidden echo (Exploration is hidden)
        echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,
            node=test_node,
        )

        # Create another hidden echo (Mystery is hidden)
        echo_manager.create_echo(
            category=EchoCategory.MYSTERY,
            node=test_node,
        )

        visible = echo_manager.get_visible_echoes(test_node)
        hidden = echo_manager.get_hidden_echoes(test_node)

        assert len(visible) == 1
        assert len(hidden) == 2

        # Verify visibility
        for echo in visible:
            assert echo.visibility == EchoVisibility.PUBLIC.value
        for echo in hidden:
            assert echo.visibility == EchoVisibility.HIDDEN.value

    def test_create_global_hook(self, echo_manager: EchoManager):
        """Test global hook creation."""
        hook = echo_manager.create_global_hook(
            event_type="boss_kill",
            location_hint="Northern mountains",
            description="A great dragon has been slain!",
        )

        assert hook["type"] == "global_hook"
        assert hook["event"] == "boss_kill"
        assert hook["location_hint"] == "Northern mountains"
        assert hook["description"] == "A great dragon has been slain!"
        assert "timestamp" in hook
        assert hook["expires_in_hours"] == 24

    def test_get_fame_reward(self, echo_manager: EchoManager):
        """Test fame reward lookup."""
        assert echo_manager.get_fame_reward(EchoCategory.COMBAT) == 5
        assert echo_manager.get_fame_reward(EchoCategory.BOSS) == 100
        assert echo_manager.get_fame_reward(EchoCategory.MYSTERY) == 15
        assert echo_manager.get_fame_reward(EchoCategory.DEATH) == 0

    def test_echo_categories_have_templates(self, echo_manager: EchoManager):
        """Test that all categories have templates."""
        for category in EchoCategory:
            assert category in echo_manager.TEMPLATES

    def test_create_all_echo_categories(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test creating echoes for all categories."""
        for category in EchoCategory:
            echo = echo_manager.create_echo(
                category=category,
                node=test_node,
            )
            assert echo is not None
            assert echo.flavor_text is not None

    def test_template_base_difficulties(self, echo_manager: EchoManager):
        """Test that templates have correct base_difficulty values."""
        templates = echo_manager.TEMPLATES

        assert templates[EchoCategory.COMBAT].base_difficulty == 2
        assert templates[EchoCategory.DEATH].base_difficulty == 2
        assert templates[EchoCategory.EXPLORATION].base_difficulty == 2
        assert templates[EchoCategory.CRAFTING].base_difficulty == 3
        assert templates[EchoCategory.BOSS].base_difficulty == 1
        assert templates[EchoCategory.DISCOVERY].base_difficulty == 3
        assert templates[EchoCategory.SOCIAL].base_difficulty == 2
        assert templates[EchoCategory.MYSTERY].base_difficulty == 4
