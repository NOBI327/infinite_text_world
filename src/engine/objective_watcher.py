"""ObjectiveWatcher — 활성 퀘스트 목표 감시 + 달성/실패 판정.

engine(ModuleManager) 내부 컴포넌트.
각 모듈의 사건 이벤트를 구독하고, 활성 목표와 대조하여
objective_completed / objective_failed 이벤트를 발행한다.
"""

import logging
from typing import Any

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes

logger = logging.getLogger(__name__)

# resolve_check 등급 순서
TIER_ORDER: dict[str, int] = {
    "failure": 0,
    "partial": 1,
    "success": 2,
    "critical": 3,
}


class ObjectiveWatcher:
    """활성 퀘스트 목표 감시 + 달성/실패 이벤트 발행"""

    def __init__(
        self,
        event_bus: EventBus,
        quest_service: Any,
        companion_service: Any | None = None,
    ) -> None:
        """
        quest_service: QuestService 인스턴스.
            get_active_objectives_by_type() 메서드 사용.
        companion_service: CompanionService 인스턴스.
            is_companion() 메서드 사용 (escort 판정).

        ObjectiveWatcher는 engine 컴포넌트이므로 quest_service를
        직접 참조해도 아키텍처 위반이 아님 (engine → service 방향).
        """
        self._bus = event_bus
        self._quest_service = quest_service
        self._companion_service = companion_service
        self._cumulative_deliveries: dict[str, int] = {}
        self._register_watchers()

    def _register_watchers(self) -> None:
        """목표 유형별 감시 이벤트 구독"""
        bus = self._bus

        # reach_node
        bus.subscribe(EventTypes.PLAYER_MOVED, self._check_reach_objectives)
        bus.subscribe(EventTypes.ACTION_COMPLETED, self._check_action_reach_objectives)

        # talk_to_npc
        bus.subscribe(EventTypes.DIALOGUE_STARTED, self._check_talk_objectives_start)
        bus.subscribe(EventTypes.DIALOGUE_ENDED, self._check_talk_objectives_end)

        # resolve_check
        bus.subscribe(EventTypes.CHECK_RESULT, self._check_resolve_objectives)

        # deliver
        bus.subscribe(EventTypes.ITEM_GIVEN, self._check_deliver_objectives)

        # escort
        bus.subscribe(EventTypes.PLAYER_MOVED, self._check_escort_objectives)

        # escort 실패 감지
        bus.subscribe(EventTypes.NPC_DIED, self._check_escort_target_dead)

    # === reach_node ===

    def _check_reach_objectives(self, event: GameEvent) -> None:
        """player_moved 시 reach_node 달성 체크.

        event.data: {player_id, from_node, to_node, move_type}

        매칭: target.node_id == to_node && require_action 없음
        """
        to_node = event.data.get("to_node")

        for obj in self._quest_service.get_active_objectives_by_type("reach_node"):
            target = obj.target
            if target.get("node_id") != to_node:
                continue

            # require_action이 없으면 도착만으로 달성
            if not target.get("require_action"):
                self._emit_completed(
                    obj, trigger_action="move", trigger_data=event.data
                )

    def _check_action_reach_objectives(self, event: GameEvent) -> None:
        """action_completed 시 require_action 있는 reach_node 달성 체크.

        event.data: {player_id, action_type, node_id, result_data}

        매칭: target.node_id == node_id && target.require_action == action_type
        """
        action_type = event.data.get("action_type")
        node_id = event.data.get("node_id")

        for obj in self._quest_service.get_active_objectives_by_type("reach_node"):
            target = obj.target
            if target.get("node_id") != node_id:
                continue
            if target.get("require_action") != action_type:
                continue

            self._emit_completed(
                obj, trigger_action=action_type or "", trigger_data=event.data
            )

    # === talk_to_npc ===

    def _check_talk_objectives_start(self, event: GameEvent) -> None:
        """dialogue_started 시 단순 접촉 talk_to_npc 달성 체크.

        event.data: {npc_id, ...}

        매칭: target.npc_id == npc_id && require_topic 없음
        """
        npc_id = event.data.get("npc_id")

        for obj in self._quest_service.get_active_objectives_by_type("talk_to_npc"):
            target = obj.target
            if target.get("npc_id") != npc_id:
                continue
            if target.get("require_topic"):
                continue  # 주제 요구는 dialogue_ended에서 판정

            self._emit_completed(obj, trigger_action="talk", trigger_data=event.data)

    def _check_talk_objectives_end(self, event: GameEvent) -> None:
        """dialogue_ended 시 주제 요구 talk_to_npc 달성 체크.

        event.data: {npc_id, topic_tags, memory_tags, ...}

        매칭: target.npc_id == npc_id && target.require_topic in (topic_tags | memory_tags)
        """
        npc_id = event.data.get("npc_id")
        topic_tags = event.data.get("topic_tags", [])
        memory_tags = event.data.get("memory_tags", [])
        all_tags = set(topic_tags + memory_tags)

        for obj in self._quest_service.get_active_objectives_by_type("talk_to_npc"):
            target = obj.target
            if target.get("npc_id") != npc_id:
                continue
            if not target.get("require_topic"):
                continue  # 단순 접촉은 dialogue_started에서 이미 처리
            if target["require_topic"] not in all_tags:
                continue

            self._emit_completed(obj, trigger_action="talk", trigger_data=event.data)

    # === resolve_check ===

    def _check_resolve_objectives(self, event: GameEvent) -> None:
        """check_result 시 resolve_check 달성 체크.

        event.data: {result_tier, stat, context_tags}

        매칭:
        1. result_tier >= target.min_result_tier (TIER_ORDER 기준)
        2. target.check_type 있으면 stat 일치
        3. target.context_tag 있으면 context_tags에 포함
        """
        result_tier = event.data.get("result_tier", "")
        stat = event.data.get("stat")
        context_tags = event.data.get("context_tags", [])

        for obj in self._quest_service.get_active_objectives_by_type("resolve_check"):
            target = obj.target

            # 최소 성공 등급 체크
            min_tier = target.get("min_result_tier", "success")
            if TIER_ORDER.get(result_tier, 0) < TIER_ORDER.get(min_tier, 2):
                continue

            # 스탯 체크 (지정된 경우)
            if target.get("check_type") and target["check_type"] != stat:
                continue

            # 컨텍스트 태그 체크 (지정된 경우)
            if target.get("context_tag") and target["context_tag"] not in context_tags:
                continue

            self._emit_completed(obj, trigger_action="check", trigger_data=event.data)

    # === deliver ===

    def _check_deliver_objectives(self, event: GameEvent) -> None:
        """item_given 시 deliver 달성 체크.

        event.data: {
            player_id, recipient_npc_id,
            item_prototype_id, item_instance_id,
            quantity, item_tags
        }

        매칭:
        1. target.recipient_npc_id == recipient_npc_id
        2. 아이템 매칭:
           a. target.item_prototype_id 있으면 -> 프로토타입 ID 일치
           b. target.item_tag 있으면 -> item_tags에 포함
        3. 수량 체크: 누적 전달량 >= target.quantity
        """
        recipient = event.data.get("recipient_npc_id")
        given_proto = event.data.get("item_prototype_id")
        given_qty = event.data.get("quantity", 1)
        given_tags = event.data.get("item_tags", [])

        for obj in self._quest_service.get_active_objectives_by_type("deliver"):
            target = obj.target
            if target.get("recipient_npc_id") != recipient:
                continue

            # 프로토타입 ID 매칭 (특정 아이템)
            if "item_prototype_id" in target:
                if target["item_prototype_id"] != given_proto:
                    continue
            # 태그 매칭 (범용 — "약초 아무거나")
            elif "item_tag" in target:
                if target["item_tag"] not in given_tags:
                    continue

            # 수량 체크 (누적)
            required_qty = target.get("quantity", 1)
            cumulative = self._get_cumulative_delivery(obj.objective_id) + given_qty
            self._cumulative_deliveries[obj.objective_id] = cumulative
            if cumulative < required_qty:
                logger.debug(
                    "deliver %s: %d/%d",
                    obj.objective_id,
                    cumulative,
                    required_qty,
                )
                continue  # 아직 부족

            self._emit_completed(obj, trigger_action="give", trigger_data=event.data)
            # 완료 시 누적 초기화
            self._cumulative_deliveries.pop(obj.objective_id, None)

    def _get_cumulative_delivery(self, objective_id: str) -> int:
        """목표별 누적 전달 수량 조회."""
        return self._cumulative_deliveries.get(objective_id, 0)

    # === escort ===

    def _check_escort_objectives(self, event: GameEvent) -> None:
        """player_moved 시 escort 달성 체크.

        event.data: {player_id, from_node, to_node, move_type}

        매칭:
        1. target.destination_node_id == to_node
        2. companion_service.is_companion(player_id, target.target_npc_id) == True
        """
        to_node = event.data.get("to_node")
        player_id = event.data.get("player_id")

        if self._companion_service is None:
            return

        for obj in self._quest_service.get_active_objectives_by_type("escort"):
            target = obj.target
            if target.get("destination_node_id") != to_node:
                continue

            if not self._companion_service.is_companion(
                player_id, target.get("target_npc_id", "")
            ):
                continue

            self._emit_completed(obj, trigger_action="move", trigger_data=event.data)

    def _check_escort_target_dead(self, event: GameEvent) -> None:
        """npc_died 시 escort 대상 사망 체크.

        event.data: {npc_id, cause, ...}

        활성 escort 목표 중 target.target_npc_id == dead_npc_id -> objective_failed 발행.
        fail_reason: "target_dead"
        """
        dead_npc_id = event.data.get("npc_id")

        for obj in self._quest_service.get_active_objectives_by_type("escort"):
            if obj.target.get("target_npc_id") != dead_npc_id:
                continue

            self._emit_failed(
                obj,
                fail_reason="target_dead",
                trigger_data=event.data,
            )

    # === 공통 발행 ===

    def _emit_completed(
        self, objective: Any, trigger_action: str, trigger_data: dict
    ) -> None:
        """objective_completed 이벤트 발행."""
        logger.info(
            "Objective completed: %s (type=%s, trigger=%s)",
            objective.objective_id,
            objective.objective_type,
            trigger_action,
        )
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.OBJECTIVE_COMPLETED,
                data={
                    "quest_id": objective.quest_id,
                    "objective_id": objective.objective_id,
                    "objective_type": objective.objective_type,
                    "trigger_action": trigger_action,
                    "trigger_data": trigger_data,
                },
                source="objective_watcher",
            )
        )

    def _emit_failed(
        self, objective: Any, fail_reason: str, trigger_data: dict
    ) -> None:
        """objective_failed 이벤트 발행."""
        logger.info(
            "Objective failed: %s (type=%s, reason=%s)",
            objective.objective_id,
            objective.objective_type,
            fail_reason,
        )
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.OBJECTIVE_FAILED,
                data={
                    "quest_id": objective.quest_id,
                    "objective_id": objective.objective_id,
                    "objective_type": objective.objective_type,
                    "fail_reason": fail_reason,
                    "trigger_data": trigger_data,
                },
                source="objective_watcher",
            )
        )
