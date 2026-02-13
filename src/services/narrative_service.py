"""Narrative service for generating game descriptions using AI.

narrative-service.md v2.0 대응 — 단일 관문(single gateway).
"""

from typing import Any

from src.core.logging import get_logger
from src.services.ai.base import AIProvider
from src.services.narrative_parser import ResponseParser
from src.services.narrative_prompts import PromptBuilder
from src.services.narrative_safety import ContentSafetyFilter, NarrationManager
from src.services.narrative_types import (
    DialoguePromptContext,
    NarrativeConfig,
    NarrativeRequestType,
    NarrativeResult,
    QuestSeedPromptContext,
)

logger = get_logger(__name__)

# 폴백 템플릿 (3단계)
FALLBACK_TEMPLATES: dict[NarrativeRequestType, str | None] = {
    NarrativeRequestType.LOOK: "あなたは{node_name}にいる。周囲を見渡す。",
    NarrativeRequestType.MOVE: "{direction}に進む。",
    NarrativeRequestType.DIALOGUE: (
        '{{"narrative": "{npc_name}が短く答える。「...そうだな。」",'
        ' "meta": {{"dialogue_state": {{"wants_to_continue": true,'
        ' "end_conversation": false, "topic_tags": []}},'
        ' "relationship_delta": {{"affinity": 0, "reason": "none"}},'
        ' "memory_tags": []}}}}'
    ),
    NarrativeRequestType.QUEST_SEED: None,
    NarrativeRequestType.IMPRESSION_TAG: "neutral",
}


class NarrativeService:
    """Service for generating game narratives using AI providers.

    모든 LLM 호출의 단일 관문.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        config: NarrativeConfig | None = None,
    ) -> None:
        """Initialize the narrative service.

        Args:
            ai_provider: The AI provider to use for text generation.
            config: Optional narrative configuration.
        """
        self.ai = ai_provider
        self._config = config or NarrativeConfig()
        self._narration_manager = NarrationManager(self._config.default_narration_level)
        self._safety = ContentSafetyFilter(self._narration_manager)
        self._prompt_builder = PromptBuilder(self._config, self._safety)
        self._parser = ResponseParser()

    # === 기존 호환 ===

    def _build_look_prompt(
        self, node_data: dict[str, Any], player_state: dict[str, Any]
    ) -> str:
        """Build a prompt for look action narrative (legacy compat)."""
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
        """Generate fallback narrative for look action."""
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        tier = node_data.get("tier", 1)
        return f"당신은 {tier} 등급의 지역에 서 있습니다. 좌표는 ({x}, {y})입니다."

    def generate_look(
        self, node_data: dict[str, Any], player_state: dict[str, Any]
    ) -> str:
        """Generate narrative for look action."""
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
        """Build a prompt for move action narrative (legacy compat)."""
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
        """Generate fallback narrative for move action."""
        return f"당신은 {direction} 방향으로 이동했습니다. 새로운 지역에 도착했습니다."

    def generate_move(
        self, from_node: dict[str, Any], to_node: dict[str, Any], direction: str
    ) -> str:
        """Generate narrative for move action."""
        if not self.ai.is_available():
            return self._fallback_move(direction, to_node)

        try:
            prompt = self._build_move_prompt(from_node, to_node, direction)
            return self.ai.generate(prompt)
        except Exception as e:
            logger.warning("AI generation failed, using fallback: %s", e)
            return self._fallback_move(direction, to_node)

    # === 신규: 대화 ===

    def generate_dialogue_response(self, ctx: DialoguePromptContext) -> NarrativeResult:
        """대화 턴 1회의 LLM 응답 생성.

        dialogue_service가 컨텍스트를 조립하여 전달한다.
        반환: narrative(플레이어용) + raw_meta(검증 전).
        """
        built = self._prompt_builder.build_dialogue(ctx)
        raw = self._call_llm(
            NarrativeRequestType.DIALOGUE,
            built.user_prompt,
            built.system_prompt,
            built.max_tokens,
            expect_json=True,
            fallback_context={"npc_name": ctx.npc_name},
        )
        narrative, meta, success = self._parser.parse_dual(raw)
        return NarrativeResult(
            narrative=narrative,
            raw_meta=meta,
            parse_success=success,
        )

    # === 신규: 퀘스트 시드 ===

    def generate_quest_seed(self, ctx: QuestSeedPromptContext) -> NarrativeResult:
        """퀘스트 시드 내용 생성."""
        built = self._prompt_builder.build_quest_seed(ctx)
        raw = self._call_llm(
            NarrativeRequestType.QUEST_SEED,
            built.user_prompt,
            built.system_prompt,
            built.max_tokens,
            expect_json=True,
            fallback_context={"npc_name": ctx.npc_name},
        )
        narrative, meta, success = self._parser.parse_dual(raw)
        return NarrativeResult(
            narrative=narrative,
            raw_meta=meta,
            parse_success=success,
        )

    # === 신규: NPC 한줄평 ===

    def generate_impression_tag(
        self, summary: str, quest_result: dict | None = None
    ) -> str:
        """대화 종료 시 NPC 한줄평 태그 생성."""
        built = self._prompt_builder.build_impression_tag(summary, quest_result)
        raw = self._call_llm(
            NarrativeRequestType.IMPRESSION_TAG,
            built.user_prompt,
            built.system_prompt,
            built.max_tokens,
        )
        return self._parser.parse_text(raw)

    # === 내부 ===

    def _call_llm(
        self,
        request_type: NarrativeRequestType,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        expect_json: bool = False,
        fallback_context: dict[str, str] | None = None,
    ) -> str:
        """LLM 호출 + 폴백 처리.

        1단계: 통상 호출
        2단계: 간소화 프롬프트 재시도
        3단계: Python 템플릿 반환
        """
        # 1단계: 통상 호출
        if self.ai.is_available():
            try:
                return self.ai.generate(
                    prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(
                    "LLM call failed for %s (stage 1): %s", request_type.value, e
                )

            # 2단계: 간소화 재시도
            try:
                return self.ai.generate(
                    prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(
                    "LLM call failed for %s (stage 2): %s", request_type.value, e
                )

        # 3단계: 폴백 템플릿
        template = FALLBACK_TEMPLATES.get(request_type)
        if template is None:
            return ""

        ctx = fallback_context or {}
        try:
            return template.format(**ctx)
        except KeyError:
            return template
