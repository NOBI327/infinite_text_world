# 구현 지시서 #01: ModuleManager + GameModule + GameContext

**대상**: Claude Code  
**우선순위**: 1/4 (가장 먼저)  
**예상 결과**: 모듈 시스템 인프라 완성, 테스트 통과

---

## 0. 사전 준비

```bash
# 반드시 먼저 읽을 문서
cat docs/30_technical/module-architecture.md   # 섹션 4 "모듈 인터페이스" 집중
cat docs/30_technical/architecture.md          # 의존 방향 규칙
cat src/core/engine.py                         # 현재 엔진 구조 파악
```

---

## 1. 목표

모듈 시스템의 기반 인프라 3개를 구현한다:
- `GameModule` (ABC): 모든 모듈이 구현할 인터페이스
- `GameContext`: 모듈에 전달되는 게임 상태 컨텍스트
- `ModuleManager`: 모듈 등록/활성화/비활성화/의존성 검증/턴 처리

이 단계에서는 **실제 모듈을 만들지 않는다**. 인프라만 구축하고 테스트한다.

---

## 2. 파일 생성

### 2.1 `src/modules/__init__.py`

```python
"""ITW 모듈 시스템"""
from src.modules.base import GameModule, GameContext
from src.modules.module_manager import ModuleManager

__all__ = ["GameModule", "GameContext", "ModuleManager"]
```

### 2.2 `src/modules/base.py`

```python
"""모듈 기반 인터페이스"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session


@dataclass
class GameContext:
    """모듈에 전달되는 게임 상태 컨텍스트"""
    player_id: str
    current_node_id: str
    current_turn: int
    db_session: Session

    # 모듈이 추가 데이터를 넣을 수 있는 확장 슬롯
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """모듈이 제공하는 행동"""
    name: str                    # 액션 식별자 (예: "talk", "trade")
    display_name: str            # 표시 이름 (예: "대화하기")
    module_name: str             # 제공한 모듈 이름
    description: str = ""        # 설명
    params: Dict[str, Any] = field(default_factory=dict)  # 추가 파라미터


class GameModule(ABC):
    """모든 ITW 모듈의 기반 인터페이스
    
    docs/30_technical/module-architecture.md 섹션 4.1 참조.
    
    규칙:
    - 모듈은 다른 모듈을 직접 import하지 않는다
    - 모듈 간 통신은 EventBus를 경유한다 (지시서 #02)
    - Module → Core, Module → DB는 허용
    - Module → Module은 금지
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """모듈 고유 이름 (예: 'geography', 'npc_core')"""
        ...

    @property
    def dependencies(self) -> List[str]:
        """이 모듈이 의존하는 다른 모듈 이름 목록
        
        기본값은 빈 리스트 (의존성 없음).
        """
        return []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def __init__(self) -> None:
        self._enabled: bool = False

    @abstractmethod
    def on_enable(self) -> None:
        """모듈 활성화 시 초기화 작업"""
        ...

    @abstractmethod
    def on_disable(self) -> None:
        """모듈 비활성화 시 정리 작업"""
        ...

    @abstractmethod
    def on_turn(self, context: GameContext) -> None:
        """매 턴 호출. 모듈별 턴 처리 로직."""
        ...

    @abstractmethod
    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """플레이어가 노드에 진입할 때 호출."""
        ...

    @abstractmethod
    def get_available_actions(self, context: GameContext) -> List[Action]:
        """현재 상황에서 이 모듈이 제공하는 행동 목록 반환."""
        ...
```

### 2.3 `src/modules/module_manager.py`

