"""TEMPORARY: Phase B 자율행동 구현 시 제거.
상인 NPC의 선반/인벤토리 자동 보충.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# TEMPORARY: Phase B 자율행동 구현 시 제거
@dataclass
class ShopRestockConfig:
    """상인 NPC별 자동 보충 설정"""

    npc_id: str
    shelf_instance_id: str
    stock_template: list[str] = field(default_factory=list)  # prototype_id 목록
    restock_cooldown: int = 5  # N턴마다 보충
    max_stock_per_item: int = 3


# TEMPORARY: Phase B 자율행동 구현 시 제거
def check_restock_needed(config: ShopRestockConfig, current_turn: int) -> bool:
    """보충 필요 여부 판정."""
    return current_turn % config.restock_cooldown == 0


# TEMPORARY: Phase B 자율행동 구현 시 제거
def calculate_restock_deficit(
    config: ShopRestockConfig,
    current_stock: dict[str, int],  # {prototype_id: count}
) -> dict[str, int]:
    """보충 필요 수량 계산. Returns: {prototype_id: deficit}"""
    deficit: dict[str, int] = {}
    for proto_id in config.stock_template:
        current = current_stock.get(proto_id, 0)
        needed = config.max_stock_per_item - current
        if needed > 0:
            deficit[proto_id] = needed
    return deficit
