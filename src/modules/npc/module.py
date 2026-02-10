"""NPCCoreModule - NPC 시스템 모듈 (GameModule 래핑)

NPCService를 래핑하여 ModuleManager 생명주기에 통합.
EventBus 구독(npc_needed)으로 다른 모듈이 NPC 생성을 요청할 수 있다.

docs/30_technical/module-architecture.md 섹션 3.2 "[B] npc_core" 참조.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.logging import get_logger
from src.core.npc.models import BackgroundEntity, NPCData
from src.modules.base import Action, GameContext, GameModule
from src.services.npc_service import NPCService

logger = get_logger(__name__)


class NPCCoreModule(GameModule):
    """NPC 핵심 시스템 모듈

    담당:
    - NPC/배경 엔티티 조회 API
    - 승격 점수 관리
    - npc_needed 이벤트 핸들링 (퀘스트용 NPC 자동 생성)
    - 턴 처리 시 기본 로직 (확장 예정)

    의존성: ["geography"] (노드 정보 필요)
    """

    def __init__(self, db_session: Session, event_bus: EventBus) -> None:
        super().__init__()
        self._db = db_session
        self._bus = event_bus
        self._service: Optional[NPCService] = None

    @property
    def name(self) -> str:
        return "npc_core"

    @property
    def dependencies(self) -> List[str]:
        return ["geography"]

    def on_enable(self) -> None:
        """모듈 활성화: NPCService 생성 + EventBus 구독"""
        self._service = NPCService(self._db, self._bus)
        self._bus.subscribe(EventTypes.NPC_NEEDED, self._handle_npc_needed)
        logger.info("npc_core 모듈 활성화")

    def on_disable(self) -> None:
        """모듈 비활성화: EventBus 구독 해제"""
        self._bus.unsubscribe(EventTypes.NPC_NEEDED, self._handle_npc_needed)
        self._service = None
        logger.info("npc_core 모듈 비활성화")

    def on_turn(self, context: GameContext) -> None:
        """턴 처리 — 현재는 패스. 향후 NPC 루틴/이동 처리."""
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 시 NPC/엔티티 정보를 context.extra에 저장"""
        if self._service is None:
            return

        entities = self._service.get_background_entities_at_node(node_id)
        npcs = self._service.get_npcs_at_node(node_id)

        context.extra["npc_core"] = {
            "background_entities": entities,
            "npcs": npcs,
        }

        logger.debug(
            f"npc_core.on_node_enter: {node_id} "
            f"entities={len(entities)} npcs={len(npcs)}"
        )

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """NPC 관련 행동 목록: 노드에 NPC가 있으면 talk 액션 제공"""
        actions: List[Action] = []

        npc_data = context.extra.get("npc_core", {})
        npcs: List[NPCData] = npc_data.get("npcs", [])

        for npc in npcs:
            actions.append(
                Action(
                    name="talk",
                    display_name=f"{npc.given_name}와 대화",
                    module_name=self.name,
                    params={"npc_id": npc.npc_id},
                )
            )

        return actions

    # ── EventBus 핸들러 ────────────────────────────────────────

    def _handle_npc_needed(self, event: GameEvent) -> None:
        """npc_needed 이벤트 → 퀘스트용 NPC 생성"""
        if self._service is None:
            logger.warning("npc_core: service 미초기화 상태에서 npc_needed 수신")
            return

        role = event.data.get("role", "villager")
        node_id = event.data.get("node_id", "0_0")

        self._service.create_npc_for_quest(role, node_id)
        logger.info(f"npc_core: npc_needed 처리 완료 role={role} node={node_id}")

    # ── 공개 쿼리 API ──────────────────────────────────────────

    def get_npcs_at_node(self, node_id: str) -> List[NPCData]:
        """노드의 NPC 목록 조회"""
        if self._service is None:
            return []
        return self._service.get_npcs_at_node(node_id)

    def get_npc_by_id(self, npc_id: str) -> Optional[NPCData]:
        """ID로 NPC 조회"""
        if self._service is None:
            return None
        return self._service.get_npc_by_id(npc_id)

    def get_background_entities_at_node(self, node_id: str) -> List[BackgroundEntity]:
        """노드의 배경 엔티티 목록 조회"""
        if self._service is None:
            return []
        return self._service.get_background_entities_at_node(node_id)

    def add_promotion_score(self, entity_id: str, action: str) -> str:
        """승격 점수 추가. Returns: 'none' / 'worldpool' / 'promoted'"""
        if self._service is None:
            return "none"
        return self._service.add_promotion_score(entity_id, action)
