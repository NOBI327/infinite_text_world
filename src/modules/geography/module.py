"""GeographyModule - 지리 시스템 모듈

기존 core/world_generator.py, core/navigator.py, core/sub_grid.py를 래핑.
Core 코드를 수정하지 않고, 모듈 인터페이스로 감싼다.

docs/30_technical/module-architecture.md 섹션 3.2 "[A] geography" 참조.
"""

from typing import List, Optional

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
                actions.append(
                    Action(
                        name=f"move_{dir_name}",
                        display_name=display,
                        module_name=self.name,
                    )
                )

            # 입구(0,0,0)이면 exit 가능
            sub_pos = context.extra.get("sub_position", {})
            if (
                sub_pos.get("sx", -1) == 0
                and sub_pos.get("sy", -1) == 0
                and sub_pos.get("sz", -1) == 0
            ):
                actions.append(
                    Action(
                        name="exit_depth",
                        display_name="밖으로 나가기",
                        module_name=self.name,
                    )
                )
        else:
            # 메인 그리드: 4방향 이동
            for dir_name, display, _ in _MAIN_DIRECTIONS:
                actions.append(
                    Action(
                        name=f"move_{dir_name}",
                        display_name=display,
                        module_name=self.name,
                    )
                )

            # depth 진입 가능 여부 확인
            geo_data = context.extra.get("geography", {})
            if geo_data.get("has_depth", False):
                actions.append(
                    Action(
                        name="enter_depth",
                        display_name="깊은 곳으로 진입",
                        module_name=self.name,
                    )
                )

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
