"""Mock AI provider for testing and fallback."""

from typing import Any, Optional

from src.services.ai.base import AIProvider


class MockProvider(AIProvider):
    """Mock AI provider that returns static text.

    Used for testing and as a fallback when no API key is configured.
    """

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "mock"

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return True

    def generate(self, prompt: str, context: Optional[dict[str, Any]] = None) -> str:
        """Generate mock text response.

        Args:
            prompt: The prompt (ignored in mock).
            context: Optional context (ignored in mock).

        Returns:
            Static mock response text.
        """
        return "[Mock] 당신은 알 수 없는 장소에 서 있습니다."
