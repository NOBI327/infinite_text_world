"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class AIProvider(ABC):
    """Abstract base class for AI providers.

    All AI providers must implement this interface to ensure
    consistent behavior across different LLM APIs.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate text based on the prompt.

        Args:
            prompt: The user prompt to send to the AI model.
            system_prompt: Optional system prompt for role/instruction.
            max_tokens: Maximum tokens for the response.
            context: Optional context dictionary (deprecated, for backward compat).

        Returns:
            Generated text response.
        """
        ...
