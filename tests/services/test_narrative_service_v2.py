"""NarrativeService v2 테스트

#10-C 검증: 최소 12개 테스트 케이스.
"""

import json
from unittest.mock import MagicMock

from src.services.ai import MockProvider
from src.services.narrative_parser import ResponseParser
from src.services.narrative_prompts import PromptBuilder
from src.services.narrative_safety import (
    ContentSafetyFilter,
    NarrationManager,
)
from src.services.narrative_service import NarrativeService
from src.services.narrative_types import (
    DialoguePromptContext,
    NarrativeConfig,
    QuestSeedPromptContext,
)


# ── ResponseParser ──


class TestResponseParserDual:
    """ResponseParser.parse_dual 테스트"""

    def test_parse_full_json(self) -> None:
        """정상 JSON 파싱"""
        parser = ResponseParser()
        raw = json.dumps(
            {
                "narrative": "NPCが答える。",
                "meta": {"dialogue_state": {"wants_to_continue": True}},
            },
            ensure_ascii=False,
        )
        narrative, meta, success = parser.parse_dual(raw)
        assert success is True
        assert narrative == "NPCが答える。"
        assert meta["dialogue_state"]["wants_to_continue"] is True

    def test_parse_json_code_block(self) -> None:
        """```json 블록 파싱"""
        parser = ResponseParser()
        raw = """Some text before
```json
{"narrative": "テスト応答", "meta": {"key": "value"}}
```
Some text after"""
        narrative, meta, success = parser.parse_dual(raw)
        assert success is True
        assert narrative == "テスト応答"
        assert meta["key"] == "value"

    def test_parse_failure_returns_raw(self) -> None:
        """파싱 실패 → (raw, {}, False)"""
        parser = ResponseParser()
        raw = "This is not JSON at all."
        narrative, meta, success = parser.parse_dual(raw)
        assert success is False
        assert narrative == raw
        assert meta == {}

    def test_parse_missing_narrative_key(self) -> None:
        """narrative 키 없으면 raw 전체를 narrative로"""
        parser = ResponseParser()
        raw = json.dumps({"meta": {"key": "val"}})
        narrative, meta, success = parser.parse_dual(raw)
        assert success is True
        assert narrative == raw.strip()
        assert meta["key"] == "val"

    def test_parse_missing_meta_key(self) -> None:
        """meta 키 없으면 빈 dict"""
        parser = ResponseParser()
        raw = json.dumps({"narrative": "hello"})
        narrative, meta, success = parser.parse_dual(raw)
        assert success is True
        assert narrative == "hello"
        assert meta == {}


class TestResponseParserText:
    """ResponseParser.parse_text 테스트"""

    def test_parse_text_strips(self) -> None:
        """앞뒤 공백 strip"""
        parser = ResponseParser()
        assert parser.parse_text("  hello world  ") == "hello world"


# ── NarrationManager ──


class TestNarrationManager:
    """NarrationManager 테스트"""

    def test_default_level(self) -> None:
        """기본 레벨 반환"""
        manager = NarrationManager("moderate")
        assert manager.get_start_level("violence") == "moderate"

    def test_record_and_recall(self) -> None:
        """폴백 기록 후 해당 카테고리에서 기록된 레벨 반환"""
        manager = NarrationManager("moderate")
        manager.record_fallback("violence", "fade_out")
        assert manager.get_start_level("violence") == "fade_out"
        assert manager.get_start_level("other") == "moderate"


# ── PromptBuilder ──


