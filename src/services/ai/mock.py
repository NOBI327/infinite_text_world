"""Mock AI provider for testing and fallback."""

import json
from typing import Any, Optional

from src.services.ai.base import AIProvider

MOCK_DIALOGUE_RESPONSE = json.dumps(
    {
        "narrative": "NPCが短く答える。「...そうだな。」",
        "meta": {
            "dialogue_state": {
                "wants_to_continue": True,
                "end_conversation": False,
                "topic_tags": [],
            },
            "relationship_delta": {"affinity": 0, "reason": "none"},
            "memory_tags": [],
            "quest_seed_response": None,
            "quest_details": None,
            "action_interpretation": None,
            "resolution_comment": None,
            "trade_request": None,
            "gift_offered": None,
            "npc_internal": {"emotional_state": "neutral", "hidden_intent": None},
        },
    },
    ensure_ascii=False,
)


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

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate mock text response.

        Returns JSON mock when prompt contains "JSON", otherwise static text.
        """
        if "JSON" in prompt or (system_prompt and "JSON" in system_prompt):
            return MOCK_DIALOGUE_RESPONSE
        return "[Mock] 당신은 알 수 없는 장소에 서 있습니다."
