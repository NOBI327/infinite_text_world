"""Constraints 빌드 — PC 보유 아이템 → 대화 시스템 Constraints"""

import logging
from typing import Callable, Optional

from .models import ItemPrototype, ItemInstance

logger = logging.getLogger(__name__)


def build_item_constraints(
    instances: list[ItemInstance],
    get_prototype: Callable[[str], Optional[ItemPrototype]],
) -> dict:
    """PC 보유 아이템에서 Constraints dict 생성.

    Returns:
        {
            "pc_items": ["wpn_rusty_sword", ...],
            "pc_axiom_powers": {"Ignis": 1, "Scindere": 2, ...}
        }

    get_prototype: Core는 DB를 모르므로, 호출자가 조회 함수를 주입.
    """
    pc_items: list[str] = []
    pc_axiom_powers: dict[str, int] = {}

    for inst in instances:
        proto = get_prototype(inst.prototype_id)
        if proto is None:
            logger.warning("Prototype not found: %s", inst.prototype_id)
            continue

        pc_items.append(proto.item_id)

        for tag, power in proto.axiom_tags.items():
            if tag not in pc_axiom_powers or power > pc_axiom_powers[tag]:
                pc_axiom_powers[tag] = power

    return {
        "pc_items": pc_items,
        "pc_axiom_powers": pc_axiom_powers,
    }