```python
"""모듈 관리자 - 등록, 활성화/비활성화, 의존성 검증, 턴/이벤트 전파"""
from typing import Dict, List, Optional

from src.core.logging import get_logger
from src.modules.base import GameModule, GameContext, Action

logger = get_logger(__name__)


class ModuleManager:
    """모듈 토글 및 생명주기 관리
    
    docs/30_technical/module-architecture.md 섹션 4.2 참조.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, GameModule] = {}

    @property
    def modules(self) -> Dict[str, GameModule]:
        """등록된 모든 모듈 (읽기 전용 접근)"""
        return dict(self._modules)

    def get_enabled_modules(self) -> List[GameModule]:
        """활성화된 모듈만 반환 (레이어 순서 보장은 추후)"""
        return [m for m in self._modules.values() if m.enabled]

    def register(self, module: GameModule) -> None:
        """모듈 등록. 같은 이름 중복 등록 시 경고 후 덮어쓰기."""
        if module.name in self._modules:
            logger.warning(f"모듈 덮어쓰기: {module.name}")
        self._modules[module.name] = module
        logger.info(f"모듈 등록: {module.name}")

    def enable(self, name: str) -> bool:
        """모듈 활성화. 의존성 미충족 시 False 반환.
        
        1. 모듈 존재 확인
        2. 의존성 모듈이 모두 등록 + 활성화 상태인지 확인
        3. on_enable() 호출
        4. enabled = True
        """
        module = self._modules.get(name)
        if not module:
            logger.error(f"모듈 미등록: {name}")
            return False

        if module.enabled:
            logger.debug(f"이미 활성화됨: {name}")
            return True

        # 의존성 체크
        for dep in module.dependencies:
            dep_module = self._modules.get(dep)
            if not dep_module:
                logger.warning(f"의존성 미등록: {name} requires {dep}")
                return False
            if not dep_module.enabled:
                logger.warning(f"의존성 비활성: {name} requires {dep} (not enabled)")
                return False

        module.on_enable()
        module.enabled = True
        logger.info(f"모듈 활성화: {name}")
        return True

    def disable(self, name: str) -> bool:
        """모듈 비활성화. 이 모듈에 의존하는 모듈을 먼저 비활성화 (cascade).
        
        Returns:
            True if 비활성화 성공, False if 모듈 미등록 또는 이미 비활성
        """
        module = self._modules.get(name)
        if not module:
            logger.error(f"모듈 미등록: {name}")
            return False

        if not module.enabled:
            logger.debug(f"이미 비활성: {name}")
            return True

        # cascade: 이 모듈에 의존하는 모듈 먼저 비활성화
        for other in self._modules.values():
            if name in other.dependencies and other.enabled:
                logger.info(f"cascade 비활성화: {other.name} (depends on {name})")
                self.disable(other.name)

        module.on_disable()
        module.enabled = False
        logger.info(f"모듈 비활성화: {name}")
        return True

    def process_turn(self, context: GameContext) -> None:
        """활성 모듈의 on_turn 순차 호출"""
        for module in self._modules.values():
            if module.enabled:
                module.on_turn(context)

    def process_node_enter(self, node_id: str, context: GameContext) -> None:
        """활성 모듈의 on_node_enter 순차 호출"""
        for module in self._modules.values():
            if module.enabled:
                module.on_node_enter(node_id, context)

    def get_all_actions(self, context: GameContext) -> List[Action]:
        """모든 활성 모듈에서 가능한 행동 수집"""
        actions: List[Action] = []
        for module in self._modules.values():
            if module.enabled:
                actions.extend(module.get_available_actions(context))
        return actions

    def is_enabled(self, name: str) -> bool:
        """특정 모듈이 활성화 상태인지 확인"""
        module = self._modules.get(name)
        return module.enabled if module else False
```

---

## 3. 테스트 작성

### 3.1 `tests/test_modules/__init__.py`

빈 파일.

### 3.2 `tests/test_modules/test_base.py`

