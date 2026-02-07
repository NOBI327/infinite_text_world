"""EventBus 테스트"""

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
        handler = lambda e: received.append(e)  # noqa: E731
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
            bus.emit(
                GameEvent(event_type="chain", data={}, source=f"handler_{call_count}")
            )

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
