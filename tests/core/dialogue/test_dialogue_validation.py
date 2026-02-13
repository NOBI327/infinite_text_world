"""META 검증 + Constraints 검증 테스트

#10-B 검증: 최소 13개 테스트 케이스.
"""

from src.core.dialogue.validation import (
    validate_meta,
    validate_dialogue_state,
    validate_relationship_delta,
    validate_memory_tags,
    validate_quest_seed_response,
    validate_trade_request,
    validate_gift_offered,
)
from src.core.dialogue.constraints import (
    validate_action_interpretation,
)


# ── validate_meta ──


class TestValidateMeta:
    """META 전체 검증"""

    def test_valid_meta_passes(self) -> None:
        """정상 META 통과"""
        raw = {
            "dialogue_state": {
                "wants_to_continue": True,
                "end_conversation": False,
                "topic_tags": ["greeting"],
            },
            "relationship_delta": {"affinity": 2, "reason": "friendly"},
            "memory_tags": ["met_player"],
            "quest_seed_response": None,
            "trade_request": None,
            "gift_offered": None,
        }
        result = validate_meta(raw)
        assert result["dialogue_state"]["wants_to_continue"] is True
        assert result["relationship_delta"]["affinity"] == 2
        assert result["memory_tags"] == ["met_player"]

    def test_missing_fields_get_defaults(self) -> None:
        """필수 필드 누락 시 기본값 적용"""
        result = validate_meta({})
        assert result["dialogue_state"]["wants_to_continue"] is True
        assert result["dialogue_state"]["end_conversation"] is False
        assert result["relationship_delta"]["affinity"] == 0
        assert result["memory_tags"] == []
        assert result["quest_seed_response"] is None

    def test_non_dict_returns_defaults(self) -> None:
        """dict가 아니면 전체 기본값"""
        result = validate_meta("not a dict")  # type: ignore[arg-type]
        assert result["dialogue_state"]["wants_to_continue"] is True
        assert result["relationship_delta"]["affinity"] == 0


# ── validate_dialogue_state ──


class TestValidateDialogueState:
    """dialogue_state 검증"""

    def test_none_returns_default(self) -> None:
        result = validate_dialogue_state(None)
        assert result["wants_to_continue"] is True
        assert result["end_conversation"] is False
        assert result["topic_tags"] == []

    def test_valid_state_preserved(self) -> None:
        state = {
            "wants_to_continue": False,
            "end_conversation": True,
            "topic_tags": ["trade"],
        }
        result = validate_dialogue_state(state)
        assert result["wants_to_continue"] is False
        assert result["end_conversation"] is True
        assert result["topic_tags"] == ["trade"]

    def test_non_bool_fields_use_default(self) -> None:
        state = {"wants_to_continue": "yes", "end_conversation": 1}
        result = validate_dialogue_state(state)
        assert result["wants_to_continue"] is True  # default
        assert result["end_conversation"] is False  # default


# ── validate_relationship_delta ──


class TestValidateRelationshipDelta:
    """relationship_delta 클램핑"""

    def test_clamp_high(self) -> None:
        result = validate_relationship_delta({"affinity": 10, "reason": "test"})
        assert result["affinity"] == 5

    def test_clamp_low(self) -> None:
        result = validate_relationship_delta({"affinity": -10, "reason": "test"})
        assert result["affinity"] == -5

    def test_normal_value_passes(self) -> None:
        result = validate_relationship_delta({"affinity": 3, "reason": "test"})
        assert result["affinity"] == 3

    def test_none_returns_default(self) -> None:
        result = validate_relationship_delta(None)
        assert result["affinity"] == 0
        assert result["reason"] == "none"

    def test_float_truncated_to_int(self) -> None:
        result = validate_relationship_delta({"affinity": 2.7, "reason": "x"})
        assert result["affinity"] == 2

    def test_non_numeric_affinity_defaults_to_zero(self) -> None:
        result = validate_relationship_delta({"affinity": "high", "reason": "x"})
        assert result["affinity"] == 0


# ── validate_memory_tags ──


class TestValidateMemoryTags:
    """memory_tags 검증"""

    def test_valid_tags(self) -> None:
        assert validate_memory_tags(["tag1", "tag2"]) == ["tag1", "tag2"]

    def test_truncate_long_tags(self) -> None:
        long_tag = "x" * 100
        result = validate_memory_tags([long_tag])
        assert len(result[0]) == 50

    def test_remove_non_strings(self) -> None:
        result = validate_memory_tags(["valid", 123, None, "also_valid"])
        assert result == ["valid", "also_valid"]

    def test_none_returns_empty(self) -> None:
        assert validate_memory_tags(None) == []

    def test_non_list_returns_empty(self) -> None:
        assert validate_memory_tags("not a list") == []  # type: ignore[arg-type]


# ── validate_quest_seed_response ──


class TestValidateQuestSeedResponse:
    """quest_seed_response 검증"""

    def test_accepted(self) -> None:
        assert validate_quest_seed_response("accepted") == "accepted"

    def test_ignored(self) -> None:
        assert validate_quest_seed_response("ignored") == "ignored"

    def test_none(self) -> None:
        assert validate_quest_seed_response(None) is None

    def test_invalid_value(self) -> None:
        assert validate_quest_seed_response("maybe") is None

    def test_non_string(self) -> None:
        assert validate_quest_seed_response(42) is None  # type: ignore[arg-type]