```python
"""GameModule, GameContext, Action 테스트"""
import pytest
from unittest.mock import MagicMock

from src.modules.base import GameModule, GameContext, Action


class DummyModule(GameModule):
    """테스트용 더미 모듈"""

    @property
    def name(self) -> str:
        return "dummy"

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        pass

    def get_available_actions(self, context: GameContext) -> list:
        return []


class DependentModule(GameModule):
    """의존성 있는 테스트용 모듈"""

    @property
    def name(self) -> str:
        return "dependent"

    @property
    def dependencies(self) -> list:
        return ["dummy"]

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        pass

    def get_available_actions(self, context: GameContext) -> list:
        return [Action(name="dep_action", display_name="Dep", module_name="dependent")]


def make_context(**kwargs):
    defaults = {
        "player_id": "test_player",
        "current_node_id": "node_0_0",
        "current_turn": 1,
        "db_session": MagicMock(),
    }
    defaults.update(kwargs)
    return GameContext(**defaults)


class TestGameContext:
    def test_create_context(self):
        ctx = make_context()
        assert ctx.player_id == "test_player"
        assert ctx.current_node_id == "node_0_0"
        assert ctx.current_turn == 1
        assert ctx.extra == {}

    def test_extra_slot(self):
        ctx = make_context()
        ctx.extra["weather"] = "rain"
        assert ctx.extra["weather"] == "rain"


class TestGameModule:
    def test_dummy_module_defaults(self):
        m = DummyModule()
        assert m.name == "dummy"
        assert m.enabled is False
        assert m.dependencies == []

    def test_dependent_module_dependencies(self):
        m = DependentModule()
        assert m.dependencies == ["dummy"]

    def test_enable_disable_flag(self):
        m = DummyModule()
        m.enabled = True
        assert m.enabled is True
        m.enabled = False
        assert m.enabled is False


class TestAction:
    def test_create_action(self):
        a = Action(name="talk", display_name="대화하기", module_name="npc_core")
        assert a.name == "talk"
        assert a.module_name == "npc_core"
        assert a.params == {}
```

### 3.3 `tests/test_modules/test_module_manager.py`

