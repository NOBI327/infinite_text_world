"""Phase 2 DB Models (NPC / Relationship / Quest / Dialogue / Item)

DDL reference: docs/30_technical/db-schema-v2.md
"""

from sqlalchemy import (
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Boolean, Float, Integer, LargeBinary, Text

from src.db.models import Base


# ── 1단계: 의존 없음 ──────────────────────────────────────


class ItemPrototypeModel(Base):
    """아이템 원형 (item-system.md 섹션 11.1)"""

    __tablename__ = "item_prototypes"

    item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name_kr: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)

    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bulk: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    base_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    primary_material: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    axiom_tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    max_durability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    durability_loss_per_use: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    broken_result: Mapped[str | None] = mapped_column(Text, nullable=True)

    container_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    flavor_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")

    is_dynamic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class QuestChainModel(Base):
    """연작 퀘스트 체인 (quest-system.md 섹션 5)"""

    __tablename__ = "quest_chains"

    chain_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_quests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )


# ── 2단계: v1 테이블 의존 ──────────────────────────────────


class BackgroundSlotModel(Base):
    """거주형 배경인물의 시설 슬롯 (npc-system.md)"""

    __tablename__ = "background_slots"

    slot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    facility_id: Mapped[str] = mapped_column(Text, nullable=False)
    facility_type: Mapped[str] = mapped_column(Text, nullable=False)

    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    reset_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    last_reset_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (
        Index("idx_slot_node", "node_id"),
        Index("idx_slot_facility", "facility_id"),
    )


class BackgroundEntityModel(Base):
    """승격 전 배경 존재 (npc-system.md 섹션 2~6)"""

    __tablename__ = "background_entities"

    entity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)

    current_node: Mapped[str] = mapped_column(Text, nullable=False)
    home_node: Mapped[str | None] = mapped_column(Text, nullable=True)

    role: Mapped[str] = mapped_column(Text, nullable=False)
    appearance_seed: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="{}"
    )

    promotion_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_npc_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    temp_combat_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    name_seed: Mapped[str | None] = mapped_column(Text, nullable=True)

    slot_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (
        Index("idx_bg_entity_node", "current_node"),
        Index("idx_bg_entity_type", "entity_type"),
    )


class NPCModel(Base):
    """승격 완료된 NPC (npc-system.md 섹션 13)"""

    __tablename__ = "npcs"

    npc_id: Mapped[str] = mapped_column(Text, primary_key=True)

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    given_name: Mapped[str] = mapped_column(Text, nullable=False)

    hexaco: Mapped[str] = mapped_column(Text, nullable=False)

    character_sheet: Mapped[str] = mapped_column(Text, nullable=False)
    resonance_shield: Mapped[str] = mapped_column(Text, nullable=False)
    axiom_proficiencies: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="{}"
    )

    home_node: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_node: Mapped[str] = mapped_column(Text, nullable=False)

    routine: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    lord_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    faction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    loyalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    currency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    origin_type: Mapped[str] = mapped_column(Text, nullable=False)
    origin_entity_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")

    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )
    last_interaction_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_npc_node", "current_node"),
        Index("idx_npc_role", "role"),
    )


# ── 3단계: npcs 의존 ──────────────────────────────────────


class NPCMemoryModel(Base):
    """NPC 기억 3계층 (npc-system.md 섹션 10)"""

    __tablename__ = "npc_memories"

    memory_id: Mapped[str] = mapped_column(Text, primary_key=True)
    npc_id: Mapped[str] = mapped_column(
        Text, ForeignKey("npcs.npc_id", ondelete="CASCADE"), nullable=False
    )

    tier: Mapped[int] = mapped_column(Integer, nullable=False)

    memory_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    emotional_valence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    is_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fixed_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)

    turn_created: Mapped[int] = mapped_column(Integer, nullable=False)
    related_node: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_memory_npc", "npc_id"),
        Index("idx_memory_npc_tier", "npc_id", "tier"),
    )


class RelationshipModel(Base):
    """PC-NPC / NPC-NPC 관계 (relationship-system.md 섹션 9.1)"""

    __tablename__ = "relationships"

    relationship_id: Mapped[str] = mapped_column(Text, primary_key=True)

    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)

    affinity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    familiarity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="stranger")
    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")

    last_interaction_turn: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            name="uq_rel_pair",
        ),
        Index("idx_rel_source", "source_type", "source_id"),
        Index("idx_rel_target", "target_type", "target_id"),
    )


class QuestSeedModel(Base):
    """퀘스트 시드 (quest-system.md 섹션 2.3)"""

    __tablename__ = "quest_seeds"

    seed_id: Mapped[str] = mapped_column(Text, primary_key=True)
    npc_id: Mapped[str] = mapped_column(Text, ForeignKey("npcs.npc_id"), nullable=False)

    seed_type: Mapped[str] = mapped_column(Text, nullable=False)
    seed_tier: Mapped[int] = mapped_column(Integer, nullable=False)

    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    ttl_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")

    context_tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    expiry_result: Mapped[str | None] = mapped_column(Text, nullable=True)

    chain_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation_count_at_creation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    __table_args__ = (
        Index("idx_seed_npc", "npc_id"),
        Index("idx_seed_status", "status"),
    )


