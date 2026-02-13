"""내구도 시스템"""

import logging

from .models import ItemInstance, ItemPrototype

logger = logging.getLogger(__name__)


def apply_durability_loss(
    instance: ItemInstance,
    prototype: ItemPrototype,
) -> dict:
    """아이템 사용 시 내구도 감소.

    Returns:
        {
            "broken": bool,
            "new_durability": int,
            "broken_result": str | None  # 파괴 시 생성할 prototype_id
        }

    max_durability == 0: 파괴 불가, 변화 없음.
    current_durability <= 0 시:
        broken_result != None → 변환 아이템 생성 필요
        broken_result == None → 소멸
    """
    if prototype.max_durability == 0:
        return {
            "broken": False,
            "new_durability": instance.current_durability,
            "broken_result": None,
        }

    new_dur = instance.current_durability - prototype.durability_loss_per_use
    instance.current_durability = max(0, new_dur)

    if new_dur <= 0:
        logger.info(
            "Item %s (proto=%s) broken",
            instance.instance_id,
            prototype.item_id,
        )
        return {
            "broken": True,
            "new_durability": 0,
            "broken_result": prototype.broken_result,
        }

    return {
        "broken": False,
        "new_durability": instance.current_durability,
        "broken_result": None,
    }


def get_durability_ratio(instance: ItemInstance, prototype: ItemPrototype) -> float:
    """현재 내구도 비율 (0.0~1.0).
    max_durability == 0 이면 1.0 (파괴 불가).
    """
    if prototype.max_durability == 0:
        return 1.0
    return instance.current_durability / prototype.max_durability
