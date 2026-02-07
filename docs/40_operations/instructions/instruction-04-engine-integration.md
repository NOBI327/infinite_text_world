# 구현 지시서 #04: engine.py 연결 (ModuleManager 통합 + geography 연결)

**대상**: Claude Code  
**우선순위**: 4/4 (마지막)  
**선행 조건**: 지시서 #01, #02, #03 모두 완료  
**예상 결과**: engine.py가 ModuleManager를 사용, geography 모듈 ON/OFF 동작 검증

---

## 0. 사전 준비

```bash
# 반드시 먼저 읽을 코드
cat src/core/engine.py                         # 전체 (1250줄)
cat src/modules/base.py                        # GameModule, GameContext, Action
cat src/modules/module_manager.py              # ModuleManager
cat src/modules/geography/module.py            # GeographyModule
cat src/core/event_bus.py                      # EventBus
cat tests/                                     # 기존 테스트 구조 파악
```

---

## 1. 목표

engine.py에 ModuleManager를 통합하되, **기존 동작을 100% 보존**한다.

전략: **Strangler Fig Pattern (점진적 이관)**

- ModuleManager를 ITWEngine에 추가
- 이동 성공/노드 진입 시 모듈에 알림 (훅 포인트)
- geography 모듈 OFF면 기존 로직 그대로, ON이면 모듈도 함께 동작
- 기존 메서드 시그니처 변경 없음

---

## 2. engine.py 수정 상세

### 2.1 import 추가 (L10 부근, 기존 import 영역)

```python
# 기존 import 아래에 추가
from src.modules.base import GameContext
from src.modules.module_manager import ModuleManager
from src.modules.geography import GeographyModule
```

### 2.2 ITWEngine.__init__ 수정 (L295~L327)

기존 코드 **끝에** 모듈 시스템 초기화를 추가한다. 기존 코드를 수정하지 않는다.

```python
def __init__(
    self,
    axiom_data_path: str = "itw_214_divine_axioms.json",
    world_seed: Optional[int] = None,
):
    # ... 기존 초기화 코드 전부 유지 (L307~L327) ...

    # === 모듈 시스템 초기화 (기존 인스턴스 래핑) ===
    self._module_manager = ModuleManager()

    geography = GeographyModule(
        world_generator=self.world,               # 기존 self.world 재사용
        navigator=self.navigator,                  # 기존 self.navigator 재사용
        sub_grid_generator=self.sub_grid_generator,  # 기존 self.sub_grid_generator 재사용
    )
    self._module_manager.register(geography)

    logger.info("ModuleManager initialized. Registered modules: %s",
                list(self._module_manager.modules.keys()))
```

**삽입 위치**: L327 `logger.info("Ready. %d Axioms loaded.", ...)` 바로 위 또는 아래.

### 2.3 module_manager 프로퍼티 추가 (L329 부근, 플레이어 관리 섹션 전)

```python
@property
def module_manager(self) -> ModuleManager:
    """모듈 관리자 접근"""
    return self._module_manager
```

### 2.4 모듈 편의 메서드 추가 (get_compass 메서드 뒤, L724 부근)

```python
# === 모듈 시스템 ===

def enable_module(self, module_name: str) -> bool:
    """모듈 활성화"""
    return self._module_manager.enable(module_name)

def disable_module(self, module_name: str) -> bool:
    """모듈 비활성화"""
    return self._module_manager.disable(module_name)
```

### 2.5 모듈 알림 헬퍼 추가 (같은 영역)

```python
def _build_game_context(
    self, player_id: str, node_id: str, db_session: Optional[Session] = None
) -> GameContext:
    """모듈에 전달할 GameContext 생성 헬퍼"""
    return GameContext(
        player_id=player_id,
        current_node_id=node_id,
        current_turn=0,  # 현재 명시적 턴 카운터 없음. 향후 추가.
        db_session=db_session,  # None이면 모듈이 DB 접근 불가 (현재 OK)
    )

def _notify_modules_node_enter(
    self, player_id: str, x: int, y: int, db_session: Optional[Session] = None
) -> None:
    """이동 성공 시 모듈에 노드 진입 알림"""
    if not self._module_manager.get_enabled_modules():
        return  # 활성 모듈 없으면 스킵

    node_id = f"{x}_{y}"
    context = self._build_game_context(player_id, node_id, db_session)
    self._module_manager.process_node_enter(node_id, context)
```

### 2.6 _move_in_main_grid에 훅 추가 (L400~L469)

이동 성공 블록(L432~L465) 끝, `return ActionResult(...)` 직전에 모듈 알림 추가:

```python
# L464 부근, return 직전에 추가
# 모듈 알림
self._notify_modules_node_enter(player.player_id, player.x, player.y)
```

**정확한 삽입 위치**: L458 `if result.encounter:` 블록 이후, L459 `data["encounter"] = result.encounter` 이후, L460 빈줄, 그리고 L461 `return ActionResult(...)` **직전**.

즉:
```python
            if result.encounter:
                data["encounter"] = result.encounter

            # 모듈 알림 (이동 성공 시)
            self._notify_modules_node_enter(player.player_id, player.x, player.y)

            return ActionResult(
                success=True,
                action_type="move",
                ...
```

### 2.7 enter_depth에 훅 추가 (L727~L790)

서브그리드 진입 성공 후(L781 `return ActionResult(...)` 직전):

```python
            # 모듈 알림 (서브그리드 진입)
            self._notify_modules_node_enter(
                player.player_id, player.x, player.y
            )

            return ActionResult(
                success=True,
                action_type="enter",
                ...
```

### 2.8 exit_depth에 훅 추가 (L792~L833)

