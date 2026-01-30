"""Tests for AI provider module."""

from src.services.ai import AIProvider, MockProvider, get_ai_provider


class TestMockProvider:
    """Tests for MockProvider class."""

    def test_mock_provider_name(self):
        """Test that MockProvider name is 'mock'."""
        provider = MockProvider()
        assert provider.name == "mock"

    def test_mock_provider_is_available(self):
        """Test that MockProvider is always available."""
        provider = MockProvider()
        assert provider.is_available() is True

    def test_mock_provider_generate(self):
        """Test that MockProvider generates a string response."""
        provider = MockProvider()
        result = provider.generate("test prompt")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "[Mock]" in result


class TestAIProviderFactory:
    """Tests for AI provider factory."""

    def test_factory_returns_mock_by_default(self):
        """Test that factory returns MockProvider by default."""
        provider = get_ai_provider()

        assert isinstance(provider, AIProvider)
        assert isinstance(provider, MockProvider)
        assert provider.name == "mock"
