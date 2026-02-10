"""NPC Core 도메인 패키지

공개 API:
- 도메인 모델: EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData
- HEXACO 생성: generate_hexaco, get_behavior_modifier
- 톤 태그: ToneContext, derive_manner_tags, calculate_emotion
- 슬롯: calculate_slot_count, should_reset_slot
- 승격: calculate_new_score, check_promotion_status, build_npc_from_entity
- 명명: NPCNameSeed, NPCFullName, generate_name
"""

from src.core.npc.models import (
    BackgroundEntity,
    BackgroundSlot,
    EntityType,
    HEXACO,
    NPCData,
)
from src.core.npc.hexaco import (
    HEXACO_BEHAVIOR_MAP,
    ROLE_HEXACO_TEMPLATES,
    generate_hexaco,
    get_behavior_modifier,
)
from src.core.npc.tone import (
    EVENT_EMOTION_MAP,
    ToneContext,
    calculate_emotion,
    derive_manner_tags,
)
from src.core.npc.slots import (
    FACILITY_BASE_SLOTS,
    FACILITY_REQUIRED_ROLES,
    calculate_slot_count,
    should_reset_slot,
)
from src.core.npc.promotion import (
    PROMOTION_SCORE_TABLE,
    PROMOTION_THRESHOLD,
    WORLDPOOL_THRESHOLD,
    build_npc_from_entity,
    calculate_new_score,
    check_promotion_status,
)
from src.core.npc.naming import (
    NPCFullName,
    NPCNameSeed,
    generate_name,
)
from src.core.npc.memory import (
    IMPORTANCE_TABLE,
    TIER2_CAPACITY,
    NPCMemory,
    assign_tier1_slot,
    create_memory,
    enforce_tier2_capacity,
    get_memories_for_context,
)

__all__ = [
    # models
    "EntityType",
    "BackgroundEntity",
    "BackgroundSlot",
    "HEXACO",
    "NPCData",
    # hexaco
    "ROLE_HEXACO_TEMPLATES",
    "generate_hexaco",
    "HEXACO_BEHAVIOR_MAP",
    "get_behavior_modifier",
    # tone
    "ToneContext",
    "derive_manner_tags",
    "EVENT_EMOTION_MAP",
    "calculate_emotion",
    # slots
    "FACILITY_BASE_SLOTS",
    "FACILITY_REQUIRED_ROLES",
    "calculate_slot_count",
    "should_reset_slot",
    # promotion
    "PROMOTION_THRESHOLD",
    "WORLDPOOL_THRESHOLD",
    "PROMOTION_SCORE_TABLE",
    "calculate_new_score",
    "check_promotion_status",
    "build_npc_from_entity",
    # naming
    "NPCNameSeed",
    "NPCFullName",
    "generate_name",
    # memory
    "IMPORTANCE_TABLE",
    "TIER2_CAPACITY",
    "NPCMemory",
    "create_memory",
    "assign_tier1_slot",
    "enforce_tier2_capacity",
    "get_memories_for_context",
]