class TestPromptBuilder:
    """PromptBuilder 테스트"""

    def _make_builder(self) -> PromptBuilder:
        config = NarrativeConfig()
        manager = NarrationManager()
        safety = ContentSafetyFilter(manager)
        return PromptBuilder(config, safety)

    def test_build_dialogue_expect_json(self) -> None:
        """build_dialogue → expect_json=True"""
        builder = self._make_builder()
        ctx = DialoguePromptContext(
            npc_name="Hans",
            pc_input="こんにちは",
        )
        result = builder.build_dialogue(ctx)
        assert result.expect_json is True
        assert "Hans" in result.user_prompt
        assert "こんにちは" in result.user_prompt
        assert result.max_tokens == 500  # open phase

    def test_build_quest_seed_expect_json(self) -> None:
        """build_quest_seed → expect_json=True"""
        builder = self._make_builder()
        ctx = QuestSeedPromptContext(
            npc_name="Merchant",
            seed_type="rumor",
        )
        result = builder.build_quest_seed(ctx)
        assert result.expect_json is True
        assert result.max_tokens == 400

    def test_build_impression_tag_max_tokens(self) -> None:
        """build_impression_tag → max_tokens=50"""
        builder = self._make_builder()
        result = builder.build_impression_tag("player helped NPC", None)
        assert result.max_tokens == 50

    def test_build_look_max_tokens(self) -> None:
        """build_look → max_tokens=300"""
        builder = self._make_builder()
        result = builder.build_look({"x": 0, "y": 0, "tier": 1}, {})
        assert result.max_tokens == 300

    def test_build_move_max_tokens(self) -> None:
        """build_move → max_tokens=150"""
        builder = self._make_builder()
        result = builder.build_move({"x": 0, "y": 0}, {"x": 1, "y": 0}, "north")
        assert result.max_tokens == 150


# ── NarrativeService ──


class TestNarrativeServiceDialogue:
    """NarrativeService.generate_dialogue_response 테스트"""

    def test_dialogue_with_mock(self) -> None:
        """MockProvider로 정상 대화 흐름"""
        provider = MockProvider()
        service = NarrativeService(provider)
        ctx = DialoguePromptContext(
            npc_name="Hans",
            pc_input="こんにちは",
        )
        result = service.generate_dialogue_response(ctx)
        assert result.parse_success is True
        assert "NPCが短く答える" in result.narrative
        assert isinstance(result.raw_meta, dict)


class TestNarrativeServiceImpressionTag:
    """NarrativeService.generate_impression_tag 테스트"""

    def test_impression_tag_with_mock(self) -> None:
        """MockProvider로 한줄평 생성"""
        provider = MockProvider()
        service = NarrativeService(provider)
        result = service.generate_impression_tag("player was helpful")
        assert isinstance(result, str)
        assert len(result) > 0


class TestNarrativeServiceLookCompat:
    """generate_look 기존 호환 테스트"""

    def test_look_compat(self) -> None:
        """기존 generate_look 호환 유지"""
        provider = MockProvider()
        service = NarrativeService(provider)
        result = service.generate_look({"x": 0, "y": 0, "tier": 1}, {"supply": 10})
        assert isinstance(result, str)
        assert len(result) > 0


class TestCallLlmFallback:
    """_call_llm 폴백 테스트"""

    def test_fallback_on_unavailable_provider(self) -> None:
        """Provider 비가용 시 폴백 템플릿 반환"""
        provider = MagicMock()
        provider.is_available.return_value = False
        service = NarrativeService(provider)

        from src.services.narrative_types import NarrativeRequestType

        result = service._call_llm(
            NarrativeRequestType.IMPRESSION_TAG,
            "test",
            "system",
            50,
        )
        assert result == "neutral"

    def test_fallback_on_exception(self) -> None:
        """Provider 예외 시 폴백 템플릿 반환"""
        provider = MagicMock()
        provider.is_available.return_value = True
        provider.generate.side_effect = RuntimeError("API error")
        service = NarrativeService(provider)

        from src.services.narrative_types import NarrativeRequestType

        result = service._call_llm(
            NarrativeRequestType.MOVE,
            "test",
            "system",
            150,
            fallback_context={"direction": "北"},
        )
        assert "北" in result

    def test_quest_seed_fallback_is_empty(self) -> None:
        """퀘스트 시드 폴백 → 빈 문자열 (시드 없음 처리)"""
        provider = MagicMock()
        provider.is_available.return_value = False
        service = NarrativeService(provider)

        from src.services.narrative_types import NarrativeRequestType

        result = service._call_llm(
            NarrativeRequestType.QUEST_SEED,
            "test",
            "system",
            400,
        )
        assert result == ""
