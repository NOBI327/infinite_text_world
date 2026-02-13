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

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate text using Gemini API.

        Args:
            prompt: The user prompt to send to Gemini.
            system_prompt: Optional system instruction for Gemini.
            max_tokens: Maximum output tokens.
            context: Optional context dictionary (deprecated).

        Returns:
            Generated text response.

        Raises:
            RuntimeError: If API call fails or provider is not available.
        """
        if not self.is_available():
            raise RuntimeError("GeminiProvider is not available. Check API key.")

        assert self._model is not None

        # Rebuild model with system instruction if provided
        model = self._model
        if system_prompt:
            model = genai.GenerativeModel(
                self._model_name,
                system_instruction=system_prompt,
            )

        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
        )

        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            result: str = response.text.strip()
            return result
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            raise RuntimeError(f"Gemini API error: {e}") from e
