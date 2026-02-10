"""이벤트 유형 상수

event-bus.md 섹션 6 대응.
각 모듈 구현 시 해당 이벤트를 추가한다.
"""


class EventTypes:
    """이벤트 유형 문자열 상수"""

    # npc_core
    NPC_PROMOTED = "npc_promoted"
    NPC_CREATED = "npc_created"
    NPC_DIED = "npc_died"
    NPC_MOVED = "npc_moved"

    # engine
    TURN_PROCESSED = "turn_processed"
