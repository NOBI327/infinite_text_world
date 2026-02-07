"""모듈 관리자 - 등록, 활성화/비활성화, 의존성 검증, 턴/이벤트 전파"""

from typing import Dict, List

from src.core.logging import get_logger
from src.core.event_bus import EventBus
from src.modules.base import GameModule, GameContext, Action

logger = get_logger(__name__)


class ModuleManager:
    """모듈 토글 및 생명주기 관리

    docs/30_technical/module-architecture.md 섹션 4.2 참조.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, GameModule] = {}
        self._event_bus: EventBus = EventBus()

    @property
    def event_bus(self) -> EventBus:
        """모듈이 이벤트 구독/발행에 사용할 EventBus"""
        return self._event_bus

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
        """활성 모듈의 on_turn 순차 호출 + 턴 종료 시 이벤트 체인 초기화"""
        for module in self._modules.values():
            if module.enabled:
                module.on_turn(context)
        self._event_bus.reset_chain()

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
