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
    NPC_NEEDED = "npc_needed"

    # relationship
    RELATIONSHIP_CHANGED = "relationship_changed"
    RELATIONSHIP_REVERSED = "relationship_reversed"
    ATTITUDE_REQUEST = "attitude_request"
    ATTITUDE_RESPONSE = "attitude_response"

    # dialogue
    DIALOGUE_STARTED = "dialogue_started"
    DIALOGUE_ACTION_DECLARED = "dialogue_action_declared"
    DIALOGUE_ENDED = "dialogue_ended"

    # quest-dialogue integration
    QUEST_SEED_GENERATED = "quest_seed_generated"

    # item
    ITEM_TRANSFERRED = "item_transferred"
    ITEM_BROKEN = "item_broken"
    ITEM_CREATED = "item_created"

    # === Quest events ===
    QUEST_ACTIVATED = "quest_activated"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    QUEST_ABANDONED = "quest_abandoned"
    QUEST_SEED_CREATED = "quest_seed_created"
    QUEST_SEED_EXPIRED = "quest_seed_expired"
    QUEST_CHAIN_FORMED = "quest_chain_formed"
    QUEST_CHAIN_FINALIZED = "quest_chain_finalized"
    CHAIN_ELIGIBLE_MATCHED = "chain_eligible_matched"

    # === Objective events (ObjectiveWatcher) ===
    OBJECTIVE_COMPLETED = "objective_completed"
    OBJECTIVE_FAILED = "objective_failed"

    # === Action events (engine → ObjectiveWatcher) ===
    PLAYER_MOVED = "player_moved"
    ACTION_COMPLETED = "action_completed"
    ITEM_GIVEN = "item_given"
    CHECK_RESULT = "check_result"

    # === Companion events ===
    COMPANION_JOINED = "companion_joined"
    COMPANION_MOVED = "companion_moved"
    COMPANION_DISBANDED = "companion_disbanded"

    # === NPC lifecycle (already have NPC_DIED, NPC_PROMOTED above) ===

    # engine
    TURN_PROCESSED = "turn_processed"
