"""engine.py + ModuleManager 통합 테스트

기존 ITWEngine 동작이 깨지지 않았는지 확인하고,
ModuleManager 통합이 올바른지 검증한다.
"""

from src.core.engine import ITWEngine
from src.modules.module_manager import ModuleManager


# --- 헬퍼 ---


def create_test_engine() -> ITWEngine:
    """테스트용 엔진 생성 (engine.py CLI 패턴 참조)"""
    engine = ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )
    return engine


def create_engine_with_player() -> tuple[ITWEngine, str]:
    """테스트용 엔진 + 플레이어 생성"""
    engine = create_test_engine()
    player_id = "test_player"
    engine.register_player(player_id)
    engine.debug_generate_area(0, 0, radius=3)
    return engine, player_id


# --- ModuleManager 통합 테스트 ---


class TestEngineHasModuleManager:
    def test_module_manager_exists(self):
        engine = create_test_engine()
        assert hasattr(engine, "module_manager")
        assert isinstance(engine.module_manager, ModuleManager)

    def test_geography_registered(self):
        engine = create_test_engine()
        assert "geography" in engine.module_manager.modules

    def test_geography_default_disabled(self):
        engine = create_test_engine()
        assert engine.module_manager.is_enabled("geography") is False

    def test_enable_geography(self):
        engine = create_test_engine()
        assert engine.enable_module("geography") is True
        assert engine.module_manager.is_enabled("geography") is True

    def test_disable_geography(self):
        engine = create_test_engine()
        engine.enable_module("geography")
        assert engine.disable_module("geography") is True
        assert engine.module_manager.is_enabled("geography") is False

    def test_enable_nonexistent_module(self):
        engine = create_test_engine()
        assert engine.enable_module("nonexistent") is False


# --- 기존 동작 보존 테스트 ---


class TestExistingBehaviorPreserved:
    """모듈 추가 후에도 기존 동작이 100% 동일한지 확인"""

    def test_look_without_module(self):
        engine, pid = create_engine_with_player()
        result = engine.look(pid)
        assert result.success is True
        assert result.action_type == "look"
        assert result.location_view is not None

    def test_look_with_geography_enabled(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.look(pid)
        assert result.success is True
        assert result.location_view is not None

    def test_move_without_module(self):
        engine, pid = create_engine_with_player()
        result = engine.move(pid, "n")
        assert result.action_type == "move"

    def test_move_with_geography_enabled(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.move(pid, "n")
        assert result.action_type == "move"

    def test_investigate_still_works(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.investigate(pid)
        assert result.action_type == "investigate"

    def test_rest_still_works(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.rest(pid)
        assert result.success is True

    def test_register_player_still_works(self):
        engine = create_test_engine()
        engine.enable_module("geography")
        player = engine.register_player("new_player")
        assert player.player_id == "new_player"
        assert "0_0" in player.discovered_nodes

    def test_get_compass_still_works(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        compass = engine.get_compass(pid)
        assert isinstance(compass, str)

    def test_daily_tick_still_works(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        engine.daily_tick()  # 에러 없이 완료

    def test_world_stats_still_works(self):
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        stats = engine.get_world_stats()
        assert "engine_version" in stats
        assert "world" in stats


# --- 모듈 ON/OFF 토글 테스트 ---


class TestModuleToggle:
    """모듈 활성/비활성 전환이 안전한지 확인"""

    def test_toggle_during_play(self):
        engine, pid = create_engine_with_player()

        # OFF 상태에서 이동
        r1 = engine.move(pid, "n")

        # ON
        engine.enable_module("geography")
        r2 = engine.move(pid, "s")

        # OFF
        engine.disable_module("geography")
        r3 = engine.look(pid)

        # 모두 에러 없이 동작해야 함
        assert r1.action_type == "move"
        assert r2.action_type == "move"
        assert r3.action_type == "look"

    def test_multiple_toggle_cycles(self):
        engine, pid = create_engine_with_player()
        for _ in range(5):
            engine.enable_module("geography")
            engine.look(pid)
            engine.disable_module("geography")
            engine.look(pid)
        # 5번 토글 후에도 정상


# --- enter/exit depth 테스트 ---


class TestDepthWithModules:
    def test_enter_depth_with_module(self):
        """enter_depth가 모듈 활성 상태에서도 동작"""
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.enter_depth(pid)
        # 현재 위치(0,0)의 tier에 따라 성공/실패 갈림
        assert result.action_type == "enter"

    def test_exit_depth_with_module(self):
        """exit_depth가 모듈 활성 상태에서도 동작"""
        engine, pid = create_engine_with_player()
        engine.enable_module("geography")
        result = engine.exit_depth(pid)
        # 서브그리드 안에 있지 않으면 실패
        assert result.action_type == "exit"
