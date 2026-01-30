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
    def generate(self, prompt: str, context: Optional[dict[str, Any]] = None) -> str:
        """Generate text based on the prompt and context.

        Args:
            prompt: The prompt to send to the AI model.
            context: Optional context dictionary for additional parameters.

        Returns:
            Generated text response.
        """
        ...
