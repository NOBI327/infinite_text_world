"""Relationship Service — Core와 DB를 연결

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""

import json
import random
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.logging import get_logger
from src.core.npc.models import HEXACO
from src.core.relationship.attitude import generate_attitude_tags
from src.core.relationship.calculations import (
    apply_affinity_damping,
    apply_familiarity_decay,
    apply_trust_damping,
    clamp_affinity,
    clamp_meta_delta,
    clamp_trust,
)
from src.core.relationship.models import (
    AttitudeContext,
    Relationship,
    RelationshipStatus,
)
from src.core.relationship.npc_opinions import build_npc_opinions
from src.core.relationship.reversals import (
    ReversalType,
    apply_reversal as core_apply_reversal,
)
from src.core.relationship.transitions import evaluate_transition
from src.db.models_v2 import NPCModel, RelationshipModel

logger = get_logger(__name__)


class RelationshipService:
    """관계 CRUD, 수치 변동, 반전, 감쇠, 태도 생성

    relationship-system.md 섹션 7, 8 대응.
    """

    def __init__(self, db_session: Session, event_bus: EventBus) -> None:
        self._db = db_session
        self._bus = event_bus

    # ── 조회 ─────────────────────────────────────────────────

    def get_relationship(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> Optional[Relationship]:
        """DB 조회 → Core 모델 변환"""
        row = (
            self._db.query(RelationshipModel)
            .filter(
                RelationshipModel.source_type == source_type,
                RelationshipModel.source_id == source_id,
                RelationshipModel.target_type == target_type,
                RelationshipModel.target_id == target_id,
            )
            .first()
        )
        if row is None:
            return None
        return self._relationship_from_orm(row)

    def get_relationships_for(
        self, source_type: str, source_id: str
    ) -> List[Relationship]:
        """특정 엔티티의 전체 관계 조회"""
        rows = (
            self._db.query(RelationshipModel)
            .filter(
                RelationshipModel.source_type == source_type,
                RelationshipModel.source_id == source_id,
            )
            .all()
        )
        return [self._relationship_from_orm(r) for r in rows]

    # ── 생성 ─────────────────────────────────────────────────

    def create_relationship(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        **initial_values: Any,
    ) -> Relationship:
        """신규 관계 생성 + DB 저장"""
        rel_id = str(uuid.uuid4())

        rel = Relationship(
            relationship_id=rel_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            affinity=initial_values.get("affinity", 0.0),
            trust=initial_values.get("trust", 0.0),
            familiarity=initial_values.get("familiarity", 0),
            status=initial_values.get("status", RelationshipStatus.STRANGER),
            tags=initial_values.get("tags", []),
            last_interaction_turn=initial_values.get("last_interaction_turn", 0),
        )

        model = RelationshipModel(
            relationship_id=rel_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            affinity=rel.affinity,
            trust=rel.trust,
            familiarity=rel.familiarity,
            status=rel.status.value,
            tags=json.dumps(rel.tags),
            last_interaction_turn=rel.last_interaction_turn,
        )
        self._db.add(model)
        self._db.flush()

        logger.info(
            f"Relationship created: {source_type}:{source_id} → "
            f"{target_type}:{target_id} ({rel_id})"
        )
        return rel

    # ── 대화 delta ───────────────────────────────────────────

    def apply_dialogue_delta(
        self,
        source_id: str,
        target_id: str,
        affinity_delta: float,
        reason: str,
    ) -> Relationship:
        """대화 종료 후: META에서 받은 delta → 감쇠 적용 → DB 갱신 → 상태 전이 체크"""
        row = self._get_relationship_row("player", source_id, "npc", target_id)
        if row is None:
            self.create_relationship("player", source_id, "npc", target_id)
            row = self._get_relationship_row("player", source_id, "npc", target_id)

        old_status = row.status

        # Clamp META delta to -5~+5
        clamped_delta = clamp_meta_delta(affinity_delta)

        # Apply affinity damping
        damped_delta = apply_affinity_damping(row.affinity, clamped_delta)

        # Update values
        row.affinity = clamp_affinity(row.affinity + damped_delta)
        row.familiarity = row.familiarity + 1  # 대화 1회당 +1 자동 증가
        self._db.flush()

        # Check transition
        rel = self._relationship_from_orm(row)
        new_status = evaluate_transition(rel)
        if new_status is not None:
            row.status = new_status.value
            self._db.flush()
            rel = self._relationship_from_orm(row)

            self._bus.emit(
                GameEvent(
                    event_type=EventTypes.RELATIONSHIP_CHANGED,
                    data={
                        "source_id": source_id,
                        "target_id": target_id,
                        "field": "status",
                        "old_value": old_status,
                        "new_value": new_status.value,
                        "old_status": old_status,
                        "new_status": new_status.value,
                    },
                    source="relationship_service",
                )
            )

        logger.info(
            f"Dialogue delta applied: {source_id}→{target_id} "
            f"affinity_delta={clamped_delta} (damped={damped_delta:.2f}), "
            f"reason={reason}"
        )
        return rel

    # ── 행동 delta ───────────────────────────────────────────

    def apply_action_delta(
        self,
        source_id: str,
        target_id: str,
        affinity_delta: float,
        trust_delta: float,
        familiarity_delta: int,
        reason: str,
    ) -> Relationship:
        """행동(부탁 수행, 선물 등) 후 수치 변동 → 감쇠 적용 → DB 갱신 → 전이 체크"""
        row = self._get_relationship_row("player", source_id, "npc", target_id)
        if row is None:
            self.create_relationship("player", source_id, "npc", target_id)
            row = self._get_relationship_row("player", source_id, "npc", target_id)

        old_status = row.status

        # Apply damping
        damped_affinity = apply_affinity_damping(row.affinity, affinity_delta)
        damped_trust = apply_trust_damping(row.trust, trust_delta)

        # Update values
        row.affinity = clamp_affinity(row.affinity + damped_affinity)
        row.trust = clamp_trust(row.trust + damped_trust)
        row.familiarity = row.familiarity + familiarity_delta
        self._db.flush()

        # Check transition
        rel = self._relationship_from_orm(row)
        new_status = evaluate_transition(rel)
        if new_status is not None:
            row.status = new_status.value
            self._db.flush()
            rel = self._relationship_from_orm(row)

            self._bus.emit(
                GameEvent(
                    event_type=EventTypes.RELATIONSHIP_CHANGED,
                    data={
                        "source_id": source_id,
                        "target_id": target_id,
                        "field": "status",
                        "old_value": old_status,
                        "new_value": new_status.value,
                        "old_status": old_status,
                        "new_status": new_status.value,
                    },
                    source="relationship_service",
                )
            )

        logger.info(
            f"Action delta applied: {source_id}→{target_id} "
            f"affinity={damped_affinity:.2f}, trust={damped_trust:.2f}, "
            f"familiarity={familiarity_delta}, reason={reason}"
        )
        return rel

    # ── 반전 ─────────────────────────────────────────────────

    def apply_reversal(
        self,
        source_id: str,
        target_id: str,
        reversal_type: str,
    ) -> Relationship:
        """반전 이벤트 적용 → DB 갱신 → relationship_reversed 이벤트 발행"""
        row = self._get_relationship_row("player", source_id, "npc", target_id)
        if row is None:
            raise ValueError(f"Relationship not found: {source_id} → {target_id}")

        old_rel = self._relationship_from_orm(row)
        old_status = old_rel.status.value

        # Apply reversal via Core
        new_rel = core_apply_reversal(old_rel, ReversalType(reversal_type))

        # Update DB
        row.affinity = new_rel.affinity
        row.trust = new_rel.trust
        row.familiarity = new_rel.familiarity
        row.status = new_rel.status.value
        row.tags = json.dumps(new_rel.tags)
        self._db.flush()

        # Emit event
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.RELATIONSHIP_REVERSED,
                data={
                    "source_id": source_id,
                    "target_id": target_id,
                    "reversal_type": reversal_type,
                    "old_status": old_status,
                    "new_status": new_rel.status.value,
                },
                source="relationship_service",
            )
        )

        logger.info(
            f"Reversal applied: {source_id}→{target_id} "
            f"type={reversal_type}, {old_status}→{new_rel.status.value}"
        )
        return new_rel

    # ── familiarity 시간 감쇠 ────────────────────────────────

    def process_familiarity_decay(self, current_turn: int) -> int:
        """전체 관계의 familiarity 시간 감쇠 처리. 감쇠된 관계 수 반환."""
        rows = self._db.query(RelationshipModel).all()
        decayed_count = 0

        for row in rows:
            days_since = current_turn - row.last_interaction_turn
            if days_since <= 0:
                continue

            new_fam = apply_familiarity_decay(row.familiarity, days_since)
            if new_fam != row.familiarity:
                row.familiarity = new_fam
                decayed_count += 1

        if decayed_count > 0:
            self._db.flush()
            logger.info(
                f"Familiarity decay: {decayed_count} relationships affected "
                f"(turn={current_turn})"
            )

        return decayed_count

    # ── 초기 NPC 관계 생성 ───────────────────────────────────

    def create_initial_npc_relationships(
        self, new_npc_id: str, node_id: str
    ) -> List[Relationship]:
        """승격 시: 같은 노드 NPC들과 초기 관계 생성 (섹션 7.1)"""
        existing_npcs = (
            self._db.query(NPCModel)
            .filter(
                NPCModel.current_node == node_id,
                NPCModel.npc_id != new_npc_id,
            )
            .all()
        )

        relationships: List[Relationship] = []

        for npc in existing_npcs:
            rel = self.create_relationship(
                source_type="npc",
                source_id=new_npc_id,
                target_type="npc",
                target_id=npc.npc_id,
                affinity=round(random.uniform(-10, 20), 1),
                trust=round(random.uniform(10, 30), 1),
                familiarity=5,
                status=RelationshipStatus.ACQUAINTANCE,
            )
            relationships.append(rel)

        logger.info(
            f"Initial NPC relationships: {new_npc_id} at {node_id}, "
            f"{len(relationships)} relationships created"
        )
        return relationships

    # ── 태도 생성 ────────────────────────────────────────────

    def generate_attitude(
        self,
        npc_id: str,
        target_id: str,
        hexaco: HEXACO,
        memory_tags: List[str],
        include_npc_opinions: bool = False,
    ) -> AttitudeContext:
        """태도 태그 생성 (Core 파이프라인 호출)"""
        # PC→NPC 관계 조회 (target_id = player)
        rel = self.get_relationship("player", target_id, "npc", npc_id)
        if rel is None:
            # 관계 없으면 기본값으로 생성
            rel = Relationship(
                relationship_id="",
                source_type="player",
                source_id=target_id,
                target_type="npc",
                target_id=npc_id,
            )

        # Core pipeline
        attitude = generate_attitude_tags(rel, hexaco, memory_tags)

        # NPC간 의견
        if include_npc_opinions:
            npc_rels = self.get_relationships_for("npc", npc_id)
            attitude.npc_opinions = build_npc_opinions(npc_id, npc_rels)

        return attitude

    # ── ORM ↔ Core 변환 ─────────────────────────────────────

    @staticmethod
    def _relationship_from_orm(model: RelationshipModel) -> Relationship:
        """ORM → Core Relationship"""
        return Relationship(
            relationship_id=model.relationship_id,
            source_type=model.source_type,
            source_id=model.source_id,
            target_type=model.target_type,
            target_id=model.target_id,
            affinity=model.affinity,
            trust=model.trust,
            familiarity=model.familiarity,
            status=RelationshipStatus(model.status),
            tags=json.loads(model.tags) if model.tags else [],
            last_interaction_turn=model.last_interaction_turn,
            created_at=model.created_at or "",
            updated_at=model.updated_at or "",
        )

    @staticmethod
    def _relationship_to_orm(rel: Relationship) -> Dict[str, Any]:
        """Core → ORM dict"""
        return {
            "relationship_id": rel.relationship_id,
            "source_type": rel.source_type,
            "source_id": rel.source_id,
            "target_type": rel.target_type,
            "target_id": rel.target_id,
            "affinity": rel.affinity,
            "trust": rel.trust,
            "familiarity": rel.familiarity,
            "status": rel.status.value,
            "tags": json.dumps(rel.tags),
            "last_interaction_turn": rel.last_interaction_turn,
        }

    # ── 내부 헬퍼 ────────────────────────────────────────────

    def _get_relationship_row(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> Optional[RelationshipModel]:
        """DB에서 관계 행 직접 조회 (업데이트용)"""
        return (
            self._db.query(RelationshipModel)
            .filter(
                RelationshipModel.source_type == source_type,
                RelationshipModel.source_id == source_id,
                RelationshipModel.target_type == target_type,
                RelationshipModel.target_id == target_id,
            )
            .first()
        )
