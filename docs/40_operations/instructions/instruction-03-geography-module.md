# 구현 지시서 #03: geography 모듈 (기존 코드 래핑)

**대상**: Claude Code  
**우선순위**: 3/4  
**선행 조건**: 지시서 #01, #02 완료  
**예상 결과**: 첫 번째 실제 모듈 완성, 모듈 ON/OFF로 지리 기능 토글 가능

---

## 0. 사전 준비

```bash
# 반드시 먼저 읽을 문서 및 코드
cat docs/30_technical/module-architecture.md   # 섹션 3.2 "[A] geography"
cat src/core/engine.py                         # 엔진 구조 (아래 분석 참조)
cat src/core/world_generator.py                # WorldGenerator 클래스 시그니처
cat src/core/navigator.py                      # Navigator 클래스 시그니처
cat src/core/sub_grid.py                       # SubGridGenerator 클래스 시그니처
cat src/modules/base.py                        # GameModule 인터페이스
```

---

## 1. 목표

기존 core/ 코드를 **수정하지 않고** 래핑하는 geography 모듈을 만든다.

### 1.1 engine.py 현재 구조 (분석 완료)

engine.py의 지리 관련 인스턴스:
```python
# ITWEngine.__init__ (L295~L327)
self.world = WorldGenerator(self.axiom_loader, seed=world_seed)
self.sub_grid_generator = SubGridGenerator(self.axiom_loader, seed=world_seed or 0)
self.navigator = Navigator(self.world, self.axiom_loader, self.sub_grid_generator)
```

engine.py의 지리 관련 메서드:
```
look()               → self.navigator.get_location_view()
_move_in_main_grid() → self.navigator.travel()
_move_in_sub_grid()  → self.navigator.travel_sub_grid()
enter_depth()        → self.sub_grid_generator.generate_entrance()
exit_depth()         → self.navigator.get_location_view()
register_player()    → self.world.get_node(), self.world.get_or_generate()
daily_tick()         → self.world.nodes 순회
save/load_world_*()  → self.world.nodes 접근
```

### 1.2 래핑 전략

geography 모듈은 WorldGenerator, Navigator, SubGridGenerator를 **소유하지 않고 참조**한다.  
engine.py가 이미 생성한 인스턴스를 주입받아 래핑한다.

---

## 2. 파일 생성

### 2.1 `src/modules/geography/__init__.py`

```python
"""geography 모듈 - 맵, 노드, 서브그리드 관리"""
from src.modules.geography.module import GeographyModule

__all__ = ["GeographyModule"]
```

### 2.2 `src/modules/geography/module.py`

