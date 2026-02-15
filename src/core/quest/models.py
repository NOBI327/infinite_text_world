"""퀘스트 도메인 모델 (DB 무관)"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class QuestSeed:
    """대화에 심어지는 퀘스트 떡밥"""

    seed_id: str
    npc_id: str
    seed_type: str  # SeedType 값
    seed_tier: int  # 1(대), 2(중), 3(소)
    created_turn: int
    ttl_turns: int
    status: str = "active"  # SeedStatus 값
    context_tags: list[str] = field(default_factory=list)
    expiry_result: Optional[str] = None
    chain_id: Optional[str] = None
    unresolved_threads: list[str] = field(default_factory=list)


@dataclass
class ChainEligibleNPC:
    """연작 퀘스트를 부여할 수 있는 NPC"""

    npc_ref: str  # 실제 npc_id 또는 role 태그
    ref_type: str  # "existing" | "unborn"
    node_hint: Optional[str] = None
    reason: str = ""  # "quest_giver"|"witness"|"antagonist"|"foreshadowed"


@dataclass
class Objective:
    """퀘스트 목표 단위"""

    objective_id: str
    quest_id: str
    description: str
    objective_type: str  # ObjectiveType 값
    target: dict[str, Any] = field(default_factory=dict)

    status: str = "active"  # ObjectiveStatus 값
    completed_turn: Optional[int] = None
    failed_turn: Optional[int] = None
    fail_reason: Optional[str] = None

    is_replacement: bool = False
    replaced_objective_id: Optional[str] = None
    replacement_origin: Optional[str] = None


@dataclass
class RelationshipDelta:
    """관계 변동값"""

    affinity: int = 0
    trust: int = 0
    familiarity: int = 0
    reason: str = ""


@dataclass
class WorldChange:
    """퀘스트 결과로 인한 월드 상태 변경"""

    node_id: str
    change_type: str  # "tag_add"|"tag_remove"|"overlay_modify"|"npc_spawn"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuestRewards:
    """퀘스트 완료 시 보상"""

    relationship_deltas: dict[str, RelationshipDelta] = field(default_factory=dict)
    items: list[str] = field(default_factory=list)
    world_changes: list[WorldChange] = field(default_factory=list)
    experience: int = 0


@dataclass
class Quest:
    """퀘스트 본체"""

    quest_id: str
    title: str = ""
    description: str = ""

    # 출처
    origin_type: str = "conversation"  # "conversation"|"environment"
    origin_npc_id: Optional[str] = None
    origin_seed_id: Optional[str] = None
    origin_overlay_id: Optional[str] = None

    # 유형
    quest_type: str = "deliver"  # QuestType 값
    seed_tier: int = 3
    urgency: str = "normal"  # Urgency 값
    time_limit: Optional[int] = None

    # 상태
    status: str = "active"  # QuestStatus 값
    result: Optional[str] = None  # QuestResult 값
    activated_turn: int = 0
    completed_turn: Optional[int] = None

    # 체이닝
    chain_id: Optional[str] = None
    chain_index: int = 0
    is_chain_finale: bool = False
    chain_eligible_npcs: list[ChainEligibleNPC] = field(default_factory=list)
    unresolved_threads: list[str] = field(default_factory=list)

    # 관련 엔티티
    related_npc_ids: list[str] = field(default_factory=list)
    target_node_ids: list[str] = field(default_factory=list)
    overlay_id: Optional[str] = None

    # 해결 기록
    resolution_method: Optional[str] = None
    resolution_comment: Optional[str] = None
    resolution_method_tag: Optional[str] = None
    resolution_impression_tag: Optional[str] = None

    # 보상
    rewards: Optional[QuestRewards] = None

    # 메타
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
