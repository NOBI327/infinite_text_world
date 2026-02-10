"""Phase 2 DB Models (NPC / Relationship / Quest / Dialogue / Item)

DDL reference: docs/30_technical/db-schema-v2.md
"""

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)

from src.db.models import Base


# ── 1단계: 의존 없음 ──────────────────────────────────────


class ItemPrototypeModel(Base):
    """아이템 원형 (item-system.md 섹션 11.1)"""

    __tablename__ = "item_prototypes"

    item_id = Column(Text, primary_key=True)
    name_kr = Column(Text, nullable=False)
    item_type = Column(Text, nullable=False)

    weight = Column(Float, nullable=False, default=0.0)
    bulk = Column(Integer, nullable=False, default=1)
    base_value = Column(Integer, nullable=False, default=0)

    primary_material = Column(Text, nullable=False, server_default="")
    axiom_tags = Column(Text, nullable=False, server_default="{}")

    max_durability = Column(Integer, nullable=False, default=0)
    durability_loss_per_use = Column(Integer, nullable=False, default=0)
    broken_result = Column(Text, nullable=True)

    container_capacity = Column(Integer, nullable=False, default=0)

    flavor_text = Column(Text, nullable=False, server_default="")
    tags = Column(Text, nullable=False, server_default="[]")

    is_dynamic = Column(Boolean, nullable=False, default=False)


class QuestChainModel(Base):
    """연작 퀘스트 체인 (quest-system.md 섹션 5)"""

    __tablename__ = "quest_chains"

    chain_id = Column(Text, primary_key=True)
    created_turn = Column(Integer, nullable=False)
    finalized = Column(Boolean, nullable=False, default=False)
    total_quests = Column(Integer, nullable=False, default=0)

    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))


# ── 2단계: v1 테이블 의존 ──────────────────────────────────


class BackgroundSlotModel(Base):
    """거주형 배경인물의 시설 슬롯 (npc-system.md)"""

    __tablename__ = "background_slots"

    slot_id = Column(Text, primary_key=True)
    node_id = Column(Text, nullable=False)
    facility_id = Column(Text, nullable=False)
    facility_type = Column(Text, nullable=False)

    role = Column(Text, nullable=False)
    is_required = Column(Boolean, nullable=False, default=False)

    entity_id = Column(Text, nullable=True)

    reset_interval = Column(Integer, nullable=False, default=24)
    last_reset_turn = Column(Integer, nullable=False, default=0)

    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_slot_node", "node_id"),
        Index("idx_slot_facility", "facility_id"),
    )


class BackgroundEntityModel(Base):
    """승격 전 배경 존재 (npc-system.md 섹션 2~6)"""

    __tablename__ = "background_entities"

    entity_id = Column(Text, primary_key=True)
    entity_type = Column(Text, nullable=False)

    current_node = Column(Text, nullable=False)
    home_node = Column(Text, nullable=True)

    role = Column(Text, nullable=False)
    appearance_seed = Column(Text, nullable=False, server_default="{}")

    promotion_score = Column(Integer, nullable=False, default=0)
    promoted = Column(Boolean, nullable=False, default=False)
    promoted_npc_id = Column(Text, nullable=True)

    temp_combat_id = Column(Text, nullable=True)

    name_seed = Column(Text, nullable=True)

    slot_id = Column(Text, nullable=True)

    created_turn = Column(Integer, nullable=False, default=0)
    updated_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_bg_entity_node", "current_node"),
        Index("idx_bg_entity_type", "entity_type"),
    )


class NPCModel(Base):
    """승격 완료된 NPC (npc-system.md 섹션 13)"""

    __tablename__ = "npcs"

    npc_id = Column(Text, primary_key=True)

    full_name = Column(Text, nullable=False)
    given_name = Column(Text, nullable=False)

    hexaco = Column(Text, nullable=False)

    character_sheet = Column(Text, nullable=False)
    resonance_shield = Column(Text, nullable=False)
    axiom_proficiencies = Column(Text, nullable=False, server_default="{}")

    home_node = Column(Text, nullable=True)
    current_node = Column(Text, nullable=False)

    routine = Column(Text, nullable=True)
    state = Column(Text, nullable=False, server_default="{}")

    lord_id = Column(Text, nullable=True)
    faction_id = Column(Text, nullable=True)
    loyalty = Column(Float, nullable=False, default=0.5)

    currency = Column(Integer, nullable=False, default=0)

    origin_type = Column(Text, nullable=False)
    origin_entity_type = Column(Text, nullable=True)
    role = Column(Text, nullable=False)
    tags = Column(Text, nullable=False, server_default="[]")

    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    last_interaction_turn = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_npc_node", "current_node"),
        Index("idx_npc_role", "role"),
    )


