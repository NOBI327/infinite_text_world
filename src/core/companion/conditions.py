"""동행 조건 생성 + 만료 판정

companion-system.md 섹션 2.3, 섹션 8 대응.
"""

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

CONDITION_CHANCE = 0.40

CONDITION_TYPES = [
    "payment",
    "time_limit",
    "destination_only",
    "safety_guarantee",
    "item_request",
]


def roll_condition() -> tuple[bool, str | None]:
    """조건 발생 판정 (40%). 성공 시 유형 랜덤 선택.

    Returns: (조건 발생 여부, 조건 유형 또는 None)
    """
    if random.random() < CONDITION_CHANCE:
        condition_type = random.choice(CONDITION_TYPES)
        logger.debug("Condition rolled: %s", condition_type)
        return True, condition_type
    return False, None


def generate_condition_data(condition_type: str) -> dict[str, Any]:
    """조건 유형별 기본 데이터 생성.

    payment: {"amount": 30~80 랜덤}
    time_limit: {"turn_limit": 20~40 랜덤}
    destination_only: {"destination": ""} — Service가 채움
    safety_guarantee: {"danger_threshold": 0.7, "warned": False}
    item_request: {"item_id": ""} — Service가 채움
    """
    if condition_type == "payment":
        return {"amount": random.randint(30, 80)}
    elif condition_type == "time_limit":
        return {"turn_limit": random.randint(20, 40)}
    elif condition_type == "destination_only":
        return {"destination": ""}
    elif condition_type == "safety_guarantee":
        return {"danger_threshold": 0.7, "warned": False}
    elif condition_type == "item_request":
        return {"item_id": ""}
    else:
        logger.warning("Unknown condition type: %s", condition_type)
        return {}


def check_condition_expired(
    condition_type: str,
    condition_data: dict[str, Any],
    started_turn: int,
    current_turn: int,
    pc_node: str,
    node_danger: float = 0.0,
) -> tuple[bool, bool]:
    """조건 만료 판정.

    Returns: (만료 여부, 경고 상태)

    time_limit: current_turn - started_turn >= turn_limit
    destination_only: pc_node == destination
    safety_guarantee: danger >= threshold → 경고(1턴 유예) → 다음 호출에서 만료
    payment, item_request: 이 함수에서 판정하지 않음 (별도 로직)
    """
    warned = condition_data.get("warned", False)

    if condition_type == "time_limit":
        turn_limit = condition_data.get("turn_limit", 0)
        elapsed = current_turn - started_turn
        expired = elapsed >= turn_limit
        return expired, warned

    elif condition_type == "destination_only":
        destination = condition_data.get("destination", "")
        expired = destination != "" and pc_node == destination
        return expired, warned

    elif condition_type == "safety_guarantee":
        threshold = condition_data.get("danger_threshold", 0.7)
        if node_danger >= threshold:
            if warned:
                return True, True
            else:
                return False, True
        return False, False

    # payment, item_request: 별도 로직
    return False, warned
