"""EventBus - 모듈/서비스 간 이벤트 통신 인프라

docs/30_technical/architecture.md "서비스 간 통신 원칙" 참조.

규칙:
- 서비스/모듈은 다른 서비스/모듈을 직접 import하지 않는다
- 이벤트는 식별자(ID)만 전달한다
- 전파 깊이 최대 MAX_DEPTH 단계
- 동일 원인에서 동일 이벤트 중복 발행 금지
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Set
from collections import defaultdict

from src.core.logging import get_logger

logger = get_logger(__name__)

MAX_DEPTH = 5  # 한 턴 내 이벤트 전파 최대 깊이


@dataclass
class GameEvent:
    """이벤트 데이터 컨테이너

    Args:
        event_type: 이벤트 유형 (예: "npc_promoted", "quest_created")
        data: 이벤트 데이터 (ID 위주, 무거운 객체 금지)
        source: 발행한 모듈/서비스 이름
    """

    event_type: str
    data: Dict[str, Any]
    source: str

    # 내부 추적용 (외부에서 설정하지 않음)
    _depth: int = field(default=0, repr=False)


# 핸들러 타입: GameEvent를 받는 callable
EventHandler = Callable[[GameEvent], None]


class EventBus:
    """동기식 이벤트 버스

    사용 패턴:
        bus = EventBus()
        bus.subscribe("npc_promoted", memory_module.handle_npc_promoted)
        bus.emit(GameEvent(event_type="npc_promoted", data={"npc_id": "abc"}, source="npc_core"))
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._current_depth: int = 0
        self._emitted_in_chain: Set[str] = set()  # "source:event_type" 중복 방지

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """이벤트 구독 등록"""
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus 구독: {event_type} → {handler.__qualname__}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """이벤트 구독 해제"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(
                    f"EventBus 구독 해제: {event_type} → {handler.__qualname__}"
                )
            except ValueError:
                logger.warning(f"핸들러 미등록: {event_type} → {handler.__qualname__}")

    def emit(self, event: GameEvent) -> None:
        """이벤트 발행. 등록된 핸들러를 동기 호출.

        안전장치:
        1. 전파 깊이 MAX_DEPTH 초과 시 무시
        2. 동일 source에서 동일 event_type 중복 발행 시 무시
        """
        # 깊이 체크
        if self._current_depth >= MAX_DEPTH:
            logger.warning(
                f"EventBus 전파 깊이 초과 ({MAX_DEPTH}): "
                f"{event.source}:{event.event_type} 무시됨"
            )
            return

        # 중복 체크
        chain_key = f"{event.source}:{event.event_type}"
        if chain_key in self._emitted_in_chain:
            logger.warning(f"EventBus 중복 이벤트 차단: {chain_key}")
            return

        self._emitted_in_chain.add(chain_key)
        event._depth = self._current_depth

        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logger.debug(f"EventBus: {event.event_type} 구독자 없음")
            return

        logger.info(
            f"EventBus 전파: {event.event_type} (source={event.source}, "
            f"depth={self._current_depth}, handlers={len(handlers)})"
        )

        self._current_depth += 1
        try:
            for handler in handlers:
                try:
                    handler(event)
                except Exception:
                    logger.exception(
                        f"EventBus 핸들러 에러: {handler.__qualname__} "
                        f"(event={event.event_type})"
                    )
        finally:
            self._current_depth -= 1

    def reset_chain(self) -> None:
        """턴 종료 시 호출. 중복 추적 초기화."""
        self._emitted_in_chain.clear()
        self._current_depth = 0

    def clear(self) -> None:
        """모든 구독 해제 (테스트용)"""
        self._handlers.clear()
        self.reset_chain()

    @property
    def handler_count(self) -> int:
        """등록된 총 핸들러 수"""
        return sum(len(h) for h in self._handlers.values())
