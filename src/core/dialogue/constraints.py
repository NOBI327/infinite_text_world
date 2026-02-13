"""Constraints 검증 — PC 보유 자원 대조

dialogue-system.md 섹션 5.3 대응.
"""

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

VALID_STATS = {"WRITE", "READ", "EXEC", "SUDO"}


def validate_action_interpretation(
    interpretation: dict | None,
    pc_axioms: list[str],
    pc_items: list[str],
    pc_stats: dict[str, int],
) -> dict | None:
    """LLM의 action_interpretation을 PC 보유 자원과 대조.

    - 미보유 axiom 참조 modifier → 제거
    - 미보유 item 참조 modifier → 제거
    - modifier value → -2.0 ~ 2.0 클램핑
    - stat → WRITE|READ|EXEC|SUDO 검증, 불허 시 EXEC

    interpretation이 None이면 None 반환.
    """
    if interpretation is None:
        return None

    if not isinstance(interpretation, dict):
        logger.warning("action_interpretation is not a dict, discarding")
        return None

    result = deepcopy(interpretation)

    # modifier 검증
    validated_modifiers: list[dict] = []
    for mod in result.get("modifiers", []):
        if not isinstance(mod, dict):
            continue

        source = mod.get("source", "")

        # 공리 참조 검증
        if (
            isinstance(source, str)
            and source.startswith("axiom_")
            and mod.get("axiom_id")
        ):
            if mod["axiom_id"] not in pc_axioms:
                logger.info(
                    "Removing axiom modifier '%s': not in PC axioms",
                    mod.get("axiom_id"),
                )
                continue

        # 아이템 참조 검증
        if (
            isinstance(source, str)
            and source.startswith("item_")
            and mod.get("item_id")
        ):
            if mod["item_id"] not in pc_items:
                logger.info(
                    "Removing item modifier '%s': not in PC items",
                    mod.get("item_id"),
                )
                continue

        # modifier value 클램핑
        value = mod.get("value", 0)
        if isinstance(value, (int, float)):
            mod["value"] = max(-2.0, min(2.0, float(value)))
        else:
            mod["value"] = 0.0

        validated_modifiers.append(mod)

    result["modifiers"] = validated_modifiers

    # stat 검증
    stat = result.get("stat", "EXEC")
    if not isinstance(stat, str) or stat not in VALID_STATS:
        logger.warning("Invalid stat '%s', defaulting to EXEC", stat)
        result["stat"] = "EXEC"

    return result
