"""RelationshipModule — GameModule 인터페이스 구현

relationship-system.md 섹션 8 대응.
RelationshipService를 래핑하여 ModuleManager 생명주기에 통합.
EventBus 구독: npc_promoted, dialogue_ended, attitude_request.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.logging import get_logger
from src.core.npc.models import HEXACO
from src.core.relationship.models import AttitudeContext, Relationship
from src.modules.base import Action, GameContext, GameModule
from src.services.relationship_service import RelationshipService

logger = get_logger(__name__)


class RelationshipModule(GameModule):
    """관계 시스템 모듈

    담당:
    - 관계 CRUD 공개 API
    - 턴 처리: familiarity 시간 감쇠
    - EventBus 구독 (npc_promoted, dialogue_ended, attitude_request)

    의존성: ["npc_core"] (NPC 데이터 필요)
    """

    def __init__(self, db_session: Session, event_bus: EventBus) -> None:
        super().__init__()
        self._db = db_session
        self._bus = event_bus
        self._service: Optional[RelationshipService] = None

    @property
    def name(self) -> str:
        return "relationship"

    @property
    def dependencies(self) -> List[str]:
        return ["npc_core"]

    def on_enable(self) -> None:
        """모듈 활성화: RelationshipService 생성 + EventBus 구독"""
        self._service = RelationshipService(self._db, self._bus)
        self._bus.subscribe(EventTypes.NPC_PROMOTED, self._handle_npc_promoted)
        self._bus.subscribe(EventTypes.DIALOGUE_ENDED, self._handle_dialogue_ended)
        self._bus.subscribe(EventTypes.ATTITUDE_REQUEST, self._handle_attitude_request)
        logger.info("relationship 모듈 활성화")

    def on_disable(self) -> None:
        """모듈 비활성화: EventBus 구독 해제"""
        self._bus.unsubscribe(EventTypes.NPC_PROMOTED, self._handle_npc_promoted)
        self._bus.unsubscribe(EventTypes.DIALOGUE_ENDED, self._handle_dialogue_ended)
        self._bus.unsubscribe(
            EventTypes.ATTITUDE_REQUEST, self._handle_attitude_request
        )
        self._service = None
        logger.info("relationship 모듈 비활성화")

    def on_turn(self, context: GameContext) -> None:
        """턴 처리: familiarity 시간 감쇠"""
        if self._service is None:
            return
        self._service.process_familiarity_decay(context.current_turn)

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 — 현재 패스 (관계 데이터는 요청 시 조회)"""
        pass

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """관계 관련 행동 목록 — 현재 없음"""
        return []

    # ── EventBus 핸들러 ────────────────────────────────────────

    def _handle_npc_promoted(self, event: GameEvent) -> None:
        """NPC 승격 시 같은 노드 NPC들과 초기 관계 생성"""
        if self._service is None:
            logger.warning("relationship: service 미초기화 상태에서 npc_promoted 수신")
            return

        npc_id = event.data["npc_id"]
        node_id = event.data["node_id"]
        self._service.create_initial_npc_relationships(npc_id, node_id)
        logger.info(f"relationship: npc_promoted 처리 완료 npc={npc_id} node={node_id}")

    def _handle_dialogue_ended(self, event: GameEvent) -> None:
        """대화 종료 시 META에서 관계 변동 추출 + 상태 전이 판정"""
        if self._service is None:
            logger.warning(
                "relationship: service 미초기화 상태에서 dialogue_ended 수신"
            )
            return

        source_id = event.data["player_id"]
        target_id = event.data["npc_id"]
        delta = event.data.get("relationship_delta", {})
        if delta:
            affinity_delta: float = delta.get("affinity", 0.0)
            reason: str = delta.get("reason", "dialogue")
            self._service.apply_dialogue_delta(
                source_id, target_id, affinity_delta, reason
            )

    def _handle_attitude_request(self, event: GameEvent) -> None:
        """태도 태그 요청 처리 → attitude_response 발행"""
        if self._service is None:
            logger.warning(
                "relationship: service 미초기화 상태에서 attitude_request 수신"
            )
            return

        npc_id: str = event.data["npc_id"]
        target_id: str = event.data["target_id"]
        hexaco: HEXACO = event.data["hexaco"]
        memory_tags: List[str] = event.data.get("memory_tags", [])
        include_opinions: bool = event.data.get("include_npc_opinions", False)

        attitude = self._service.generate_attitude(
            npc_id, target_id, hexaco, memory_tags, include_opinions
        )

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.ATTITUDE_RESPONSE,
                data={
                    "request_id": event.data.get("request_id"),
                    "npc_id": npc_id,
                    "target_id": target_id,
                    "attitude_tags": attitude.attitude_tags,
                    "relationship_status": attitude.relationship_status,
                    "npc_opinions": attitude.npc_opinions,
                },
                source="relationship_module",
            )
        )

    # ── 공개 쿼리 API ──────────────────────────────────────────

    def get_relationship(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
    ) -> Optional[Relationship]:
        """관계 조회"""
        if self._service is None:
            return None
        return self._service.get_relationship(
            source_type, source_id, target_type, target_id
        )

    def get_relationships_for(
        self, source_type: str, source_id: str
    ) -> List[Relationship]:
        """특정 엔티티의 전체 관계 조회"""
        if self._service is None:
            return []
        return self._service.get_relationships_for(source_type, source_id)

    def generate_attitude(
        self,
        npc_id: str,
        target_id: str,
        hexaco: HEXACO,
        memory_tags: List[str],
        include_npc_opinions: bool = False,
    ) -> Optional[AttitudeContext]:
        """태도 태그 생성"""
        if self._service is None:
            return None
        return self._service.generate_attitude(
            npc_id, target_id, hexaco, memory_tags, include_npc_opinions
        )
