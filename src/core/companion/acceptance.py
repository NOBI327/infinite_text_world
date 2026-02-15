"""동행 수락 판정 — 순수 Python

companion-system.md 섹션 2.2, 2.3 대응.
"""

import logging
import random

logger = logging.getLogger(__name__)

# === 퀘스트 동행 ===
QUEST_COMPANION_ACCEPT_BASE = 0.90


def quest_companion_accept_chance(
    npc_hexaco_a: float,
    is_rescue: bool = False,
) -> float:
    """퀘스트 동행 수락 확률 계산.

    구출 상황(is_rescue): 98%
    기본: 90%
    A(원만성) <= 0.2: -10%
    최대 99%.
    """
    if is_rescue:
        base = 0.98
    else:
        base = QUEST_COMPANION_ACCEPT_BASE

    if npc_hexaco_a <= 0.2:
        base -= 0.10

    return min(base, 0.99)


def roll_quest_companion(
    npc_hexaco_a: float,
    is_rescue: bool = False,
) -> bool:
    """퀘스트 동행 수락 판정."""
    chance = quest_companion_accept_chance(npc_hexaco_a, is_rescue)
    result = random.random() < chance
    logger.debug(
        "Quest companion roll: chance=%.2f, result=%s",
        chance,
        result,
    )
    return result


# === 자발적 동행 ===
ACCEPT_BY_STATUS: dict[str, float] = {
    "stranger": 0.0,
    "acquaintance": 0.10,
    "friend": 0.50,
    "bonded": 0.85,
    "rival": 0.0,
    "nemesis": 0.0,
}


def voluntary_companion_accept(
    relationship_status: str,
    trust: int,
    npc_hexaco: dict[str, float],
    pc_destination_danger: float = 0.0,
) -> tuple[bool, str | None]:
    """자발적 동행 수락 판정.

    Returns: (수락 여부, 거절 시 사유 태그)

    사유: "insufficient_relationship" | "personality_reluctance"

    보정:
    - trust >= 50: +0.15, trust <= 20: -0.15
    - X >= 0.7: +0.10
    - E >= 0.7: -danger*0.20
    - C >= 0.7: -0.10
    최종: 0.0 ~ 0.95 클램핑
    """
    base = ACCEPT_BY_STATUS.get(relationship_status, 0.0)
    if base == 0.0:
        return False, "insufficient_relationship"

    # trust 보정
    if trust >= 50:
        base += 0.15
    elif trust <= 20:
        base -= 0.15

    # 성격 보정
    if npc_hexaco.get("X", 0.5) >= 0.7:
        base += 0.10
    if npc_hexaco.get("E", 0.5) >= 0.7:
        base -= pc_destination_danger * 0.20
    if npc_hexaco.get("C", 0.5) >= 0.7:
        base -= 0.10

    base = max(0.0, min(base, 0.95))

    if random.random() < base:
        return True, None
    else:
        return False, "personality_reluctance"
