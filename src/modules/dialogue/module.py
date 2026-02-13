"""DialogueModule — GameModule 인터페이스 구현

dialogue-system.md 섹션 1.3 대응.
DialogueService를 래핑하여 ModuleManager 생명주기에 통합.
EventBus 구독은 DialogueService가 자체 처리.
"""

from __future__ import annotations

from typing import List

from src.core.logging import get_logger
from src.modules.base import Action, GameContext, GameModule
from src.services.dialogue_service import DialogueService

logger = get_logger(__name__)


class DialogueModule(GameModule):
    """대화 시스템 모듈

    담당:
    - DialogueService 래핑 (GameModule 인터페이스)
    - 대화 가능 상태를 context.extra에 표시
    - talk / say / end_talk 액션 제공

    의존성: ["npc_core", "relationship"]
    """

    def __init__(self, dialogue_service: DialogueService) -> None:
        super().__init__()
        self._service = dialogue_service

    @property
    def name(self) -> str:
        return "dialogue"

    @property
    def dependencies(self) -> List[str]:
        return ["npc_core", "relationship"]

    def on_enable(self) -> None:
        """모듈 활성화. EventBus 구독은 DialogueService가 이미 처리."""
        logger.info("dialogue 모듈 활성화")

    def on_disable(self) -> None:
        """모듈 비활성화."""
        logger.info("dialogue 모듈 비활성화")

    def on_turn(self, context: GameContext) -> None:
        """대화 중에는 다른 모듈의 턴이 처리되지 않으므로 패스."""
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 시 대화 가능 상태를 context.extra에 추가."""
        context.extra["dialogue"] = {
            "active_session": self._service.get_active_session() is not None,
        }

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """대화 관련 액션 반환."""
        if self._service.get_active_session() is not None:
            return [
                Action(
                    name="say",
                    display_name="Say",
                    module_name="dialogue",
                    description="대화 중 발언",
                    params={"text": "str"},
                ),
                Action(
                    name="end_talk",
                    display_name="End Talk",
                    module_name="dialogue",
                    description="대화 종료",
                ),
            ]
        return [
            Action(
                name="talk",
                display_name="Talk",
                module_name="dialogue",
                description="NPC와 대화 시작",
                params={"npc_id": "str"},
            ),
        ]

    # ── 공개 API ──────────────────────────────────────────────

    @property
    def service(self) -> DialogueService:
        """DialogueService 접근 (API 레이어 용)"""
        return self._service
