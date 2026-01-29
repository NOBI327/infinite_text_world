"""Tests for echo_system module."""

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
        assert echo.base_dc == 10  # Combat base DC
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

    def test_create_echo_with_dc_modifier(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test Echo creation with DC modifier."""
        # Mystery has base DC 20
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,
            node=test_node,
            dc_modifier=5,
        )

        assert echo.base_dc == 25  # 20 + 5

    def test_calculate_investigation_dc(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test DC calculation with time decay and fame bonus."""
        echo = echo_manager.create_echo(
            category=EchoCategory.EXPLORATION,
            node=test_node,
        )

        # Test with fame bonus
        dc_info = echo_manager.calculate_investigation_dc(
            echo=echo,
            investigator_fame=50,  # -5 DC bonus (50 // 10)
            bonus_modifiers=2,
        )

        assert "base_dc" in dc_info
        assert "time_decay" in dc_info
        assert "fame_bonus" in dc_info
        assert "modifiers" in dc_info
        assert "final_dc" in dc_info

        # Fame bonus should be 5 (50 // 10)
        assert dc_info["fame_bonus"] == 5

        # Final DC should be reduced by fame and modifiers
        expected_dc = echo.base_dc + dc_info["time_decay"] - 5 - 2
        expected_dc = max(5, expected_dc)  # Minimum DC is 5
        assert dc_info["final_dc"] == expected_dc

    def test_calculate_investigation_dc_time_decay(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test that time decay increases DC."""
        # Create echo with old timestamp
        old_timestamp = (datetime.utcnow() - timedelta(days=5)).isoformat()
        echo = Echo(
            echo_type=EchoType.SHORT.value,
            visibility=EchoVisibility.HIDDEN.value,
            base_dc=10,
            timestamp=old_timestamp,
            flavor_text="Old echo",
            source_player_id=None,
        )

        dc_info = echo_manager.calculate_investigation_dc(echo)

        # 5 days passed = +5 time decay
        assert dc_info["days_passed"] == 5
        assert dc_info["time_decay"] == 5

    def test_investigate_success(self, echo_manager: EchoManager, test_node: MapNode):
        """Test successful investigation."""
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,
            node=test_node,
            source_player_id="player_xyz",
        )

        # High roll should succeed (base DC 10 for combat)
        result = echo_manager.investigate(
            echo=echo,
            roll=20,
            investigator_fame=0,
            bonus_modifiers=0,
        )

        assert result["success"] is True
        assert "discovered_info" in result
        assert result["discovered_info"]["flavor"] == echo.flavor_text
        assert result["margin"] >= 0

    def test_investigate_failure(self, echo_manager: EchoManager, test_node: MapNode):
        """Test failed investigation."""
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,  # High DC (20)
            node=test_node,
        )

        # Low roll should fail
        result = echo_manager.investigate(
            echo=echo,
            roll=5,
            investigator_fame=0,
            bonus_modifiers=0,
        )

        assert result["success"] is False
        assert "message" in result
        assert "discovered_info" not in result

    def test_investigate_critical_failure(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test critical failure with penalty (margin <= -5)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.MYSTERY,  # High DC (20)
            node=test_node,
        )

        # Very low roll = critical failure
        result = echo_manager.investigate(
            echo=echo,
            roll=5,  # DC is at least 20, so margin is -15 or worse
            investigator_fame=0,
            bonus_modifiers=0,
        )

        assert result["success"] is False
        assert result["margin"] <= -5
        assert "penalty" in result
        assert "페널티" in result["penalty"]

    def test_investigate_critical_success(
        self, echo_manager: EchoManager, test_node: MapNode
    ):
        """Test critical success with bonus info (margin >= 5)."""
        echo = echo_manager.create_echo(
            category=EchoCategory.COMBAT,  # DC 10
            node=test_node,
            source_player_id="player_abc",
        )

        # High roll = critical success
        result = echo_manager.investigate(
            echo=echo,
            roll=20,  # margin = 20 - 10 = 10
            investigator_fame=0,
            bonus_modifiers=0,
        )

        assert result["success"] is True
        assert result["margin"] >= 5
        assert "bonus_info" in result
        # Should reveal partial player ID
        assert "source_player_hint" in result

    def test_decay_echoes(self, echo_manager: EchoManager, test_node: MapNode):
        """Test Short Echo decay over time."""
        # Create a short echo with old timestamp (beyond decay days)
        old_timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()
        short_echo = Echo(
            echo_type=EchoType.SHORT.value,
            visibility=EchoVisibility.PUBLIC.value,
            base_dc=10,
            timestamp=old_timestamp,
            flavor_text="Old short echo",
            source_player_id=None,
        )
        test_node.echoes.append(short_echo)

        # Create a long echo (should not decay)
        long_echo = Echo(
            echo_type=EchoType.LONG.value,
            visibility=EchoVisibility.PUBLIC.value,
            base_dc=5,
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
