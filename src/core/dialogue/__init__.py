"""대화 시스템 Core 패키지

dialogue-system.md 대응.
DB 무관 순수 Python 도메인 모델 + 예산/검증 로직.
"""

from src.core.dialogue.models import (
    DIALOGUE_END_STATUSES,
    DialogueSession,
    DialogueTurn,
)
from src.core.dialogue.budget import (
    BASE_BUDGET,
    PHASE_INSTRUCTIONS,
    calculate_budget,
    get_budget_phase,
    get_phase_instruction,
)
from src.core.dialogue.hexaco_descriptors import (
    HEXACO_DESCRIPTORS,
    hexaco_to_natural_language,
)
from src.core.dialogue.validation import (
    validate_meta,
    validate_dialogue_state,
    validate_relationship_delta,
    validate_memory_tags,
    validate_quest_seed_response,
    validate_trade_request,
    validate_gift_offered,
)
from src.core.dialogue.constraints import (
    validate_action_interpretation,
)

__all__ = [
    "DIALOGUE_END_STATUSES",
    "DialogueSession",
    "DialogueTurn",
    "BASE_BUDGET",
    "PHASE_INSTRUCTIONS",
    "calculate_budget",
    "get_budget_phase",
    "get_phase_instruction",
    "HEXACO_DESCRIPTORS",
    "hexaco_to_natural_language",
    "validate_meta",
    "validate_dialogue_state",
    "validate_relationship_delta",
    "validate_memory_tags",
    "validate_quest_seed_response",
    "validate_trade_request",
    "validate_gift_offered",
    "validate_action_interpretation",
]
