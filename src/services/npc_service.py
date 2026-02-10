"""NPC Service — Core 로직과 DB를 연결

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""

import json
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.logging import get_logger
from src.core.npc.hexaco import generate_hexaco
from src.core.npc.memory import (
    NPCMemory,
    assign_tier1_slot,
    create_memory,
    get_memories_for_context as _get_memories_for_context,
)
from src.core.npc.models import BackgroundEntity, EntityType, HEXACO, NPCData
from src.core.npc.naming import NPCNameSeed, generate_name
from src.core.npc.promotion import (
    build_npc_from_entity,
    calculate_new_score,
    check_promotion_status,
)
from src.db.models_v2 import (
    BackgroundEntityModel,
    NPCMemoryModel,
    NPCModel,
    WorldPoolModel,
)

logger = get_logger(__name__)


class NPCService:
    """NPC CRUD, 승격, WorldPool, 기억 관리

    npc-system.md 섹션 14 대응.
    """

    def __init__(self, db_session: Session, event_bus: EventBus) -> None:
        self._db = db_session
        self._bus = event_bus

    # ── 조회 ─────────────────────────────────────────────────

    def get_background_entities_at_node(self, node_id: str) -> List[BackgroundEntity]:
        """노드의 배경 존재 목록 (미승격만)"""
        rows = (
            self._db.query(BackgroundEntityModel)
            .filter(
                BackgroundEntityModel.current_node == node_id,
                BackgroundEntityModel.promoted == False,  # noqa: E712
            )
            .all()
        )
        return [self._entity_from_orm(r) for r in rows]

    def get_npcs_at_node(self, node_id: str) -> List[NPCData]:
        """노드의 NPC 목록"""
        rows = self._db.query(NPCModel).filter(NPCModel.current_node == node_id).all()
        return [self._npc_from_orm(r) for r in rows]

    def get_npc_by_id(self, npc_id: str) -> Optional[NPCData]:
        """ID로 NPC 조회"""
        row = self._db.query(NPCModel).filter(NPCModel.npc_id == npc_id).first()
        if row is None:
            return None
        return self._npc_from_orm(row)

    # ── 승격 ─────────────────────────────────────────────────

    def add_promotion_score(self, entity_id: str, action: str) -> str:
        """승격 점수 추가 → 상태 반환

        Returns:
            "none" / "worldpool" / "promoted"
        """
        row = (
            self._db.query(BackgroundEntityModel)
            .filter(BackgroundEntityModel.entity_id == entity_id)
            .first()
        )
        if row is None:
            logger.warning(f"Entity not found: {entity_id}")
            return "none"

        new_score = calculate_new_score(row.promotion_score, action)
        row.promotion_score = new_score
        self._db.flush()

        status = check_promotion_status(new_score)

        if status == "promoted":
            self._promote_entity(entity_id)
        elif status == "worldpool":
            if row.entity_type in (EntityType.WANDERER.value, EntityType.HOSTILE.value):
                self._register_worldpool(entity_id)

        return status

    def _promote_entity(self, entity_id: str) -> NPCData:
        """승격 처리 (내부)"""
        row = (
            self._db.query(BackgroundEntityModel)
            .filter(BackgroundEntityModel.entity_id == entity_id)
            .first()
        )
        if row is None:
            raise ValueError(f"Entity not found: {entity_id}")

        entity = self._entity_from_orm(row)

        # HEXACO 생성
        hexaco = generate_hexaco(entity.role)

        # Core 순수 변환
        npc_data = build_npc_from_entity(entity, hexaco)

        # UUID 할당
        npc_id = str(uuid.uuid4())
        npc_data.npc_id = npc_id

        # 이름 생성
        name_seed = None
        if row.name_seed:
            try:
                seed_dict = json.loads(row.name_seed)
                name_seed = NPCNameSeed(**seed_dict)
            except (json.JSONDecodeError, TypeError):
                pass
        full_name = generate_name(name_seed)
        npc_data.full_name = full_name.to_dict()
        npc_data.given_name = full_name.given_name

        # DB 저장
        npc_model = NPCModel(
            npc_id=npc_id,
            full_name=json.dumps(npc_data.full_name, ensure_ascii=False),
            given_name=npc_data.given_name,
            hexaco=json.dumps(hexaco.to_dict()),
            character_sheet=json.dumps(npc_data.character_sheet),
            resonance_shield=json.dumps(npc_data.resonance_shield),
            axiom_proficiencies=json.dumps(npc_data.axiom_proficiencies),
            home_node=npc_data.home_node,
            current_node=npc_data.current_node,
            origin_type=npc_data.origin_type,
            origin_entity_type=npc_data.origin_entity_type,
            role=npc_data.role,
        )
        self._db.add(npc_model)

        # 배경 엔티티 승격 마킹
        row.promoted = True
        row.promoted_npc_id = npc_id
        self._db.flush()

        # 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_PROMOTED,
                data={
                    "npc_id": npc_id,
                    "origin_type": entity.entity_type.value,
                    "node_id": entity.current_node,
                },
                source="npc_service",
            )
        )

        logger.info(f"Entity promoted: {entity_id} → NPC {npc_id}")
        return npc_data

    def _register_worldpool(self, entity_id: str) -> None:
        """WorldPool 등록 (내부)"""
        existing = (
            self._db.query(WorldPoolModel)
            .filter(WorldPoolModel.entity_id == entity_id)
            .first()
        )
        if existing:
            return

        row = (
            self._db.query(BackgroundEntityModel)
            .filter(BackgroundEntityModel.entity_id == entity_id)
            .first()
        )
        if row is None:
            return

        wp = WorldPoolModel(
            entity_id=entity_id,
            entity_type=row.entity_type,
            promotion_score=row.promotion_score,
            last_known_node=row.current_node,
            registered_turn=row.created_turn,
        )
        self._db.add(wp)
        self._db.flush()

        logger.info(f"WorldPool registered: {entity_id}")

    # ── 퀘스트용 NPC 생성 ────────────────────────────────────

    def create_npc_for_quest(self, role: str, node_id: str) -> NPCData:
        """퀘스트용 NPC 직접 생성"""
        npc_id = str(uuid.uuid4())
        hexaco = generate_hexaco(role)
        full_name = generate_name(NPCNameSeed(role=role))

        npc_data = NPCData(
            npc_id=npc_id,
            full_name=full_name.to_dict(),
            given_name=full_name.given_name,
            hexaco=hexaco,
            current_node=node_id,
            origin_type="scripted",
            role=role,
        )

        npc_model = NPCModel(
            npc_id=npc_id,
            full_name=json.dumps(npc_data.full_name, ensure_ascii=False),
            given_name=npc_data.given_name,
            hexaco=json.dumps(hexaco.to_dict()),
            character_sheet=json.dumps(npc_data.character_sheet),
            resonance_shield=json.dumps(npc_data.resonance_shield),
            axiom_proficiencies=json.dumps(npc_data.axiom_proficiencies),
            home_node=None,
            current_node=node_id,
            origin_type="scripted",
            origin_entity_type=None,
            role=role,
        )
        self._db.add(npc_model)
        self._db.flush()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.NPC_CREATED,
                data={"npc_id": npc_id, "role": role, "node_id": node_id},
                source="npc_service",
            )
        )

        logger.info(f"Quest NPC created: {npc_id} ({role}) at {node_id}")
        return npc_data

    # ── 기억 ─────────────────────────────────────────────────

    def save_memory(
        self,
        npc_id: str,
        memory_type: str,
        summary: str,
        turn: int,
        emotional_valence: float = 0.0,
    ) -> NPCMemory:
        """기억 저장 + Tier 관리"""
        memory_id = str(uuid.uuid4())
        mem = create_memory(
            npc_id=npc_id,
            memory_type=memory_type,
            summary=summary,
            turn=turn,
            emotional_valence=emotional_valence,
            memory_id=memory_id,
        )

        # Tier 1 슬롯 배치 시도
        tier1_memories = self._get_tier1_memories(npc_id)
        evicted = assign_tier1_slot(tier1_memories, mem)

        if evicted:
            # 밀려난 기억 Tier 2로 강등 (DB 업데이트)
            evicted_row = (
                self._db.query(NPCMemoryModel)
                .filter(NPCMemoryModel.memory_id == evicted.memory_id)
                .first()
            )
            if evicted_row:
                evicted_row.tier = 2
                evicted_row.is_fixed = False
                evicted_row.fixed_slot = None

        # 새 기억 저장
        mem_model = NPCMemoryModel(
            memory_id=memory_id,
            npc_id=npc_id,
            tier=mem.tier,
            memory_type=mem.memory_type,
            summary=mem.summary,
            emotional_valence=mem.emotional_valence,
            importance=mem.importance,
            turn_created=turn,
            is_fixed=mem.is_fixed,
            fixed_slot=mem.fixed_slot,
        )
        self._db.add(mem_model)
        self._db.flush()

        return mem

    def get_memories_for_context(
        self, npc_id: str, relationship_status: str = "stranger"
    ) -> List[NPCMemory]:
        """LLM 컨텍스트용 기억 조회"""
        rows = (
            self._db.query(NPCMemoryModel).filter(NPCMemoryModel.npc_id == npc_id).all()
        )
        all_memories = [self._memory_from_orm(r) for r in rows]
        return _get_memories_for_context(all_memories, relationship_status)

    def _get_tier1_memories(self, npc_id: str) -> List[NPCMemory]:
        """NPC의 Tier 1 기억 목록 조회"""
        rows = (
            self._db.query(NPCMemoryModel)
            .filter(
                NPCMemoryModel.npc_id == npc_id,
                NPCMemoryModel.tier == 1,
            )
            .all()
        )
        return [self._memory_from_orm(r) for r in rows]

    # ── ORM ↔ Core 변환 ─────────────────────────────────────

    @staticmethod
    def _entity_from_orm(model: BackgroundEntityModel) -> BackgroundEntity:
        """ORM → Core BackgroundEntity"""
        return BackgroundEntity(
            entity_id=model.entity_id,
            entity_type=EntityType(model.entity_type),
            current_node=model.current_node,
            home_node=model.home_node,
            role=model.role,
            appearance_seed=json.loads(model.appearance_seed)
            if model.appearance_seed
            else {},
            promotion_score=model.promotion_score,
            promoted=model.promoted,
            name_seed=json.loads(model.name_seed) if model.name_seed else None,
            slot_id=model.slot_id,
            temp_combat_id=model.temp_combat_id,
            created_turn=model.created_turn,
        )

    @staticmethod
    def _npc_from_orm(model: NPCModel) -> NPCData:
        """ORM → Core NPCData"""
        hexaco_dict = json.loads(model.hexaco) if model.hexaco else {}
        return NPCData(
            npc_id=model.npc_id,
            full_name=json.loads(model.full_name) if model.full_name else {},
            given_name=model.given_name,
            hexaco=HEXACO(**hexaco_dict) if hexaco_dict else HEXACO(),
            character_sheet=json.loads(model.character_sheet)
            if model.character_sheet
            else {},
            resonance_shield=json.loads(model.resonance_shield)
            if model.resonance_shield
            else {},
            axiom_proficiencies=json.loads(model.axiom_proficiencies)
            if model.axiom_proficiencies
            else {},
            home_node=model.home_node,
            current_node=model.current_node,
            routine=json.loads(model.routine) if model.routine else None,
            state=json.loads(model.state) if model.state else {},
            lord_id=model.lord_id,
            faction_id=model.faction_id,
            loyalty=model.loyalty,
            currency=model.currency,
            origin_type=model.origin_type,
            origin_entity_type=model.origin_entity_type,
            role=model.role,
            tags=json.loads(model.tags) if model.tags else [],
        )

    @staticmethod
    def _memory_from_orm(model: NPCMemoryModel) -> NPCMemory:
        """ORM → Core NPCMemory"""
        return NPCMemory(
            memory_id=model.memory_id,
            npc_id=model.npc_id,
            tier=model.tier,
            memory_type=model.memory_type,
            summary=model.summary,
            emotional_valence=model.emotional_valence,
            importance=model.importance,
            embedding=model.embedding,
            turn_created=model.turn_created,
            related_node=model.related_node,
            related_entity_id=model.related_entity_id,
            is_fixed=model.is_fixed,
            fixed_slot=model.fixed_slot,
        )