메인 그리드 복귀 성공 후(L828 `return ActionResult(...)` 직전):

```python
            # 모듈 알림 (메인 그리드 복귀)
            self._notify_modules_node_enter(
                player_id, player.x, player.y
            )

            return ActionResult(
                success=True,
                action_type="exit",
                ...
```

### 2.9 daily_tick에 모듈 턴 처리 추가 (L1046~L1062)

daily_tick 메서드 끝에 추가:

```python
    def daily_tick(self):
        """일일 월드 업데이트"""
        logger.info("Daily tick processing...")

        # ... 기존 노드 순회 로직 유지 ...

        # 모듈 턴 처리
        if self._module_manager.get_enabled_modules():
            # daily_tick은 특정 플레이어 없이 호출되므로 빈 컨텍스트
            context = self._build_game_context(
                player_id="__system__",
                node_id="__global__",
            )
            self._module_manager.process_turn(context)

        logger.info("Daily tick complete")
```

---

## 3. 수정하지 않는 것 (명시)

| 메서드 | 이유 |
|--------|------|
| `look()` | 모듈이 추가 정보를 넣는 건 향후 |
| `_move_in_sub_grid()` | 서브그리드 내 이동은 아직 모듈화 불필요 |
| `investigate()` | Echo 시스템은 geography 모듈 범위 밖 |
| `harvest()` | 자원은 item_core 모듈 범위 |
| `rest()` | 모듈 연관 없음 |
| `save/load_*_db()` | DB 로직은 현재 유지 |
| `register_player()` | 플레이어 관리는 Core |

---

## 4. 테스트 작성

### 4.1 `tests/test_modules/test_engine_integration.py`

```python
"""engine.py + ModuleManager 통합 테스트

기존 ITWEngine 동작이 깨지지 않았는지 확인하고,
ModuleManager 통합이 올바른지 검증한다.
"""
import pytest

from src.core.engine import ITWEngine, ActionResult, PlayerState
from src.modules.module_manager import ModuleManager


# --- 헬퍼 ---

def create_test_engine() -> ITWEngine:
    """테스트용 엔진 생성 (engine.py L1119 CLI 패턴 참조)"""
    engine = ITWEngine(
        axiom_data_path="itw_214_divine_axioms.json",
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
        assert hasattr(engine, 'module_manager')
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
        # 성공 여부는 맵 상태에 따라 다를 수 있음

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
```

---

## 5. 품질 게이트

```bash
ruff check src/core/engine.py src/modules/
pytest tests/ -v                              # 전체 테스트 (기존 168개 + 신규)
pytest tests/ -v -k "engine"                  # engine 관련 집중
pytest tests/test_modules/ -v                 # 모듈 테스트
pytest tests/ --cov --cov-report=term-missing # 커버리지 확인
mypy src/core/engine.py src/modules/
```

---

## 6. 체크리스트

- [ ] engine.py에 import 추가 (ModuleManager, GeographyModule, GameContext)
- [ ] `ITWEngine.__init__`에 ModuleManager + geography 등록 추가 (L327 부근)
- [ ] `module_manager` 프로퍼티 추가
- [ ] `enable_module()`, `disable_module()` 추가
- [ ] `_build_game_context()`, `_notify_modules_node_enter()` 헬퍼 추가
- [ ] `_move_in_main_grid()`에 모듈 알림 훅 추가 (L460 부근)
- [ ] `enter_depth()`에 모듈 알림 훅 추가 (L781 부근)
- [ ] `exit_depth()`에 모듈 알림 훅 추가 (L828 부근)
- [ ] `daily_tick()`에 모듈 턴 처리 추가 (L1062 부근)
- [ ] **기존 테스트 168개 전부 통과** (회귀 없음)
- [ ] `tests/test_modules/test_engine_integration.py` 작성 + 통과
- [ ] `ruff check` 통과
- [ ] `pytest` 전체 통과
- [ ] 커밋: `feat: integrate ModuleManager into ITWEngine with geography module`

---

## 7. 주의사항

- **기존 동작 보존이 최우선.** 모듈 비활성 상태에서 기존과 100% 동일해야 한다.
- engine.py의 기존 메서드 **시그니처를 변경하지 않는다**.
- `self.world`, `self.navigator`, `self.sub_grid_generator`는 **그대로 유지**. geography 모듈은 이들을 참조만 한다.
- `_build_game_context`에서 `db_session=None`이 기본값. 현재 액션 메서드들은 Session을 받지 않으므로 None으로 전달. 향후 API 레벨에서 Session 주입 시 변경.
- `current_turn=0`은 임시값. 현재 engine.py에 명시적 턴 카운터가 없음. time_core 모듈 구현 시 교체.
- `_notify_modules_node_enter`는 활성 모듈이 없으면 early return하므로 성능 영향 최소.

---

## 8. 검증 시나리오

지시서 완료 후 수동 확인:

```python
# 기존 테스트 전부 통과 확인
pytest tests/ -v

# 신규 통합 테스트 확인
pytest tests/test_modules/test_engine_integration.py -v

# 모듈 OFF 상태에서 기존 동작
engine = ITWEngine(axiom_data_path="itw_214_divine_axioms.json", world_seed=42)
engine.register_player("p1")
engine.debug_generate_area(0, 0, radius=3)
r = engine.look("p1")       # 정상
r = engine.move("p1", "n")  # 정상

# 모듈 ON
engine.enable_module("geography")
r = engine.look("p1")       # 정상 (변함없음)
r = engine.move("p1", "s")  # 정상 + 모듈 알림 발생

# 모듈 OFF
engine.disable_module("geography")
r = engine.look("p1")       # 정상 (원복)
```
