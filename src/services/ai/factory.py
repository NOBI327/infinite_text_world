"""Factory for creating AI provider instances."""

from typing import Optional

from src.config import settings
from src.core.logging import get_logger
from src.services.ai.base import AIProvider
from src.services.ai.mock import MockProvider

logger = get_logger(__name__)


def get_ai_provider(provider_name: Optional[str] = None) -> AIProvider:
    """Get an AI provider instance.

    Args:
        provider_name: Optional provider name. If not specified,
                      uses AI_PROVIDER from config.

    Returns:
        An AIProvider instance.
    """
    name = provider_name or settings.AI_PROVIDER

    if name == "mock":
        logger.debug("Using MockProvider")
        return MockProvider()

    # Fallback to MockProvider for unknown providers
    logger.warning("Unknown provider '%s', falling back to MockProvider", name)
    return MockProvider()