```python
"""ModuleManager 테스트"""
import pytest
from unittest.mock import MagicMock, patch

from src.modules.base import GameModule, GameContext, Action
from src.modules.module_manager import ModuleManager


# --- 테스트용 모듈 ---

class AlphaModule(GameModule):
    def __init__(self):
        super().__init__()
        self.enable_called = False
        self.disable_called = False
        self.turns_processed = 0
        self.nodes_entered = []

    @property
    def name(self):
        return "alpha"

    def on_enable(self):
        self.enable_called = True

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        self.turns_processed += 1

    def on_node_enter(self, node_id, context):
        self.nodes_entered.append(node_id)

    def get_available_actions(self, context):
        return [Action(name="alpha_act", display_name="Alpha", module_name="alpha")]


class BetaModule(GameModule):
    """alpha에 의존하는 모듈"""
    def __init__(self):
        super().__init__()
        self.enable_called = False
        self.disable_called = False

    @property
    def name(self):
        return "beta"

    @property
    def dependencies(self):
        return ["alpha"]

    def on_enable(self):
        self.enable_called = True

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        pass

    def on_node_enter(self, node_id, context):
        pass

    def get_available_actions(self, context):
        return [Action(name="beta_act", display_name="Beta", module_name="beta")]


class GammaModule(GameModule):
    """beta에 의존 (alpha → beta → gamma 체인)"""
    def __init__(self):
        super().__init__()
        self.disable_called = False

    @property
    def name(self):
        return "gamma"

    @property
    def dependencies(self):
        return ["beta"]

    def on_enable(self):
        pass

    def on_disable(self):
        self.disable_called = True

    def on_turn(self, context):
        pass

    def on_node_enter(self, node_id, context):
        pass

    def get_available_actions(self, context):
        return []


def make_context():
    return GameContext(
        player_id="p1",
        current_node_id="n1",
        current_turn=1,
        db_session=MagicMock(),
    )


class TestRegister:
    def test_register_module(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert "alpha" in mm.modules

    def test_register_overwrites(self):
        mm = ModuleManager()
        m1 = AlphaModule()
        m2 = AlphaModule()
        mm.register(m1)
        mm.register(m2)
        assert mm.modules["alpha"] is m2


class TestEnable:
    def test_enable_success(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.enable("alpha") is True
        assert mm.is_enabled("alpha") is True

    def test_enable_calls_on_enable(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        assert m.enable_called is True

    def test_enable_nonexistent(self):
        mm = ModuleManager()
        assert mm.enable("nonexistent") is False

    def test_enable_already_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")
        assert mm.enable("alpha") is True  # 중복 활성화 OK

    def test_enable_with_dependency_met(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        mm.enable("alpha")
        assert mm.enable("beta") is True

    def test_enable_with_dependency_not_met(self):
        mm = ModuleManager()
        mm.register(BetaModule())  # alpha 미등록
        assert mm.enable("beta") is False

    def test_enable_with_dependency_not_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())  # 등록만, 활성화 안 함
        mm.register(BetaModule())
        assert mm.enable("beta") is False


class TestDisable:
    def test_disable_success(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        assert mm.disable("alpha") is True
        assert mm.is_enabled("alpha") is False
        assert m.disable_called is True

    def test_disable_nonexistent(self):
        mm = ModuleManager()
        assert mm.disable("nonexistent") is False

    def test_disable_already_disabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.disable("alpha") is True

    def test_cascade_disable(self):
        """alpha 비활성화 시 beta도 비활성화"""
        mm = ModuleManager()
        mm.register(AlphaModule())
        b = BetaModule()
        mm.register(b)
        mm.enable("alpha")
        mm.enable("beta")
        mm.disable("alpha")
        assert mm.is_enabled("alpha") is False
        assert mm.is_enabled("beta") is False
        assert b.disable_called is True

    def test_deep_cascade_disable(self):
        """alpha → beta → gamma 체인 cascade"""
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        g = GammaModule()
        mm.register(g)
        mm.enable("alpha")
        mm.enable("beta")
        mm.enable("gamma")
        mm.disable("alpha")
        assert mm.is_enabled("gamma") is False
        assert g.disable_called is True


class TestProcessTurn:
    def test_only_enabled_modules_process(self):
        mm = ModuleManager()
        m1 = AlphaModule()
        m2 = AlphaModule.__new__(AlphaModule)
        # m2는 별도 이름 필요 — 대신 beta 사용
        b = BetaModule()
        mm.register(m1)
        mm.register(b)
        mm.enable("alpha")
        # beta는 비활성 (의존성 때문이 아니라 enable 안 해서)

        ctx = make_context()
        mm.process_turn(ctx)
        assert m1.turns_processed == 1


class TestProcessNodeEnter:
    def test_node_enter_called(self):
        mm = ModuleManager()
        m = AlphaModule()
        mm.register(m)
        mm.enable("alpha")
        ctx = make_context()
        mm.process_node_enter("node_5_3", ctx)
        assert "node_5_3" in m.nodes_entered


class TestGetAllActions:
    def test_collect_actions_from_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.register(BetaModule())
        mm.enable("alpha")
        mm.enable("beta")
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        names = [a.name for a in actions]
        assert "alpha_act" in names
        assert "beta_act" in names

    def test_disabled_module_no_actions(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        assert len(actions) == 0  # alpha 미활성화


class TestIsEnabled:
    def test_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        mm.enable("alpha")
        assert mm.is_enabled("alpha") is True

    def test_not_enabled(self):
        mm = ModuleManager()
        mm.register(AlphaModule())
        assert mm.is_enabled("alpha") is False

    def test_not_registered(self):
        mm = ModuleManager()
        assert mm.is_enabled("unknown") is False
```

---

## 4. 품질 게이트

```bash
ruff check src/modules/ tests/test_modules/
pytest tests/test_modules/ -v
pytest tests/ -v                    # 기존 테스트 깨지지 않는지 확인
mypy src/modules/
```

---

## 5. 체크리스트

- [ ] `src/modules/__init__.py` 생성
- [ ] `src/modules/base.py` — GameModule ABC, GameContext, Action
- [ ] `src/modules/module_manager.py` — ModuleManager
- [ ] `tests/test_modules/__init__.py` 생성
- [ ] `tests/test_modules/test_base.py` — 테스트 통과
- [ ] `tests/test_modules/test_module_manager.py` — 테스트 통과
- [ ] `ruff check` 통과
- [ ] `pytest` 전체 통과
- [ ] 커밋: `feat: add ModuleManager, GameModule ABC, GameContext`

---

## 6. 주의사항

- `src/core/engine.py`는 이 지시서에서 **수정하지 않는다** (지시서 #04에서 연결)
- `print()` 사용 금지, `logging` 모듈 사용
- 의존 방향: `modules/` → `core/` OK, `modules/` → `db/` OK, 역방향 금지
- GameContext의 `db_session`은 SQLAlchemy Session 타입이지만, 테스트에서는 MagicMock 사용
