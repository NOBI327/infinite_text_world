"""Tests for core_rule module."""

from unittest.mock import patch

import pytest

from src.core.core_rule import (
    CharacterSheet,
    CheckResultTier,
    ResolutionEngine,
    StatType,
)


@pytest.fixture()
def character() -> CharacterSheet:
    """Create a test character."""
    return CharacterSheet(name="Test Hero", level=1)


@pytest.fixture()
def engine() -> ResolutionEngine:
    """Create a ResolutionEngine instance."""
    return ResolutionEngine()


class TestCharacterSheet:
    """Tests for CharacterSheet class."""

    def test_character_sheet_stats(self, character: CharacterSheet):
        """Test stat setting and retrieval."""
        # Default stats should be 1
        assert character.get_stat(StatType.WRITE) == 1
        assert character.get_stat(StatType.READ) == 1
        assert character.get_stat(StatType.EXEC) == 1
        assert character.get_stat(StatType.SUDO) == 1

        # Set stats
        character.set_stat(StatType.WRITE, 3)
        character.set_stat(StatType.READ, 2)

        assert character.get_stat(StatType.WRITE) == 3
        assert character.get_stat(StatType.READ) == 2

        # Can use string instead of enum
        character.set_stat("EXEC", 4)
        assert character.get_stat("EXEC") == 4

    def test_character_sheet_stats_minimum(self, character: CharacterSheet):
        """Test that stats cannot go below 1."""
        character.set_stat(StatType.WRITE, 0)
        assert character.get_stat(StatType.WRITE) == 1

        character.set_stat(StatType.WRITE, -5)
        assert character.get_stat(StatType.WRITE) == 1

    def test_resonance_damage(self, character: CharacterSheet):
        """Test resonance shield damage."""
        # Initial value should be 10
        assert character.resonance_shield["Thermal"] == 10

        # Apply damage
        result = character.damage_resonance("Thermal", 3)
        assert result == "DAMAGED"
        assert character.resonance_shield["Thermal"] == 7

        # Apply more damage
        result = character.damage_resonance("Thermal", 5)
        assert result == "DAMAGED"
        assert character.resonance_shield["Thermal"] == 2

        # Break the shield
        result = character.damage_resonance("Thermal", 5)
        assert result == "BROKEN"
        assert character.resonance_shield["Thermal"] == 0

    def test_resonance_damage_immune(self, character: CharacterSheet):
        """Test immunity when shield is None (Null)."""
        # Set shield to None for immunity
        character.resonance_shield["Esoteric"] = None

        result = character.damage_resonance("Esoteric", 100)
        assert result == "IMMUNE"
        assert character.resonance_shield["Esoteric"] is None

    def test_resonance_damage_all_types(self, character: CharacterSheet):
        """Test damage to all resonance types."""
        resonance_types = [
            "Kinetic",
            "Thermal",
            "Structural",
            "Bio",
            "Psyche",
            "Data",
            "Social",
            "Esoteric",
        ]

        for res_type in resonance_types:
            result = character.damage_resonance(res_type, 3)
            assert result == "DAMAGED"
            assert character.resonance_shield[res_type] == 7


class TestResolutionEngine:
    """Tests for ResolutionEngine class."""

    def test_resolve_check_success(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test successful check with mocked dice."""
        character.set_stat(StatType.WRITE, 3)

        # Mock dice to always roll 6 (guaranteed success)
        with patch("random.randint", return_value=6):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.WRITE,
                difficulty=2,
            )

        assert result.success is True
        assert result.hits >= result.required_hits
        assert result.tier in [
            CheckResultTier.SUCCESS,
            CheckResultTier.CRITICAL_SUCCESS,
        ]
        assert len(result.rolls) == 3  # 3 dice from WRITE stat

    def test_resolve_check_failure(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test failed check with mocked dice."""
        character.set_stat(StatType.READ, 2)

        # Mock dice to roll 2 (never succeeds, 5+ needed)
        with patch("random.randint", return_value=2):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.READ,
                difficulty=1,
            )

        assert result.success is False
        assert result.hits == 0
        assert result.tier == CheckResultTier.FAILURE
        assert len(result.rolls) == 2

    def test_critical_success(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test critical success condition (hits >= difficulty + 2)."""
        character.set_stat(StatType.EXEC, 5)

        # Mock dice to always roll 5 (all succeed)
        with patch("random.randint", return_value=5):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.EXEC,
                difficulty=2,  # Need 2, getting 5 hits = critical
            )

        assert result.success is True
        assert result.hits == 5
        assert result.tier == CheckResultTier.CRITICAL_SUCCESS
        assert "압도적" in result.narrative_hint

    def test_critical_failure(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test critical failure condition (0 hits and at least one 1)."""
        character.set_stat(StatType.SUDO, 3)

        # Mock dice to roll 1 (critical failure: no hits + ones present)
        with patch("random.randint", return_value=1):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.SUDO,
                difficulty=1,
            )

        assert result.success is False
        assert result.hits == 0
        assert result.tier == CheckResultTier.CRITICAL_FAILURE
        assert "치명적" in result.narrative_hint

    def test_resolve_check_with_bonus_dice(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test check with bonus dice."""
        character.set_stat(StatType.WRITE, 2)

        with patch("random.randint", return_value=6):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.WRITE,
                difficulty=1,
                bonus_dice=3,
            )

        # 2 (stat) + 3 (bonus) = 5 dice
        assert len(result.rolls) == 5

    def test_resolve_check_with_penalty(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test check with risk penalty."""
        character.set_stat(StatType.READ, 4)

        with patch("random.randint", return_value=6):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.READ,
                difficulty=1,
                risk_penalty=2,
            )

        # 4 (stat) - 2 (penalty) = 2 dice
        assert len(result.rolls) == 2

    def test_resolve_check_minimum_one_die(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test that at least 1 die is always rolled."""
        character.set_stat(StatType.EXEC, 1)

        with patch("random.randint", return_value=3):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.EXEC,
                difficulty=1,
                risk_penalty=10,  # Would result in -9 dice
            )

        # Should still roll at least 1 die
        assert len(result.rolls) >= 1

    def test_resolve_check_with_relevant_tags(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test check with relevant tags bonus."""
        character.set_stat(StatType.WRITE, 2)

        with patch("random.randint", return_value=5):
            result = engine.resolve_check(
                character=character,
                stat_type=StatType.WRITE,
                difficulty=1,
                relevant_tags=2,  # +2 dice from tags
            )

        # 2 (stat) + 2 (tags) = 4 dice
        assert len(result.rolls) == 4

    def test_check_result_structure(
        self, character: CharacterSheet, engine: ResolutionEngine
    ):
        """Test CheckResult has all required fields."""
        result = engine.resolve_check(
            character=character,
            stat_type=StatType.WRITE,
            difficulty=1,
        )

        assert hasattr(result, "success")
        assert hasattr(result, "tier")
        assert hasattr(result, "hits")
        assert hasattr(result, "required_hits")
        assert hasattr(result, "rolls")
        assert hasattr(result, "narrative_hint")

        assert isinstance(result.success, bool)
        assert isinstance(result.tier, CheckResultTier)
        assert isinstance(result.hits, int)
        assert isinstance(result.required_hits, int)
        assert isinstance(result.rolls, list)
        assert isinstance(result.narrative_hint, str)
