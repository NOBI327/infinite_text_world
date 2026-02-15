"""동행 시스템 Core 패키지

companion-system.md 대응.
DB 무관 순수 Python 로직.
"""

from src.core.companion.acceptance import (
    ACCEPT_BY_STATUS,
    QUEST_COMPANION_ACCEPT_BASE,
    quest_companion_accept_chance,
    roll_quest_companion,
    voluntary_companion_accept,
)
from src.core.companion.conditions import (
    CONDITION_CHANCE,
    CONDITION_TYPES,
    check_condition_expired,
    generate_condition_data,
    roll_condition,
)
from src.core.companion.models import CompanionState
from src.core.companion.return_logic import determine_return_destination

__all__ = [
    "CompanionState",
    "QUEST_COMPANION_ACCEPT_BASE",
    "ACCEPT_BY_STATUS",
    "quest_companion_accept_chance",
    "roll_quest_companion",
    "voluntary_companion_accept",
    "CONDITION_CHANCE",
    "CONDITION_TYPES",
    "roll_condition",
    "generate_condition_data",
    "check_condition_expired",
    "determine_return_destination",
]