class WorldPoolModel(Base):
    """유랑형/적대형 재조우 풀 (npc-system.md 섹션 6)"""

    __tablename__ = "world_pool"

    entity_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("background_entities.entity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    promotion_score: Mapped[int] = mapped_column(Integer, nullable=False)
    last_known_node: Mapped[str] = mapped_column(Text, nullable=False)
    registered_turn: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("idx_wp_type", "entity_type"),)


# ── 4단계: quests 의존 ────────────────────────────────────


class QuestModel(Base):
    """활성/완료 퀘스트 (quest-system.md 섹션 3.1)"""

    __tablename__ = "quests"

    quest_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    origin_type: Mapped[str] = mapped_column(Text, nullable=False)
    origin_npc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_seed_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_overlay_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    quest_type: Mapped[str] = mapped_column(Text, nullable=False)
    seed_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency: Mapped[str] = mapped_column(Text, nullable=False, server_default="normal")
    time_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chain_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    chain_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_chain_finale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    related_npc_ids: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]"
    )
    target_node_ids: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]"
    )
    overlay_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolution_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_method_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_impression_tag: Mapped[str | None] = mapped_column(Text, nullable=True)

    rewards: Mapped[str | None] = mapped_column(Text, nullable=True)

    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (
        Index("idx_quest_status", "status"),
        Index("idx_quest_chain", "chain_id"),
        Index("idx_quest_npc", "origin_npc_id"),
    )


class QuestObjectiveModel(Base):
    """퀘스트 목표 (quest-system.md 섹션 12.2)"""

    __tablename__ = "quest_objectives"

    objective_id: Mapped[str] = mapped_column(Text, primary_key=True)
    quest_id: Mapped[str] = mapped_column(
        Text, ForeignKey("quests.quest_id", ondelete="CASCADE"), nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective_type: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("idx_objective_quest", "quest_id"),)


class QuestChainEligibleModel(Base):
    """연작 가능 NPC (quest-system.md 섹션 5.3)"""

    __tablename__ = "quest_chain_eligible"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quest_id: Mapped[str] = mapped_column(
        Text, ForeignKey("quests.quest_id", ondelete="CASCADE"), nullable=False
    )

    npc_ref: Mapped[str] = mapped_column(Text, nullable=False)
    ref_type: Mapped[str] = mapped_column(Text, nullable=False)
    node_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    matched_npc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_chain_eligible_quest", "quest_id"),
        Index("idx_chain_eligible_ref", "ref_type", "npc_ref"),
    )


class QuestUnresolvedThreadModel(Base):
    """미해결 복선 태그 (quest-system.md 섹션 5)"""

    __tablename__ = "quest_unresolved_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quest_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("quests.quest_id", ondelete="SET NULL"), nullable=True
    )
    chain_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("quest_chains.chain_id", ondelete="SET NULL"), nullable=True
    )

    thread_tag: Mapped[str] = mapped_column(Text, nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("idx_thread_chain", "chain_id"),)


# ── 5단계: npcs + quests 의존 ─────────────────────────────


class DialogueSessionModel(Base):
    """대화 세션 이력 (dialogue-system.md 섹션 9.3)"""

    __tablename__ = "dialogue_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    player_id: Mapped[str] = mapped_column(Text, nullable=False)
    npc_id: Mapped[str] = mapped_column(Text, nullable=False)
    node_id: Mapped[str] = mapped_column(Text, nullable=False)

    budget_total: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    started_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    ended_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dialogue_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    seed_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_result: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_affinity_delta: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (
        Index("idx_session_player", "player_id"),
        Index("idx_session_npc", "npc_id"),
    )


class DialogueTurnModel(Base):
    """대화 턴 이력 (dialogue-system.md 섹션 9.3)"""

    __tablename__ = "dialogue_turns"

    turn_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("dialogue_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)

    pc_input: Mapped[str] = mapped_column(Text, nullable=False)
    npc_narrative: Mapped[str] = mapped_column(Text, nullable=False)
    raw_meta: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    validated_meta: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="{}"
    )

    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("datetime('now')")
    )

    __table_args__ = (Index("idx_turn_session", "session_id"),)


class ItemInstanceModel(Base):
    """아이템 개체 (item-system.md 섹션 11.2)"""

    __tablename__ = "item_instances"

    instance_id: Mapped[str] = mapped_column(Text, primary_key=True)
    prototype_id: Mapped[str] = mapped_column(
        Text, ForeignKey("item_prototypes.item_id"), nullable=False
    )

    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)

    current_durability: Mapped[int] = mapped_column(Integer, nullable=False)
    state_tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")

    acquired_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custom_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_item_owner", "owner_type", "owner_id"),
        Index("idx_item_proto", "prototype_id"),
    )
