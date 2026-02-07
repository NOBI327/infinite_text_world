# 구현 지시서 #02: EventBus 인프라

**대상**: Claude Code  
**우선순위**: 2/4  
**선행 조건**: 지시서 #01 완료 (ModuleManager 존재)  
**예상 결과**: EventBus 인프라 완성, 아직 실제 구독자 없음

---

## 0. 사전 준비

```bash
# 반드시 먼저 읽을 문서
cat docs/30_technical/architecture.md          # "서비스 간 통신 원칙" 섹션
cat docs/30_technical/module-architecture.md   # 섹션 4.3 "모듈 간 이벤트 통신"
cat src/modules/base.py                        # GameModule 인터페이스 확인
cat src/modules/module_manager.py              # ModuleManager 구조 확인
```

---

## 1. 목표

EventBus를 구현한다. 핵심 규칙:
- 서비스/모듈 간 직접 호출 금지, EventBus 경유
- 이벤트는 식별자(ID)만 전달
- 무한 루프 방지: 전파 깊이 제한 (최대 5단계)
- 동일 원인에서 동일 이벤트 중복 발행 금지

이 단계에서는 **인프라만 구현**하고, 실제 이벤트 정의나 구독자는 만들지 않는다.

---

## 2. 파일 생성

### 2.1 `src/core/event_bus.py`

```python
"""EventBus - 모듈/서비스 간 이벤트 통신 인프라

docs/30_technical/architecture.md "서비스 간 통신 원칙" 참조.

규칙:
- 서비스/모듈은 다른 서비스/모듈을 직접 import하지 않는다
- 이벤트는 식별자(ID)만 전달한다
- 전파 깊이 최대 MAX_DEPTH 단계
- 동일 원인에서 동일 이벤트 중복 발행 금지
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional
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
        self._emitted_in_chain: set[str] = set()  # "source:event_type" 중복 방지

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """이벤트 구독 등록"""
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus 구독: {event_type} → {handler.__qualname__}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """이벤트 구독 해제"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"EventBus 구독 해제: {event_type} → {handler.__qualname__}")
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
            logger.warning(
                f"EventBus 중복 이벤트 차단: {chain_key}"
            )
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
```

### 2.2 `src/core/__init__.py` 수정

기존 `__init__.py`에 EventBus를 추가 export한다.

```python
# 기존 export에 추가:
from src.core.event_bus import EventBus, GameEvent
```

**주의**: 기존 export를 제거하지 말 것. 추가만 한다.

---

## 3. ModuleManager와 EventBus 연결

### 3.1 `src/modules/module_manager.py` 수정

ModuleManager가 EventBus를 소유하고, 턴 종료 시 `reset_chain()`을 호출한다.

```python
# ModuleManager.__init__에 추가:
from src.core.event_bus import EventBus

class ModuleManager:
    def __init__(self) -> None:
        self._modules: Dict[str, GameModule] = {}
        self._event_bus: EventBus = EventBus()

    @property
    def event_bus(self) -> EventBus:
        """모듈이 이벤트 구독/발행에 사용할 EventBus"""
        return self._event_bus

    # process_turn 수정:
    def process_turn(self, context: GameContext) -> None:
        """활성 모듈의 on_turn 순차 호출 + 턴 종료 시 이벤트 체인 초기화"""
        for module in self._modules.values():
            if module.enabled:
                module.on_turn(context)
        self._event_bus.reset_chain()
```

**주의**: 기존 메서드를 유지하면서 `__init__`에 `_event_bus` 추가, `process_turn` 끝에 `reset_chain()` 추가만 한다.

---

## 4. 테스트 작성

### 4.1 `tests/test_event_bus.py`

