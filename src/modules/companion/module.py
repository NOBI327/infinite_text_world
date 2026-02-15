"""CompanionModule — GameModule 인터페이스

companion-system.md 섹션 1.3 대응.
Layer 3 상호작용 모듈.
"""

import logging
from typing import List

from src.modules.base import Action, GameContext, GameModule
from src.services.companion_service import CompanionService

logger = logging.getLogger(__name__)


class CompanionModule(GameModule):
    """동행 시스템 모듈

    담당:
    - 동행 NPC 정보를 context.extra에 공급
    - recruit / dismiss 액션 제공

    의존성: ["npc_core", "relationship", "dialogue"]
    """

    def __init__(self, companion_service: CompanionService) -> None:
        super().__init__()
        self._service = companion_service

    @property
    def name(self) -> str:
        return "companion"

    @property
    def dependencies(self) -> List[str]:
        return ["npc_core", "relationship", "dialogue"]

    def on_enable(self) -> None:
        """CompanionService의 이벤트 핸들러는 __init__에서 이미 등록됨."""
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        """턴 처리. CompanionService._on_turn_processed가 EventBus로 처리."""
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 시 동행 정보를 context.extra에 추가."""
        companion = self._service.get_active_companion(context.player_id)
        if companion:
            context.extra["companion"] = {
                "npc_id": companion.npc_id,
                "companion_type": companion.companion_type,
            }

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """동행 관련 액션."""
        companion = self._service.get_active_companion(context.player_id)
        actions: List[Action] = []

        if companion is None:
            actions.append(
                Action(
                    name="recruit",
                    display_name="Recruit",
                    module_name="companion",
                    description="NPC에게 동행 요청",
                    params={"npc_id": "str"},
                )
            )
        else:
            actions.append(
                Action(
                    name="dismiss",
                    display_name="Dismiss",
                    module_name="companion",
                    description="동행 해산",
                )
            )

        return actions