# ── 3단계: npcs 의존 ──────────────────────────────────────


class NPCMemoryModel(Base):
    """NPC 기억 3계층 (npc-system.md 섹션 10)"""

    __tablename__ = "npc_memories"

    memory_id = Column(Text, primary_key=True)
    npc_id = Column(Text, ForeignKey("npcs.npc_id", ondelete="CASCADE"), nullable=False)

    tier = Column(Integer, nullable=False)

    memory_type = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)

    emotional_valence = Column(Float, nullable=False, default=0.0)
    importance = Column(Float, nullable=False, default=0.0)

    embedding = Column(LargeBinary, nullable=True)

    is_fixed = Column(Boolean, nullable=False, default=False)
    fixed_slot = Column(Integer, nullable=True)

    turn_created = Column(Integer, nullable=False)
    related_node = Column(Text, nullable=True)
    related_entity_id = Column(Text, nullable=True)
    source_session_id = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_memory_npc", "npc_id"),
        Index("idx_memory_npc_tier", "npc_id", "tier"),
    )


class RelationshipModel(Base):
    """PC-NPC / NPC-NPC 관계 (relationship-system.md 섹션 9.1)"""

    __tablename__ = "relationships"

    relationship_id = Column(Text, primary_key=True)

    source_type = Column(Text, nullable=False)
    source_id = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False)

    affinity = Column(Float, nullable=False, default=0.0)
    trust = Column(Float, nullable=False, default=0.0)
    familiarity = Column(Integer, nullable=False, default=0)

    status = Column(Text, nullable=False, server_default="stranger")
    tags = Column(Text, nullable=False, server_default="[]")

    last_interaction_turn = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    updated_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

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

    seed_id = Column(Text, primary_key=True)
    npc_id = Column(Text, ForeignKey("npcs.npc_id"), nullable=False)

    seed_type = Column(Text, nullable=False)
    seed_tier = Column(Integer, nullable=False)

    created_turn = Column(Integer, nullable=False)
    ttl_turns = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, server_default="active")

    context_tags = Column(Text, nullable=False, server_default="[]")
    expiry_result = Column(Text, nullable=True)

    chain_id = Column(Text, nullable=True)

    conversation_count_at_creation = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_seed_npc", "npc_id"),
        Index("idx_seed_status", "status"),
    )


class WorldPoolModel(Base):
    """유랑형/적대형 재조우 풀 (npc-system.md 섹션 6)"""

    __tablename__ = "world_pool"

    entity_id = Column(
        Text,
        ForeignKey("background_entities.entity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_type = Column(Text, nullable=False)
    promotion_score = Column(Integer, nullable=False)
    last_known_node = Column(Text, nullable=False)
    registered_turn = Column(Integer, nullable=False)

    __table_args__ = (Index("idx_wp_type", "entity_type"),)


# ── 4단계: quests 의존 ────────────────────────────────────


class QuestModel(Base):
    """활성/완료 퀘스트 (quest-system.md 섹션 3.1)"""

    __tablename__ = "quests"

    quest_id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

    origin_type = Column(Text, nullable=False)
    origin_npc_id = Column(Text, nullable=True)
    origin_seed_id = Column(Text, nullable=True)
    origin_overlay_id = Column(Text, nullable=True)

    quest_type = Column(Text, nullable=False)
    seed_tier = Column(Integer, nullable=False)
    urgency = Column(Text, nullable=False, server_default="normal")
    time_limit = Column(Integer, nullable=True)

    status = Column(Text, nullable=False, server_default="active")
    result = Column(Text, nullable=True)
    activated_turn = Column(Integer, nullable=False)
    completed_turn = Column(Integer, nullable=True)

    chain_id = Column(Text, nullable=True)
    chain_index = Column(Integer, nullable=False, default=0)
    is_chain_finale = Column(Boolean, nullable=False, default=False)

    related_npc_ids = Column(Text, nullable=False, server_default="[]")
    target_node_ids = Column(Text, nullable=False, server_default="[]")
    overlay_id = Column(Text, nullable=True)

    resolution_method = Column(Text, nullable=True)
    resolution_comment = Column(Text, nullable=True)
    resolution_method_tag = Column(Text, nullable=True)
    resolution_impression_tag = Column(Text, nullable=True)

    rewards = Column(Text, nullable=True)

    tags = Column(Text, nullable=False, server_default="[]")
    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    updated_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_quest_status", "status"),
        Index("idx_quest_chain", "chain_id"),
        Index("idx_quest_npc", "origin_npc_id"),
    )


class QuestObjectiveModel(Base):
    """퀘스트 목표 (quest-system.md 섹션 12.2)"""

    __tablename__ = "quest_objectives"

    objective_id = Column(Text, primary_key=True)
    quest_id = Column(
        Text, ForeignKey("quests.quest_id", ondelete="CASCADE"), nullable=False
    )

    description = Column(Text, nullable=False)
    objective_type = Column(Text, nullable=False)
    target = Column(Text, nullable=False, server_default="{}")

    completed = Column(Boolean, nullable=False, default=False)
    completed_turn = Column(Integer, nullable=True)

    __table_args__ = (Index("idx_objective_quest", "quest_id"),)


class QuestChainEligibleModel(Base):
    """연작 가능 NPC (quest-system.md 섹션 5.3)"""

    __tablename__ = "quest_chain_eligible"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(
        Text, ForeignKey("quests.quest_id", ondelete="CASCADE"), nullable=False
    )

    npc_ref = Column(Text, nullable=False)
    ref_type = Column(Text, nullable=False)
    node_hint = Column(Text, nullable=True)
    reason = Column(Text, nullable=False)

    matched_npc_id = Column(Text, nullable=True)
    matched_turn = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_chain_eligible_quest", "quest_id"),
        Index("idx_chain_eligible_ref", "ref_type", "npc_ref"),
    )


