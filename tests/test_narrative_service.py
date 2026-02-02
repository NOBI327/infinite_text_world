"""Tests for narrative service."""

from unittest.mock import MagicMock

from src.services.ai import MockProvider
from src.services.narrative_service import NarrativeService


class TestNarrativeService:
    """Tests for NarrativeService class."""

    def test_generate_look_with_mock(self):
        """Test generate_look with MockProvider."""
        provider = MockProvider()
        service = NarrativeService(provider)

        node_data = {"x": 0, "y": 0, "tier": 1}
        player_state = {"supply": 20}

        result = service.generate_look(node_data, player_state)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "[Mock]" in result

    def test_generate_look_fallback(self):
        """Test generate_look falls back when AI is not available."""
        provider = MagicMock()
        provider.is_available.return_value = False
        service = NarrativeService(provider)

        node_data = {"x": 5, "y": 10, "tier": 2}
        player_state = {"supply": 15}

        result = service.generate_look(node_data, player_state)

        assert "2 등급" in result
        assert "(5, 10)" in result
        provider.generate.assert_not_called()

    def test_generate_move_with_mock(self):
        """Test generate_move with MockProvider."""
        provider = MockProvider()
        service = NarrativeService(provider)

        from_node = {"x": 0, "y": 0}
        to_node = {"x": 0, "y": 1}

        result = service.generate_move(from_node, to_node, "북쪽")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "[Mock]" in result

    def test_generate_move_fallback(self):
        """Test generate_move falls back when AI is not available."""
        provider = MagicMock()
        provider.is_available.return_value = False
        service = NarrativeService(provider)

        from_node = {"x": 0, "y": 0}
        to_node = {"x": 0, "y": 1}

        result = service.generate_move(from_node, to_node, "북쪽")

        assert "북쪽" in result
        assert "이동했습니다" in result
        provider.generate.assert_not_called()

    def test_fallback_on_exception(self):
        """Test fallback is used when AI raises exception."""
        provider = MagicMock()
        provider.is_available.return_value = True
        provider.generate.side_effect = RuntimeError("API error")
        service = NarrativeService(provider)

        node_data = {"x": 3, "y": 7, "tier": 3}
        player_state = {"supply": 10}

        result = service.generate_look(node_data, player_state)

        assert "3 등급" in result
        assert "(3, 7)" in result