```python
"""GeographyModule - 지리 시스템 모듈

기존 core/world_generator.py, core/navigator.py, core/sub_grid.py를 래핑.
Core 코드를 수정하지 않고, 모듈 인터페이스로 감싼다.

docs/30_technical/module-architecture.md 섹션 3.2 "[A] geography" 참조.
"""
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.core.navigator import Direction, LocationView, Navigator
from src.core.sub_grid import SubGridGenerator
from src.core.world_generator import MapNode, NodeTier, WorldGenerator
from src.modules.base import Action, GameContext, GameModule

logger = get_logger(__name__)

# 메인 그리드 4방향 (서브그리드는 UP/DOWN 추가)
_MAIN_DIRECTIONS = [
    ("north", "북쪽으로 이동", Direction.NORTH),
    ("south", "남쪽으로 이동", Direction.SOUTH),
    ("east", "동쪽으로 이동", Direction.EAST),
    ("west", "서쪽으로 이동", Direction.WEST),
]

_SUB_DIRECTIONS = _MAIN_DIRECTIONS + [
    ("up", "위로 이동", Direction.UP),
    ("down", "아래로 이동", Direction.DOWN),
]


class GeographyModule(GameModule):
    """지리 시스템 모듈

    담당:
    - 맵 노드 조회/생성 (WorldGenerator 래핑)
    - 위치 정보 제공 (Navigator 래핑)
    - 서브그리드 관련 정보 (SubGridGenerator 래핑)

    의존성: 없음 (Layer 1 기반 모듈)

    참조하는 engine.py 인스턴스:
    - self.world (WorldGenerator)
    - self.navigator (Navigator)
    - self.sub_grid_generator (SubGridGenerator)
    """

    def __init__(
        self,
        world_generator: WorldGenerator,
        navigator: Navigator,
        sub_grid_generator: SubGridGenerator,
    ) -> None:
        super().__init__()
        self._world = world_generator
        self._navigator = navigator
        self._sub_grid_gen = sub_grid_generator

    @property
    def name(self) -> str:
        return "geography"

    @property
    def dependencies(self) -> List[str]:
        return []

    def on_enable(self) -> None:
        logger.info("geography 모듈 활성화")

    def on_disable(self) -> None:
        logger.info("geography 모듈 비활성화")

    def on_turn(self, context: GameContext) -> None:
        """턴 처리 - 현재 geography는 턴별 처리 없음.

        향후 확장: 바이옴 시간 변화, 서브그리드 상태 업데이트 등.
        """
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 시 지리 정보를 context.extra에 저장.

        다른 모듈(overlay, npc 등)이 context.extra["geography"]를 참조할 수 있다.

        Args:
            node_id: "x_y" 형식 좌표 문자열
            context: 게임 컨텍스트
        """
        try:
            parts = node_id.split("_")
            x, y = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            logger.warning(f"geography: 좌표 파싱 실패: {node_id}")
            return

        node = self._world.get_or_generate(x, y)
        if not node:
            logger.warning(f"geography: 노드 생성 실패: ({x}, {y})")
            return

        view = self._navigator.get_location_view(x, y, context.player_id)

        context.extra["geography"] = {
            "node": node,
            "location_view": view,
            "x": x,
            "y": y,
            "tier": node.tier.value,
            "has_depth": self._check_has_depth(node),
        }

        logger.debug(f"geography.on_node_enter: ({x}, {y}) tier={node.tier.value}")

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """geography가 제공하는 행동 목록.

        현재 위치 상태에 따라 이동 방향과 서브그리드 진입/탈출 액션을 반환.

        context.extra에 in_sub_grid 정보가 없으면 메인 그리드 기준으로 판단.
        """
        actions: List[Action] = []

        # extra에서 서브그리드 상태 확인
        in_sub_grid = context.extra.get("in_sub_grid", False)

        if in_sub_grid:
            # 서브그리드: 6방향 이동
            for dir_name, display, _ in _SUB_DIRECTIONS:
                actions.append(Action(
                    name=f"move_{dir_name}",
                    display_name=display,
                    module_name=self.name,
                ))

            # 입구(0,0,0)이면 exit 가능
            sub_pos = context.extra.get("sub_position", {})
            if (
                sub_pos.get("sx", -1) == 0
                and sub_pos.get("sy", -1) == 0
                and sub_pos.get("sz", -1) == 0
            ):
                actions.append(Action(
                    name="exit_depth",
                    display_name="밖으로 나가기",
                    module_name=self.name,
                ))
        else:
            # 메인 그리드: 4방향 이동
            for dir_name, display, _ in _MAIN_DIRECTIONS:
                actions.append(Action(
                    name=f"move_{dir_name}",
                    display_name=display,
                    module_name=self.name,
                ))

            # depth 진입 가능 여부 확인
            geo_data = context.extra.get("geography", {})
            if geo_data.get("has_depth", False):
                actions.append(Action(
                    name="enter_depth",
                    display_name="깊은 곳으로 진입",
                    module_name=self.name,
                ))

        return actions

    # --- geography 전용 메서드 ---

    def get_node(self, x: int, y: int) -> Optional[MapNode]:
        """좌표로 노드 조회 (없으면 None)"""
        return self._world.get_node(x, y)

    def get_or_generate_node(self, x: int, y: int) -> MapNode:
        """좌표로 노드 조회/생성"""
        return self._world.get_or_generate(x, y)

    def get_location_view(self, x: int, y: int, player_id: str) -> LocationView:
        """위치 뷰 조회 (Navigator 래핑)"""
        return self._navigator.get_location_view(x, y, player_id)

    @property
    def world(self) -> WorldGenerator:
        """WorldGenerator 직접 접근 (engine 호환용)"""
        return self._world

    @property
    def navigator(self) -> Navigator:
        """Navigator 직접 접근 (engine 호환용)"""
        return self._navigator

    @property
    def sub_grid_generator(self) -> SubGridGenerator:
        """SubGridGenerator 직접 접근 (engine 호환용)"""
        return self._sub_grid_gen

    # --- 내부 헬퍼 ---

    @staticmethod
    def _check_has_depth(node: MapNode) -> bool:
        """노드에 서브그리드(depth) 진입이 가능한지 확인.

        현재 로직: engine.py L744와 동일 — tier가 UNCOMMON 또는 RARE.
        TODO: 실제 depth_name 필드 확인으로 교체.
        """
        return node.tier in [NodeTier.UNCOMMON, NodeTier.RARE]
```

