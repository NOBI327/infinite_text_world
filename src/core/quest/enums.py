"""퀘스트 관련 열거형"""

from enum import Enum


class QuestType(str, Enum):
    DELIVER = "deliver"
    ESCORT = "escort"
    INVESTIGATE = "investigate"
    RESOLVE = "resolve"
    NEGOTIATE = "negotiate"
    BOND = "bond"
    RIVALRY = "rivalry"


class ObjectiveType(str, Enum):
    REACH_NODE = "reach_node"
    DELIVER = "deliver"
    ESCORT = "escort"
    TALK_TO_NPC = "talk_to_npc"
    RESOLVE_CHECK = "resolve_check"


class QuestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class QuestResult(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ABANDONED = "abandoned"


class SeedType(str, Enum):
    PERSONAL = "personal"
    RUMOR = "rumor"
    REQUEST = "request"
    WARNING = "warning"


class SeedStatus(str, Enum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    RESOLVED_OFFSCREEN = "resolved_offscreen"


class ObjectiveStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class Urgency(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"