```python
"""EventBus 테스트"""
import pytest

from src.core.event_bus import EventBus, GameEvent, MAX_DEPTH


class TestSubscribeEmit:
    def test_basic_emit(self):
        bus = EventBus()
        received = []
        bus.subscribe("test_event", lambda e: received.append(e))
        bus.emit(GameEvent(event_type="test_event", data={"id": "1"}, source="test"))
        assert len(received) == 1
        assert received[0].data["id"] == "1"

    def test_multiple_handlers(self):
        bus = EventBus()
        results = []
        bus.subscribe("evt", lambda e: results.append("a"))
        bus.subscribe("evt", lambda e: results.append("b"))
        bus.emit(GameEvent(event_type="evt", data={}, source="test"))
        assert results == ["a", "b"]

    def test_no_handlers(self):
        """구독자 없는 이벤트 발행 — 에러 없이 무시"""
        bus = EventBus()
        bus.emit(GameEvent(event_type="no_one_listens", data={}, source="test"))

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("evt", handler)
        bus.unsubscribe("evt", handler)
        bus.emit(GameEvent(event_type="evt", data={}, source="test"))
        assert len(received) == 0

    def test_unsubscribe_nonexistent(self):
        """미등록 핸들러 해제 — 경고만, 에러 없음"""
        bus = EventBus()
        bus.unsubscribe("evt", lambda e: None)


class TestDepthLimit:
    def test_max_depth_prevents_infinite_loop(self):
        bus = EventBus()
        call_count = 0

        def recursive_handler(event: GameEvent):
            nonlocal call_count
            call_count += 1
            # 다른 source로 발행해서 중복 체크를 우회
            bus.emit(GameEvent(
                event_type="chain",
                data={},
                source=f"handler_{call_count}"
            ))

        bus.subscribe("chain", recursive_handler)
        bus.emit(GameEvent(event_type="chain", data={}, source="origin"))

        # MAX_DEPTH(5)까지만 전파
        assert call_count == MAX_DEPTH


class TestDuplicatePrevention:
    def test_same_source_same_event_blocked(self):
        bus = EventBus()
        count = 0

        def handler(event: GameEvent):
            nonlocal count
            count += 1
            # 같은 source에서 같은 이벤트 재발행 시도
            bus.emit(GameEvent(event_type="evt", data={}, source="same_source"))

        bus.subscribe("evt", handler)
        bus.emit(GameEvent(event_type="evt", data={}, source="same_source"))
        assert count == 1  # 두 번째는 중복으로 차단

    def test_different_source_allowed(self):
        bus = EventBus()
        received = []

        bus.subscribe("evt", lambda e: received.append(e.source))
        bus.emit(GameEvent(event_type="evt", data={}, source="source_a"))
        bus.emit(GameEvent(event_type="evt", data={}, source="source_b"))
        assert len(received) == 2


class TestResetChain:
    def test_reset_allows_re_emit(self):
        bus = EventBus()
        count = 0
        bus.subscribe("evt", lambda e: None.__class__.__init__(None) or None)  # no-op

        # 간단히: emit 후 reset 후 다시 emit
        received = []
        bus.subscribe("re", lambda e: received.append(1))
        bus.emit(GameEvent(event_type="re", data={}, source="s"))
        bus.reset_chain()
        bus.emit(GameEvent(event_type="re", data={}, source="s"))
        assert len(received) == 2


class TestHandlerError:
    def test_handler_exception_doesnt_stop_others(self):
        bus = EventBus()
        results = []

        def bad_handler(e):
            raise ValueError("boom")

        def good_handler(e):
            results.append("ok")

        bus.subscribe("evt", bad_handler)
        bus.subscribe("evt", good_handler)
        bus.emit(GameEvent(event_type="evt", data={}, source="test"))
        assert results == ["ok"]


class TestClear:
    def test_clear_removes_all(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.handler_count == 2
        bus.clear()
        assert bus.handler_count == 0
```

### 4.2 `tests/test_modules/test_module_manager.py` 추가 테스트

기존 테스트 파일에 EventBus 관련 테스트 추가:

```python
class TestModuleManagerEventBus:
    def test_has_event_bus(self):
        mm = ModuleManager()
        assert mm.event_bus is not None

    def test_process_turn_resets_chain(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")
        
        # 이벤트 발행으로 chain에 기록 남기기
        mm.event_bus.emit(GameEvent(
            event_type="test", data={}, source="test"
        ))
        assert len(mm.event_bus._emitted_in_chain) == 1
        
        ctx = make_context()
        mm.process_turn(ctx)
        
        # process_turn 후 chain 초기화됨
        assert len(mm.event_bus._emitted_in_chain) == 0
```

**주의**: 이 클래스를 기존 `test_module_manager.py` 파일 끝에 추가한다. import에 `GameEvent`도 추가할 것:

```python
from src.core.event_bus import GameEvent
```

---

## 5. 품질 게이트

```bash
ruff check src/core/event_bus.py tests/test_event_bus.py
ruff check src/modules/ tests/test_modules/
pytest tests/test_event_bus.py -v
pytest tests/test_modules/ -v
pytest tests/ -v                    # 전체 테스트 회귀 확인
mypy src/core/event_bus.py src/modules/module_manager.py
```

---

## 6. 체크리스트

- [ ] `src/core/event_bus.py` — EventBus, GameEvent 구현
- [ ] `src/core/__init__.py` — EventBus, GameEvent export 추가
- [ ] `src/modules/module_manager.py` — EventBus 소유, process_turn에서 reset_chain
- [ ] `tests/test_event_bus.py` — 테스트 통과
- [ ] `tests/test_modules/test_module_manager.py` — EventBus 관련 테스트 추가 + 통과
- [ ] `ruff check` 통과
- [ ] `pytest` 전체 통과
- [ ] 커밋: `feat: add EventBus infrastructure with depth limit and duplicate prevention`

---

## 7. 주의사항

- EventBus는 **동기식**이다 (async 아님). ITW는 턴제이므로 동기로 충분.
- `set[str]` 구문은 Python 3.9+에서 지원. 프로젝트 최소 Python 버전 확인 필요. 안 되면 `Set[str]`로 변경.
- 핸들러 내 예외는 로깅 후 다음 핸들러로 진행 (한 핸들러 실패가 전체를 중단하지 않음).
- 이 지시서에서 실제 이벤트 타입(npc_promoted 등)을 **정의하지 않는다**. 추후 각 모듈 구현 시 정의.
