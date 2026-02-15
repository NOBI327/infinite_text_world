"""QuestModule — GameModule 인터페이스"""

import logging
from typing import List

from src.modules.base import Action, GameContext, GameModule
from src.services.quest_service import QuestService

logger = logging.getLogger(__name__)


class QuestModule(GameModule):
    """퀘스트 시스템 모듈

    담당:
    - 활성 퀘스트 정보를 context.extra에 공급
    - 퀘스트 관련 액션 제공 (quest_list, quest_detail, quest_abandon)

    의존성: ["npc_core", "relationship", "dialogue"]
    """

    def __init__(self, quest_service: QuestService) -> None:
        super().__init__()
        self._service = quest_service

    @property
    def name(self) -> str:
        return "quest"

    @property
    def dependencies(self) -> List[str]:
        return ["npc_core", "relationship", "dialogue"]

    def on_enable(self) -> None:
        """QuestService의 이벤트 핸들러는 __init__에서 이미 등록됨."""
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        """턴 처리. QuestService._on_turn_processed가 EventBus로 처리하므로 여기서는 pass."""
        pass

    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """노드 진입 시 활성 퀘스트 정보를 context.extra에 추가."""
        active_quests = self._service.get_active_quests()
        relevant = [
            q for q in active_quests if context.current_node_id in q.target_node_ids
        ]
        context.extra["quest"] = {
            "active_count": len(active_quests),
            "relevant_quests": [
                {
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "quest_type": q.quest_type,
                }
                for q in relevant
            ],
        }

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """퀘스트 관련 액션."""
        return [
            Action(
                name="quest_list",
                display_name="Quests",
                module_name="quest",
                description="활성 퀘스트 목록",
            ),
            Action(
                name="quest_detail",
                display_name="Quest Detail",
                module_name="quest",
                description="퀘스트 상세",
                params={"quest_id": "str"},
            ),
            Action(
                name="quest_abandon",
                display_name="Abandon Quest",
                module_name="quest",
                description="퀘스트 포기",
                params={"quest_id": "str"},
            ),
        ]