---

## 3. 테스트 작성

### 3.1 `tests/test_modules/test_geography.py`

```python
"""GeographyModule 테스트"""
import pytest
from unittest.mock import MagicMock

from src.modules.base import GameContext, Action
from src.modules.geography.module import GeographyModule
from src.modules.module_manager import ModuleManager


def make_mock_node(tier_value=1, tier_enum=None):
    """테스트용 Mock MapNode"""
    node = MagicMock()
    node.tier.value = tier_value
    if tier_enum:
        node.tier = tier_enum
    node.coordinate = "5_3"
    return node


def make_context(**kwargs):
    defaults = {
        "player_id": "test_player",
        "current_node_id": "0_0",
        "current_turn": 1,
        "db_session": MagicMock(),
    }
    defaults.update(kwargs)
    return GameContext(**defaults)


def make_geography():
    """테스트용 GeographyModule (Mock 의존성)"""
    return GeographyModule(
        world_generator=MagicMock(),
        navigator=MagicMock(),
        sub_grid_generator=MagicMock(),
    )


class TestGeographyBasics:
    def test_name(self):
        geo = make_geography()
        assert geo.name == "geography"

    def test_no_dependencies(self):
        geo = make_geography()
        assert geo.dependencies == []

    def test_enable_disable(self):
        geo = make_geography()
        geo.on_enable()
        geo.enabled = True
        assert geo.enabled is True
        geo.on_disable()
        geo.enabled = False
        assert geo.enabled is False

    def test_on_turn_no_error(self):
        geo = make_geography()
        ctx = make_context()
        geo.on_turn(ctx)


class TestGeographyInModuleManager:
    def test_register_and_enable(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        assert mm.enable("geography") is True
        assert mm.is_enabled("geography") is True

    def test_provides_movement_actions(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        mm.enable("geography")

        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        action_names = [a.name for a in actions]
        assert "move_north" in action_names
        assert "move_south" in action_names
        assert "move_east" in action_names
        assert "move_west" in action_names

    def test_disabled_no_actions(self):
        mm = ModuleManager()
        geo = make_geography()
        mm.register(geo)
        ctx = make_context()
        actions = mm.get_all_actions(ctx)
        assert len(actions) == 0


class TestOnNodeEnter:
    def test_stores_geography_in_extra(self):
        mock_world = MagicMock()
        mock_node = make_mock_node(tier_value=1)
        mock_world.get_or_generate.return_value = mock_node

        mock_nav = MagicMock()
        mock_view = MagicMock()
        mock_nav.get_location_view.return_value = mock_view

        geo = GeographyModule(
            world_generator=mock_world,
            navigator=mock_nav,
            sub_grid_generator=MagicMock(),
        )

        ctx = make_context(current_node_id="5_3")
        geo.on_node_enter("5_3", ctx)

        assert "geography" in ctx.extra
        assert ctx.extra["geography"]["x"] == 5
        assert ctx.extra["geography"]["y"] == 3
        assert ctx.extra["geography"]["node"] is mock_node
        assert ctx.extra["geography"]["location_view"] is mock_view

    def test_invalid_node_id_no_crash(self):
        geo = make_geography()
        ctx = make_context()
        geo.on_node_enter("invalid", ctx)
        assert "geography" not in ctx.extra

    def test_world_get_or_generate_called(self):
        mock_world = MagicMock()
        mock_world.get_or_generate.return_value = make_mock_node()
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        ctx = make_context()
        geo.on_node_enter("10_20", ctx)
        mock_world.get_or_generate.assert_called_once_with(10, 20)


class TestGetAvailableActions:
    def test_main_grid_4_directions(self):
        geo = make_geography()
        ctx = make_context()
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "move_north" in names
        assert "move_up" not in names
        assert "enter_depth" not in names

    def test_main_grid_with_depth(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["geography"] = {"has_depth": True}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "enter_depth" in names

    def test_sub_grid_6_directions(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "move_north" in names
        assert "move_up" in names
        assert "move_down" in names
        assert "enter_depth" not in names

    def test_sub_grid_at_entrance_has_exit(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        ctx.extra["sub_position"] = {"sx": 0, "sy": 0, "sz": 0}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "exit_depth" in names

    def test_sub_grid_deep_no_exit(self):
        geo = make_geography()
        ctx = make_context()
        ctx.extra["in_sub_grid"] = True
        ctx.extra["sub_position"] = {"sx": 1, "sy": 0, "sz": -2}
        actions = geo.get_available_actions(ctx)
        names = [a.name for a in actions]
        assert "exit_depth" not in names


class TestGeographyAccessors:
    def test_get_node_delegates(self):
        mock_world = MagicMock()
        mock_world.get_node.return_value = "fake_node"
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        result = geo.get_node(5, 3)
        mock_world.get_node.assert_called_once_with(5, 3)
        assert result == "fake_node"

    def test_get_or_generate_delegates(self):
        mock_world = MagicMock()
        mock_world.get_or_generate.return_value = "generated_node"
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=MagicMock(),
            sub_grid_generator=MagicMock(),
        )
        result = geo.get_or_generate_node(7, 8)
        mock_world.get_or_generate.assert_called_once_with(7, 8)
        assert result == "generated_node"

    def test_property_accessors(self):
        mock_world = MagicMock()
        mock_nav = MagicMock()
        mock_sub = MagicMock()
        geo = GeographyModule(
            world_generator=mock_world,
            navigator=mock_nav,
            sub_grid_generator=mock_sub,
        )
        assert geo.world is mock_world
        assert geo.navigator is mock_nav
        assert geo.sub_grid_generator is mock_sub


class TestModuleNameOnActions:
    def test_all_actions_have_correct_module_name(self):
        geo = make_geography()
        ctx = make_context()
        actions = geo.get_available_actions(ctx)
        for action in actions:
            assert action.module_name == "geography"
```

---

## 4. 품질 게이트

```bash
ruff check src/modules/geography/ tests/test_modules/test_geography.py
pytest tests/test_modules/test_geography.py -v
pytest tests/ -v
mypy src/modules/geography/
```

---

## 5. 체크리스트

- [ ] `src/modules/geography/__init__.py` 생성
- [ ] `src/modules/geography/module.py` 구현
- [ ] WorldGenerator의 `get_node()`, `get_or_generate()` 메서드명 확인 (engine.py L340, L1086)
- [ ] Navigator의 `get_location_view()` 시그니처 확인 (engine.py L378)
- [ ] `tests/test_modules/test_geography.py` 작성 + 통과
- [ ] `ruff check` 통과
- [ ] `pytest` 전체 통과
- [ ] 커밋: `feat: add geography module wrapping existing core systems`

---

## 6. 주의사항

- **기존 core/ 파일을 수정하지 않는다.**
- engine.py도 이 지시서에서 수정하지 않는다 (지시서 #04에서 처리).
- `_check_has_depth`의 로직은 engine.py L744와 동일하게 유지.
- Module → Core 의존은 허용. Module → Module은 금지.
