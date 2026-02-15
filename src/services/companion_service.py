"""동행 Service — Core↔DB 연결, EventBus 통신

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""

import json
import logging
import uuid

from sqlalchemy.orm import Session

from src.core.companion.acceptance import (
    roll_quest_companion,
    voluntary_companion_accept,
)
from src.core.companion.conditions import (
    check_condition_expired,
    generate_condition_data,
    roll_condition,
)
from src.core.companion.models import CompanionState
from src.core.companion.return_logic import determine_return_destination
from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.db.models_v2 import CompanionLogModel, CompanionModel

logger = logging.getLogger(__name__)

# Alpha: 동시 동행 1명 제한
MAX_COMPANIONS = 1

# 이동 서술 템플릿
COMPANION_MOVE_TEMPLATE = "{npc_name}이(가) 뒤따라온다."

# 해산 서술 템플릿
DISBAND_TEMPLATES: dict[str, str] = {
    "pc_dismiss": "{npc_name}에게 작별을 고한다.",
    "quest_complete": "{npc_name}이(가) 감사를 표하며 자리를 잡는다.",
    "quest_failed": "{npc_name}이(가) 침울한 표정으로 돌아선다.",
    "condition_expired": "{npc_name}: '약속한 기한이 됐어. 나는 여기서 돌아가야 해.'",
    "npc_dead": "",
}


class CompanionService:
    """동행 CRUD + 비즈니스 로직"""

    def __init__(self, db: Session, event_bus: EventBus):
        self._db = db
        self._bus = event_bus
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독"""
        self._bus.subscribe(EventTypes.PLAYER_MOVED, self._on_player_moved)
        self._bus.subscribe(EventTypes.QUEST_ACTIVATED, self._on_quest_activated)
        self._bus.subscribe(EventTypes.QUEST_COMPLETED, self._on_quest_completed)
        self._bus.subscribe(EventTypes.QUEST_FAILED, self._on_quest_failed)
        self._bus.subscribe(EventTypes.QUEST_ABANDONED, self._on_quest_abandoned)
        self._bus.subscribe(EventTypes.NPC_DIED, self._on_npc_died)
        self._bus.subscribe(EventTypes.TURN_PROCESSED, self._on_turn_processed)

    # === 동행 조회 ===

    def get_active_companion(self, player_id: str) -> CompanionState | None:
        """현재 활성 동행 조회. Alpha: 최대 1명."""
        orm = (
            self._db.query(CompanionModel)
            .filter(
                CompanionModel.player_id == player_id,
                CompanionModel.status == "active",
            )
            .first()
        )
        if orm is None:
            return None
        return self._companion_to_core(orm)

    def is_companion(self, player_id: str, npc_id: str) -> bool:
        """해당 NPC가 현재 PC의 동행인지 확인.
        ObjectiveWatcher가 escort 달성 판정에 사용.
        """
        companion = self.get_active_companion(player_id)
        return companion is not None and companion.npc_id == npc_id

    # === 동행 요청 ===

    def request_quest_companion(
        self,
        player_id: str,
        npc_id: str,
        quest_id: str,
        npc_hexaco_a: float,
        is_rescue: bool,
        npc_origin_node: str,
        current_turn: int,
    ) -> tuple[bool, CompanionState | None]:
        """퀘스트 동행 요청.
        1. 이미 동행 있으면 거절 (Alpha 1인 제한)
        2. 수락 판정 (roll_quest_companion)
        3. 수락 시 CompanionState 생성 + DB 저장 + companion_joined 발행
        Returns: (수락 여부, CompanionState 또는 None)
        """
        if self.get_active_companion(player_id) is not None:
            logger.info("Quest companion rejected: already has companion")
            return False, None

        if not roll_quest_companion(npc_hexaco_a, is_rescue):
            logger.info("Quest companion rejected: roll failed")
            return False, None

        state = CompanionState(
            companion_id=str(uuid.uuid4()),
            player_id=player_id,
            npc_id=npc_id,
            companion_type="quest",
            quest_id=quest_id,
            status="active",
            started_turn=current_turn,
            origin_node_id=npc_origin_node,
        )

        orm = self._companion_to_orm(state)
        self._db.add(orm)
        self._db.commit()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.COMPANION_JOINED,
                data={
                    "companion_id": state.companion_id,
                    "player_id": player_id,
                    "npc_id": npc_id,
                    "companion_type": "quest",
                    "quest_id": quest_id,
                },
                source="companion_service",
            )
        )

        self._log_event(state.companion_id, current_turn, "joined")
        logger.info("Quest companion joined: npc=%s, quest=%s", npc_id, quest_id)
        return True, state

    def request_voluntary_companion(
        self,
        player_id: str,
        npc_id: str,
        relationship_status: str,
        trust: int,
        npc_hexaco: dict[str, float],
        npc_origin_node: str,
        current_turn: int,
        pc_destination_danger: float = 0.0,
    ) -> tuple[bool, str | None, CompanionState | None]:
        """자발적 동행 요청.
        1. 이미 동행 있으면 거절
        2. 수락 판정 (voluntary_companion_accept)
        3. 수락 시 조건 판정 (roll_condition)
        4. CompanionState 생성 + DB 저장 + companion_joined 발행
        Returns: (수락 여부, 거절/조건 사유, CompanionState 또는 None)
        """
        if self.get_active_companion(player_id) is not None:
            logger.info("Voluntary companion rejected: already has companion")
            return False, "already_has_companion", None

        accepted, reject_reason = voluntary_companion_accept(
            relationship_status, trust, npc_hexaco, pc_destination_danger
        )

        if not accepted:
            logger.info("Voluntary companion rejected: %s", reject_reason)
            return False, reject_reason, None

        # 조건 판정
        condition_type = None
        condition_data = None
        has_cond, cond_type = roll_condition()
        if has_cond and cond_type is not None:
            condition_type = cond_type
            condition_data = generate_condition_data(cond_type)

        state = CompanionState(
            companion_id=str(uuid.uuid4()),
            player_id=player_id,
            npc_id=npc_id,
            companion_type="voluntary",
            status="active",
            started_turn=current_turn,
            origin_node_id=npc_origin_node,
            condition_type=condition_type,
            condition_data=condition_data,
        )

        orm = self._companion_to_orm(state)
        self._db.add(orm)
        self._db.commit()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.COMPANION_JOINED,
                data={
                    "companion_id": state.companion_id,
                    "player_id": player_id,
                    "npc_id": npc_id,
                    "companion_type": "voluntary",
                    "quest_id": None,
                },
                source="companion_service",
            )
        )

        self._log_event(state.companion_id, current_turn, "joined")
        logger.info(
            "Voluntary companion joined: npc=%s, condition=%s",
            npc_id,
            condition_type,
        )
        return True, condition_type, state

    # === 해산 ===

    def dismiss_companion(
        self, player_id: str, current_turn: int
    ) -> CompanionState | None:
        """PC가 동행 해산. companion_disbanded 발행.
        Returns: 해산된 CompanionState 또는 None.
        """
        companion = self.get_active_companion(player_id)
        if companion is None:
            return None
        self._disband(companion, "pc_dismiss", current_turn)
        return companion

    def _disband(
        self,
        companion: CompanionState,
        reason: str,
        current_turn: int,
    ) -> None:
        """공통 해산 처리."""
        companion.status = "disbanded"
        companion.ended_turn = current_turn
        companion.disband_reason = reason

        # DB 갱신
        orm = (
            self._db.query(CompanionModel)
            .filter(CompanionModel.companion_id == companion.companion_id)
            .first()
        )
        if orm is not None:
            orm.status = "disbanded"
            orm.ended_turn = current_turn
            orm.disband_reason = reason
            self._db.commit()

        # 귀환 목적지 결정
        return_dest = determine_return_destination(
            npc_home_node=companion.origin_node_id or None,
            disband_reason=reason,
            quest_type=None,  # Beta: quest_type 전달 필요
            client_npc_node=None,  # Beta: client NPC 위치 전달 필요
        )

        # companion_disbanded 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.COMPANION_DISBANDED,
                data={
                    "companion_id": companion.companion_id,
                    "npc_id": companion.npc_id,
                    "disband_reason": reason,
                    "quest_id": companion.quest_id,
                    "return_destination": return_dest,
                },
                source="companion_service",
            )
        )

        self._log_event(
            companion.companion_id,
            current_turn,
            "disbanded",
            {"reason": reason, "return_destination": return_dest},
        )
        logger.info("Companion disbanded: npc=%s, reason=%s", companion.npc_id, reason)

    # === 이동 동기화 ===

    def _sync_companion_move(self, player_id: str, to_node: str) -> str | None:
        """동행 NPC 좌표를 PC 좌표로 갱신.
        Returns: 이동 서술 문자열 또는 None (동행 없음).
        """
        companion = self.get_active_companion(player_id)
        if companion is None:
            return None

        # companion_moved 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.COMPANION_MOVED,
                data={
                    "companion_id": companion.companion_id,
                    "npc_id": companion.npc_id,
                    "to_node": to_node,
                },
                source="companion_service",
            )
        )

        self._log_event(companion.companion_id, 0, "moved", {"to_node": to_node})

        return COMPANION_MOVE_TEMPLATE.format(npc_name=companion.npc_id)

    # === 대화 보정 ===

    def get_companion_dialogue_bonus(self, player_id: str, npc_id: str) -> int:
        """동행 NPC와의 대화 예산 보정. 동행 중이면 +2, 아니면 0."""
        if self.is_companion(player_id, npc_id):
            return 2
        return 0

    def build_companion_context(self, player_id: str) -> dict | None:
        """LLM 프롬프트용 동행 컨텍스트.
        동행 없으면 None.
        """
        companion = self.get_active_companion(player_id)
        if companion is None:
            return None

        context: dict = {
            "companion_context": {
                "is_companion": True,
                "companion_type": companion.companion_type,
                "npc_id": companion.npc_id,
                "turns_together": 0,  # 현재 턴 정보 없이 기본값
                "instruction": (
                    "이 NPC는 PC와 동행 중이다. "
                    "여행 동반자로서의 친밀감이 대화에 반영되어야 한다."
                ),
            }
        }

        if companion.condition_type and companion.condition_data:
            context["companion_context"]["condition"] = {
                "type": companion.condition_type,
                **companion.condition_data,
            }

        return context

    # === EventBus 핸들러 ===

    def _on_player_moved(self, event: GameEvent) -> None:
        """PC 이동 시 동행 NPC 이동 동기화."""
        player_id = event.data.get("player_id", "")
        to_node = event.data.get("to_node", "")
        if player_id and to_node:
            self._sync_companion_move(player_id, to_node)

    def _on_quest_activated(self, event: GameEvent) -> None:
        """escort 퀘스트 활성화 시 동행 자동 요청 판정."""
        quest_type = event.data.get("quest_type", "")
        if quest_type != "escort":
            return

        player_id = event.data.get("player_id", "")
        quest_id = event.data.get("quest_id", "")
        related_npc_ids = event.data.get("related_npc_ids", [])
        initial_status = event.data.get("initial_status", "present")

        if initial_status == "present" and related_npc_ids:
            npc_id = related_npc_ids[0]
            npc_hexaco_a = event.data.get("npc_hexaco_a", 0.5)
            is_rescue = event.data.get("is_rescue", False)
            npc_origin_node = event.data.get("npc_origin_node", "")
            current_turn = event.data.get("current_turn", 0)
            self.request_quest_companion(
                player_id=player_id,
                npc_id=npc_id,
                quest_id=quest_id,
                npc_hexaco_a=npc_hexaco_a,
                is_rescue=is_rescue,
                npc_origin_node=npc_origin_node,
                current_turn=current_turn,
            )

    def _on_quest_completed(self, event: GameEvent) -> None:
        """퀘스트 완료 시 퀘스트 동행 자동 해산."""
        quest_id = event.data.get("quest_id", "")
        current_turn = event.data.get("current_turn", 0)
        self._disband_by_quest(quest_id, "quest_complete", current_turn)

    def _on_quest_failed(self, event: GameEvent) -> None:
        """퀘스트 실패 시 퀘스트 동행 자동 해산."""
        quest_id = event.data.get("quest_id", "")
        current_turn = event.data.get("current_turn", 0)
        self._disband_by_quest(quest_id, "quest_failed", current_turn)

    def _on_quest_abandoned(self, event: GameEvent) -> None:
        """퀘스트 포기 시 퀘스트 동행 자동 해산."""
        quest_id = event.data.get("quest_id", "")
        current_turn = event.data.get("current_turn", 0)
        self._disband_by_quest(quest_id, "quest_failed", current_turn)

    def _disband_by_quest(self, quest_id: str, reason: str, current_turn: int) -> None:
        """퀘스트 ID로 동행 찾아서 해산."""
        orm = (
            self._db.query(CompanionModel)
            .filter(
                CompanionModel.quest_id == quest_id,
                CompanionModel.status == "active",
            )
            .first()
        )
        if orm is None:
            return
        companion = self._companion_to_core(orm)
        self._disband(companion, reason, current_turn)

    def _on_npc_died(self, event: GameEvent) -> None:
        """동행 NPC 사망 시 강제 해산."""
        npc_id = event.data.get("npc_id", "")
        current_turn = event.data.get("current_turn", 0)
        orm = (
            self._db.query(CompanionModel)
            .filter(
                CompanionModel.npc_id == npc_id,
                CompanionModel.status == "active",
            )
            .first()
        )
        if orm is None:
            return
        companion = self._companion_to_core(orm)
        self._disband(companion, "npc_dead", current_turn)

    def _on_turn_processed(self, event: GameEvent) -> None:
        """매 턴 조건 만료 체크."""
        player_id = event.data.get("player_id", "")
        current_turn = event.data.get("turn_number", 0)
        pc_node = event.data.get("pc_node", "")
        node_danger = event.data.get("node_danger", 0.0)

        companion = self.get_active_companion(player_id)
        if companion is None or companion.condition_type is None:
            return
        if companion.condition_data is None:
            return

        expired, warned = check_condition_expired(
            companion.condition_type,
            companion.condition_data,
            companion.started_turn,
            current_turn,
            pc_node,
            node_danger,
        )

        if expired:
            self._disband(companion, "condition_expired", current_turn)
        elif warned and not companion.condition_data.get("warned", False):
            # 경고 상태 DB 갱신
            companion.condition_data["warned"] = True
            orm = (
                self._db.query(CompanionModel)
                .filter(CompanionModel.companion_id == companion.companion_id)
                .first()
            )
            if orm is not None:
                orm.condition_data = json.dumps(companion.condition_data)
                self._db.commit()
            self._log_event(companion.companion_id, current_turn, "condition_warned")

    # === ORM ↔ Core 변환 ===

    def _companion_to_core(self, orm: CompanionModel) -> CompanionState:
        """ORM → Core. condition_data JSON 역직렬화."""
        condition_data = None
        if orm.condition_data:
            condition_data = json.loads(orm.condition_data)

        return CompanionState(
            companion_id=orm.companion_id,
            player_id=orm.player_id,
            npc_id=orm.npc_id,
            companion_type=orm.companion_type,
            quest_id=orm.quest_id,
            status=orm.status,
            started_turn=orm.started_turn,
            ended_turn=orm.ended_turn,
            disband_reason=orm.disband_reason,
            condition_type=orm.condition_type,
            condition_data=condition_data,
            condition_met=orm.condition_met,
            origin_node_id=orm.origin_node_id,
            created_at=orm.created_at,
        )

    def _companion_to_orm(self, core: CompanionState) -> CompanionModel:
        """Core → ORM. condition_data JSON 직렬화."""
        condition_data_str = None
        if core.condition_data is not None:
            condition_data_str = json.dumps(core.condition_data)

        return CompanionModel(
            companion_id=core.companion_id,
            player_id=core.player_id,
            npc_id=core.npc_id,
            companion_type=core.companion_type,
            quest_id=core.quest_id,
            status=core.status,
            started_turn=core.started_turn,
            ended_turn=core.ended_turn,
            disband_reason=core.disband_reason,
            condition_type=core.condition_type,
            condition_data=condition_data_str,
            condition_met=core.condition_met,
            origin_node_id=core.origin_node_id,
        )

    def _log_event(
        self,
        companion_id: str,
        turn: int,
        event_type: str,
        data: dict | None = None,
    ) -> None:
        """companion_log 기록."""
        log = CompanionLogModel(
            companion_id=companion_id,
            turn_number=turn,
            event_type=event_type,
            data=json.dumps(data) if data else None,
        )
        self._db.add(log)
        self._db.commit()
