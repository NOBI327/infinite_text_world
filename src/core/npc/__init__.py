"""NPC Core 도메인 패키지

공개 API:
- 도메인 모델: EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData
- HEXACO 생성: generate_hexaco, get_behavior_modifier
- 톤 태그: ToneContext, derive_manner_tags, calculate_emotion
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
]
