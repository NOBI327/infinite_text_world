"""거래 시스템 — 가격 계산 + 흥정 판정"""

import logging

logger = logging.getLogger(__name__)

RELATIONSHIP_DISCOUNT: dict[str, float] = {
    "stranger": 1.0,
    "acquaintance": 0.95,
    "friend": 0.85,
    "bonded": 0.75,
    "rival": 1.1,
    "nemesis": 1.3,
}


def calculate_trade_price(
    base_value: int,
    relationship_status: str,
    is_buying: bool,
    npc_hexaco_h: float,
    durability_ratio: float,
) -> int:
    """거래가 계산. 최소 1.

    is_buying=True: NPC 판매 (50% 마진)
    is_buying=False: NPC 구매 (50% 할인)
    관계 보정, HEXACO H 보정, 내구도 반영.
    """
    if is_buying:
        price = base_value * 1.5
    else:
        price = base_value * 0.5

    price *= RELATIONSHIP_DISCOUNT.get(relationship_status, 1.0)

    if npc_hexaco_h <= 0.3:
        price *= 1.2
    elif npc_hexaco_h >= 0.7:
        price *= 0.9

    price *= max(0.3, durability_ratio)

    return max(1, round(price))


def evaluate_haggle(
    proposed_price: int,
    calculated_price: int,
    relationship_status: str,
    npc_hexaco_a: float,
) -> str:
    """흥정 결과: "accept" | "counter" | "reject"

    A(관용성) 기반 threshold:
    - A >= 0.7: threshold 0.7
    - A >= 0.3: threshold 0.8
    - A < 0.3: threshold 0.9

    discount_ratio >= threshold → accept
    discount_ratio >= threshold - 0.15 → counter
    else → reject
    """
    if calculated_price == 0:
        return "accept"

    discount_ratio = proposed_price / calculated_price

    if npc_hexaco_a >= 0.7:
        threshold = 0.7
    elif npc_hexaco_a >= 0.3:
        threshold = 0.8
    else:
        threshold = 0.9

    if discount_ratio >= threshold:
        return "accept"
    elif discount_ratio >= threshold - 0.15:
        return "counter"
    else:
        return "reject"


def calculate_counter_price(
    proposed_price: int,
    calculated_price: int,
) -> int:
    """counter 시 역제안 가격. 중간값."""
    return round((proposed_price + calculated_price) / 2)