class QuestUnresolvedThreadModel(Base):
    """미해결 복선 태그 (quest-system.md 섹션 5)"""

    __tablename__ = "quest_unresolved_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_id = Column(
        Text, ForeignKey("quests.quest_id", ondelete="SET NULL"), nullable=True
    )
    chain_id = Column(
        Text, ForeignKey("quest_chains.chain_id", ondelete="SET NULL"), nullable=True
    )

    thread_tag = Column(Text, nullable=False)
    created_turn = Column(Integer, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_turn = Column(Integer, nullable=True)

    __table_args__ = (Index("idx_thread_chain", "chain_id"),)


# ── 5단계: npcs + quests 의존 ─────────────────────────────


class DialogueSessionModel(Base):
    """대화 세션 이력 (dialogue-system.md 섹션 9.3)"""

    __tablename__ = "dialogue_sessions"

    session_id = Column(Text, primary_key=True)
    player_id = Column(Text, nullable=False)
    npc_id = Column(Text, nullable=False)
    node_id = Column(Text, nullable=False)

    budget_total = Column(Integer, nullable=False)

    status = Column(Text, nullable=False, server_default="active")
    started_turn = Column(Integer, nullable=False)
    ended_turn = Column(Integer, nullable=True)
    dialogue_turn_count = Column(Integer, nullable=False, default=0)

    seed_id = Column(Text, nullable=True)
    seed_result = Column(Text, nullable=True)

    total_affinity_delta = Column(Float, nullable=False, default=0.0)

    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_session_player", "player_id"),
        Index("idx_session_npc", "npc_id"),
    )


class DialogueTurnModel(Base):
    """대화 턴 이력 (dialogue-system.md 섹션 9.3)"""

    __tablename__ = "dialogue_turns"

    turn_id = Column(Text, primary_key=True)
    session_id = Column(
        Text,
        ForeignKey("dialogue_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index = Column(Integer, nullable=False)

    pc_input = Column(Text, nullable=False)
    npc_narrative = Column(Text, nullable=False)
    raw_meta = Column(Text, nullable=False, server_default="{}")
    validated_meta = Column(Text, nullable=False, server_default="{}")

    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (Index("idx_turn_session", "session_id"),)


class ItemInstanceModel(Base):
    """아이템 개체 (item-system.md 섹션 11.2)"""

    __tablename__ = "item_instances"

    instance_id = Column(Text, primary_key=True)
    prototype_id = Column(Text, ForeignKey("item_prototypes.item_id"), nullable=False)

    owner_type = Column(Text, nullable=False)
    owner_id = Column(Text, nullable=False)

    current_durability = Column(Integer, nullable=False)
    state_tags = Column(Text, nullable=False, server_default="[]")

    acquired_turn = Column(Integer, nullable=False, default=0)
    custom_name = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_item_owner", "owner_type", "owner_id"),
        Index("idx_item_proto", "prototype_id"),
    )
