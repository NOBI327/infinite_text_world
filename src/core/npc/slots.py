"""배경인물 슬롯 시스템

npc-system.md 섹션 3 대응.
"""

from typing import Dict, List

# ── 시설별 기본 슬롯 수 (섹션 3.3) ──────────────────────────

FACILITY_BASE_SLOTS: Dict[str, int] = {
    "inn": 4,
    "smithy": 2,
    "market": 6,
    "temple": 3,
    "tavern": 5,
    "farm": 2,
    "mine": 3,
}

# ── 시설별 필수 역할 (섹션 3.1 기반) ────────────────────────

FACILITY_REQUIRED_ROLES: Dict[str, List[str]] = {
    "inn": ["innkeeper"],
    "smithy": ["blacksmith"],
    "market": ["merchant"],
    "temple": ["priest"],
    "tavern": ["barkeeper"],
    "farm": ["farmer"],
    "mine": ["foreman"],
}


def calculate_slot_count(facility_type: str, facility_size: int) -> int:
    """슬롯 개수 = 기본값 + 규모 보정 (섹션 3.3)

    Args:
        facility_type: 시설 유형 (e.g. "inn", "smithy")
        facility_size: 시설 규모 (정수)

    Returns:
        총 슬롯 수. 미등록 시설은 기본 2개.
    """
    base = FACILITY_BASE_SLOTS.get(facility_type, 2)
    size_modifier = facility_size // 2
    return base + size_modifier


def should_reset_slot(
    promotion_score: int,
    turns_since_reset: int,
    reset_interval: int = 24,
) -> bool:
    """슬롯 리셋 여부 판정 (섹션 3.4)

    순수 함수. BackgroundSlot 객체 대신 필요한 값만 받는다.

    Args:
        promotion_score: 배치된 개체의 승격 점수. 0이면 보호 안 함.
        turns_since_reset: 마지막 리셋 이후 경과 턴 수.
        reset_interval: 리셋 주기 (기본 24턴).

    Returns:
        True면 리셋해야 함.
    """
    # 승격 진행 중이면 보호
    if promotion_score > 0:
        return False

    # 시간 기반 리셋
    if turns_since_reset >= reset_interval:
        return True

    return False
