"""Tests for AI provider module."""

from unittest.mock import MagicMock, patch

from src.services.ai import AIProvider, GeminiProvider, MockProvider, get_ai_provider


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


class TestGeminiProvider:
    """Tests for GeminiProvider class."""

    @patch("src.services.ai.gemini.genai")
    def test_gemini_provider_name(self, mock_genai: MagicMock):
        """Test that GeminiProvider name is 'gemini'."""
        provider = GeminiProvider(api_key="test_key")
        assert provider.name == "gemini"

    @patch("src.services.ai.gemini.genai")
    def test_gemini_provider_not_available_without_key(self, mock_genai: MagicMock):
        """Test that GeminiProvider is not available without API key."""
        provider = GeminiProvider(api_key="")
        assert provider.is_available() is False

    @patch("src.services.ai.gemini.genai")
    def test_gemini_provider_available_with_key(self, mock_genai: MagicMock):
        """Test that GeminiProvider is available with API key."""
        provider = GeminiProvider(api_key="test_key")
        assert provider.is_available() is True


class TestAIProviderFactory:
    """Tests for AI provider factory."""

    def test_factory_returns_mock_by_default(self):
        """Test that factory returns MockProvider by default."""
        provider = get_ai_provider()

        assert isinstance(provider, AIProvider)
        assert isinstance(provider, MockProvider)
        assert provider.name == "mock"

    @patch("src.services.ai.factory.settings")
    @patch("src.services.ai.gemini.genai")
    def test_factory_returns_gemini_with_config(
        self, mock_genai: MagicMock, mock_settings: MagicMock
    ):
        """Test that factory returns GeminiProvider when configured."""
        mock_settings.AI_PROVIDER = "gemini"
        mock_settings.AI_API_KEY = "test_key"
        mock_settings.AI_MODEL = "gemini-2.0-flash"

        provider = get_ai_provider()

        assert isinstance(provider, GeminiProvider)
        assert provider.name == "gemini"

    @patch("src.services.ai.factory.settings")
    def test_factory_fallback_without_key(self, mock_settings: MagicMock):
        """Test that factory falls back to MockProvider without API key."""
        mock_settings.AI_PROVIDER = "gemini"
        mock_settings.AI_API_KEY = None

        provider = get_ai_provider()

        assert isinstance(provider, MockProvider)
        assert provider.name == "mock"
