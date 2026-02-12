"""관계 시스템 도메인 모델

relationship-system.md 섹션 9 대응.
DB 무관 순수 데이터 클래스.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class RelationshipStatus(str, Enum):
    """관계 상태 6단계 (섹션 9.2)"""

    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    BONDED = "bonded"
    RIVAL = "rival"
    NEMESIS = "nemesis"


@dataclass
class Relationship:
    """관계 데이터 (섹션 9.1)"""

    relationship_id: str
    source_type: str  # "player" | "npc"
    source_id: str
    target_type: str  # "player" | "npc"
    target_id: str

    # 3축 수치
    affinity: float = 0.0  # -100 ~ +100
    trust: float = 0.0  # 0 ~ 100
    familiarity: int = 0  # 0 ~ ∞

    # 상태
    status: RelationshipStatus = RelationshipStatus.STRANGER
    tags: List[str] = field(default_factory=list)

    # 메타
    last_interaction_turn: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AttitudeContext:
    """태도 태그 생성 결과 (섹션 9.3). EventBus attitude_response에 사용."""

    target_npc_id: str
    attitude_tags: List[str]  # 2~7개
    relationship_status: str
    npc_opinions: Dict[str, List[str]]  # 같은 노드 NPC에 대한 태도
