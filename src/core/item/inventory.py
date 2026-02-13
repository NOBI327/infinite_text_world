"""인벤토리 용량 관리"""

import logging

logger = logging.getLogger(__name__)

BASE_INVENTORY_CAPACITY = 50


def calculate_inventory_capacity(stats: dict[str, int]) -> int:
    """PC/NPC 공통. EXEC 기준 ±5.
    최소 30.
    """
    base = BASE_INVENTORY_CAPACITY
    base += (stats.get("EXEC", 2) - 2) * 5
    return max(30, base)


def calculate_current_bulk(bulks: list[int]) -> int:
    """아이템 목록의 bulk 합계.
    bulks: 각 아이템의 bulk 값 리스트.
    """
    return sum(bulks)


def can_add_item(current_bulk: int, capacity: int, item_bulk: int) -> bool:
    """아이템 추가 가능 여부"""
    return current_bulk + item_bulk <= capacity
