"""선물 시스템 — affinity 변동 계산"""

import logging

logger = logging.getLogger(__name__)


def calculate_gift_affinity(
    item_base_value: int,
    npc_desire_tags: list[str],
    item_tags: list[str],
) -> int:
    """선물에 의한 affinity 변동 계산.

    기본 +1 (선물 자체)
    + 가치 보정 (100+ → +2, 40+ → +1)
    + 욕구 매칭 (겹치는 태그 수)
    최대 5 (relationship_delta 클램핑).
    """
    base = 1

    if item_base_value >= 100:
        base += 2
    elif item_base_value >= 40:
        base += 1

    matching = set(npc_desire_tags) & set(item_tags)
    if matching:
        base += len(matching)

    return min(base, 5)
