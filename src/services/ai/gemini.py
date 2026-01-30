"""Gemini AI provider implementation."""

from typing import Any, Optional

import google.generativeai as genai

from src.core.logging import get_logger
from src.services.ai.base import AIProvider

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    """AI provider using Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        """Initialize the Gemini provider.

        Args:
            api_key: Google API key for Gemini.
            model: Model name to use.
        """
        self._api_key = api_key
        self._model_name = model
        self._model = None

        if self._api_key:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
            logger.info("GeminiProvider initialized with model: %s", self._model_name)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "gemini"

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return bool(self._api_key) and self._model is not None

    def generate(self, prompt: str, context: Optional[dict[str, Any]] = None) -> str:
        """Generate text using Gemini API.

        Args:
            prompt: The prompt to send to Gemini.
            context: Optional context dictionary (currently unused).

        Returns:
            Generated text response.

        Raises:
            RuntimeError: If API call fails or provider is not available.
        """
        if not self.is_available():
            raise RuntimeError("GeminiProvider is not available. Check API key.")

        try:
            response = self._model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            raise RuntimeError(f"Gemini API error: {e}") from e