# ── validate_trade_request ──


class TestValidateTradeRequest:
    """trade_request 검증"""

    def test_valid_trade(self) -> None:
        trade = {"action": "buy", "item_instance_id": "item_001"}
        result = validate_trade_request(trade)
        assert result is not None
        assert result["action"] == "buy"

    def test_invalid_action(self) -> None:
        trade = {"action": "steal", "item_instance_id": "item_001"}
        assert validate_trade_request(trade) is None

    def test_missing_item_id(self) -> None:
        trade = {"action": "buy"}
        assert validate_trade_request(trade) is None

    def test_empty_item_id(self) -> None:
        trade = {"action": "buy", "item_instance_id": ""}
        assert validate_trade_request(trade) is None

    def test_none_returns_none(self) -> None:
        assert validate_trade_request(None) is None


# ── validate_gift_offered ──


class TestValidateGiftOffered:
    """gift_offered 검증"""

    def test_valid_gift(self) -> None:
        gift = {"item_instance_id": "item_002", "npc_reaction": "grateful"}
        result = validate_gift_offered(gift)
        assert result is not None

    def test_missing_item_id(self) -> None:
        assert validate_gift_offered({"npc_reaction": "grateful"}) is None

    def test_none_returns_none(self) -> None:
        assert validate_gift_offered(None) is None

    def test_non_dict_returns_none(self) -> None:
        assert validate_gift_offered("not a dict") is None  # type: ignore[arg-type]


# ── validate_action_interpretation ──


class TestValidateActionInterpretation:
    """Constraints 검증 — action_interpretation"""

    def test_none_returns_none(self) -> None:
        result = validate_action_interpretation(None, [], [], {})
        assert result is None

    def test_non_dict_returns_none(self) -> None:
        result = validate_action_interpretation(
            "bad",
            [],
            [],
            {},  # type: ignore[arg-type]
        )
        assert result is None

    def test_remove_unowned_axiom(self) -> None:
        """미보유 axiom 제거"""
        interp = {
            "stat": "EXEC",
            "modifiers": [
                {"source": "axiom_use", "axiom_id": "Fire_01", "value": 0.5},
                {"source": "axiom_counter", "axiom_id": "Water_03", "value": 1.0},
            ],
        }
        result = validate_action_interpretation(
            interp,
            pc_axioms=["Fire_01"],  # Water_03 미보유
            pc_items=[],
            pc_stats={"EXEC": 2},
        )
        assert result is not None
        assert len(result["modifiers"]) == 1
        assert result["modifiers"][0]["axiom_id"] == "Fire_01"

    def test_remove_unowned_item(self) -> None:
        """미보유 item 제거"""
        interp = {
            "stat": "EXEC",
            "modifiers": [
                {"source": "item_use", "item_id": "rope", "value": 0.5},
                {"source": "item_boost", "item_id": "bomb", "value": 1.0},
            ],
        }
        result = validate_action_interpretation(
            interp,
            pc_axioms=[],
            pc_items=["rope"],  # bomb 미보유
            pc_stats={"EXEC": 2},
        )
        assert result is not None
        assert len(result["modifiers"]) == 1
        assert result["modifiers"][0]["item_id"] == "rope"

    def test_clamp_modifier_value(self) -> None:
        """modifier value -2.0~+2.0 클램핑"""
        interp = {
            "stat": "EXEC",
            "modifiers": [
                {"source": "skill", "value": 5.0},
                {"source": "penalty", "value": -5.0},
            ],
        }
        result = validate_action_interpretation(interp, [], [], {})
        assert result is not None
        assert result["modifiers"][0]["value"] == 2.0
        assert result["modifiers"][1]["value"] == -2.0

    def test_invalid_stat_defaults_to_exec(self) -> None:
        """잘못된 stat → EXEC"""
        interp = {"stat": "MAGIC", "modifiers": []}
        result = validate_action_interpretation(interp, [], [], {})
        assert result is not None
        assert result["stat"] == "EXEC"

    def test_valid_stats_preserved(self) -> None:
        """유효한 stat 유지"""
        for stat in ("WRITE", "READ", "EXEC", "SUDO"):
            interp = {"stat": stat, "modifiers": []}
            result = validate_action_interpretation(interp, [], [], {})
            assert result is not None
            assert result["stat"] == stat

    def test_non_axiom_non_item_modifiers_kept(self) -> None:
        """axiom/item이 아닌 modifier는 유지"""
        interp = {
            "stat": "EXEC",
            "modifiers": [
                {"source": "prior_investigation", "value": 1.0, "reason": "bonus"},
            ],
        }
        result = validate_action_interpretation(interp, [], [], {})
        assert result is not None
        assert len(result["modifiers"]) == 1

    def test_does_not_mutate_original(self) -> None:
        """원본 dict를 변경하지 않음"""
        interp = {
            "stat": "MAGIC",
            "modifiers": [{"source": "axiom_use", "axiom_id": "X", "value": 9.0}],
        }
        original_stat = interp["stat"]
        validate_action_interpretation(interp, [], [], {})
        assert interp["stat"] == original_stat  # 원본 유지
