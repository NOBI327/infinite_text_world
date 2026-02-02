"""Narrative service for generating game descriptions using AI."""

from typing import Any

from src.core.logging import get_logger
from src.services.ai.base import AIProvider

logger = get_logger(__name__)


class NarrativeService:
    """Service for generating game narratives using AI providers."""

    def __init__(self, ai_provider: AIProvider) -> None:
        """Initialize the narrative service.

        Args:
            ai_provider: The AI provider to use for text generation.
        """
        self.ai = ai_provider

    def _build_look_prompt(
        self, node_data: dict[str, Any], player_state: dict[str, Any]
    ) -> str:
        """Build a prompt for look action narrative.

        Args:
            node_data: Current node information.
            player_state: Current player state.

        Returns:
            Formatted prompt string.
        """
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        tier = node_data.get("tier", 1)

        return f"""당신은 텍스트 RPG의 게임 마스터입니다.
플레이어가 현재 위치를 관찰합니다.

[위치 정보]
- 좌표: {x}, {y}
- 등급: {tier}

2-3문장으로 분위기 있는 장소 묘사를 해주세요.
한국어로 작성하세요."""

    def _fallback_look(self, node_data: dict[str, Any]) -> str:
        """Generate fallback narrative for look action.

        Args:
            node_data: Current node information.

        Returns:
            Default narrative string.
        """
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        tier = node_data.get("tier", 1)

        return f"당신은 {tier} 등급의 지역에 서 있습니다. 좌표는 ({x}, {y})입니다."

    def generate_look(
        self, node_data: dict[str, Any], player_state: dict[str, Any]
    ) -> str:
        """Generate narrative for look action.

        Args:
            node_data: Current node information.
            player_state: Current player state.

        Returns:
            Generated narrative string.
        """
        if not self.ai.is_available():
            return self._fallback_look(node_data)

        try:
            prompt = self._build_look_prompt(node_data, player_state)
            return self.ai.generate(prompt)
        except Exception as e:
            logger.warning("AI generation failed, using fallback: %s", e)
            return self._fallback_look(node_data)

    def _build_move_prompt(
        self, from_node: dict[str, Any], to_node: dict[str, Any], direction: str
    ) -> str:
        """Build a prompt for move action narrative.

        Args:
            from_node: Origin node information.
            to_node: Destination node information.
            direction: Direction of movement.

        Returns:
            Formatted prompt string.
        """
        from_x = from_node.get("x", 0)
        from_y = from_node.get("y", 0)
        to_x = to_node.get("x", 0)
        to_y = to_node.get("y", 0)

        return f"""당신은 텍스트 RPG의 게임 마스터입니다.
플레이어가 {direction} 방향으로 이동했습니다.

[이동 정보]
- 출발: ({from_x}, {from_y})
- 도착: ({to_x}, {to_y})

1-2문장으로 이동 묘사를 해주세요.
한국어로 작성하세요."""

    def _fallback_move(self, direction: str, to_node: dict[str, Any]) -> str:
        """Generate fallback narrative for move action.

        Args:
            direction: Direction of movement.
            to_node: Destination node information.

        Returns:
            Default narrative string.
        """
        return f"당신은 {direction} 방향으로 이동했습니다. 새로운 지역에 도착했습니다."

    def generate_move(
        self, from_node: dict[str, Any], to_node: dict[str, Any], direction: str
    ) -> str:
        """Generate narrative for move action.

        Args:
            from_node: Origin node information.
            to_node: Destination node information.
            direction: Direction of movement.

        Returns:
            Generated narrative string.
        """
        if not self.ai.is_available():
            return self._fallback_move(direction, to_node)

        try:
            prompt = self._build_move_prompt(from_node, to_node, direction)
            return self.ai.generate(prompt)
        except Exception as e:
            logger.warning("AI generation failed, using fallback: %s", e)
            return self._fallback_move(direction, to_node)
