"""META JSON 사후 검증 파이프라인

dialogue-system.md 섹션 6.2 대응.
보정 우선, 재생성 금지 원칙.
"""

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# --- 기본값 ---
DEFAULT_DIALOGUE_STATE: dict = {
    "wants_to_continue": True,
    "end_conversation": False,
    "topic_tags": [],
}

DEFAULT_RELATIONSHIP_DELTA: dict = {
    "affinity": 0,
    "reason": "none",
}

# --- 허용값 ---
VALID_SEED_RESPONSES = {"accepted", "ignored"}
VALID_TRADE_ACTIONS = {"buy", "sell", "negotiate", "confirm", "reject"}


def validate_meta(raw_meta: dict) -> dict:
    """META 전체 검증. 보정된 meta dict 반환.

    항상 검증:
    - dialogue_state: 필수 필드 존재 → 없으면 기본값
    - relationship_delta.affinity: -5 ~ +5 클램핑
    - memory_tags: list[str], 각 50자 이내

    조건부 검증:
    - quest_seed_response: "accepted"|"ignored"|null
    - trade_request: action 허용값 확인
    - gift_offered: 기본 구조 검증
    """
    if not isinstance(raw_meta, dict):
        logger.warning("META is not a dict, using defaults")
        return _build_default_meta()

    meta = deepcopy(raw_meta)

    # 항상 검증
    meta["dialogue_state"] = validate_dialogue_state(meta.get("dialogue_state"))
    meta["relationship_delta"] = validate_relationship_delta(
        meta.get("relationship_delta")
    )
    meta["memory_tags"] = validate_memory_tags(meta.get("memory_tags"))

    # 조건부 검증
    meta["quest_seed_response"] = validate_quest_seed_response(
        meta.get("quest_seed_response")
    )
    meta["trade_request"] = validate_trade_request(meta.get("trade_request"))
    meta["gift_offered"] = validate_gift_offered(meta.get("gift_offered"))

    return meta


def validate_dialogue_state(state: dict | None) -> dict:
    """dialogue_state 필수 필드 검증 + 기본값"""
    if not isinstance(state, dict):
        return dict(DEFAULT_DIALOGUE_STATE)

    result = dict(DEFAULT_DIALOGUE_STATE)

    if isinstance(state.get("wants_to_continue"), bool):
        result["wants_to_continue"] = state["wants_to_continue"]

    if isinstance(state.get("end_conversation"), bool):
        result["end_conversation"] = state["end_conversation"]

    if isinstance(state.get("topic_tags"), list):
        result["topic_tags"] = [
            str(t) for t in state["topic_tags"] if isinstance(t, str)
        ]

    return result


def validate_relationship_delta(delta: dict | None) -> dict:
    """affinity -5~+5 클램핑"""
    if not isinstance(delta, dict):
        return dict(DEFAULT_RELATIONSHIP_DELTA)

    result = dict(DEFAULT_RELATIONSHIP_DELTA)

    affinity = delta.get("affinity", 0)
    if isinstance(affinity, (int, float)):
        result["affinity"] = max(-5, min(5, int(affinity)))
    else:
        result["affinity"] = 0

    reason = delta.get("reason", "none")
    if isinstance(reason, str):
        result["reason"] = reason

    return result


def validate_memory_tags(tags: list | None) -> list[str]:
    """문자열 배열, 각 50자 이내 보정"""
    if not isinstance(tags, list):
        return []

    validated: list[str] = []
    for tag in tags:
        if isinstance(tag, str):
            validated.append(tag[:50])
    return validated


def validate_quest_seed_response(response: str | None) -> str | None:
    """'accepted'|'ignored'|None만 허용"""
    if response is None:
        return None
    if isinstance(response, str) and response in VALID_SEED_RESPONSES:
        return response
    logger.warning("Invalid quest_seed_response '%s', setting to None", response)
    return None


def validate_trade_request(trade: dict | None) -> dict | None:
    """action 허용값 검증. 불허 시 None"""
    if trade is None:
        return None
    if not isinstance(trade, dict):
        return None

    action = trade.get("action")
    if not isinstance(action, str) or action not in VALID_TRADE_ACTIONS:
        logger.warning("Invalid trade_request action '%s', discarding", action)
        return None

    item_id = trade.get("item_instance_id")
    if not isinstance(item_id, str) or not item_id:
        logger.warning("Missing item_instance_id in trade_request, discarding")
        return None

    return trade


def validate_gift_offered(gift: dict | None) -> dict | None:
    """기본 구조 검증. 불허 시 None"""
    if gift is None:
        return None
    if not isinstance(gift, dict):
        return None

    item_id = gift.get("item_instance_id")
    if not isinstance(item_id, str) or not item_id:
        logger.warning("Missing item_instance_id in gift_offered, discarding")
        return None

    return gift


def _build_default_meta() -> dict:
    """전체 기본 META 생성"""
    return {
        "dialogue_state": dict(DEFAULT_DIALOGUE_STATE),
        "relationship_delta": dict(DEFAULT_RELATIONSHIP_DELTA),
        "memory_tags": [],
        "quest_seed_response": None,
        "trade_request": None,
        "gift_offered": None,
    }
