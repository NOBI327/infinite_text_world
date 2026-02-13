"""ItemModule — GameModule 인터페이스

item-system.md 섹션 1.3 대응.
Layer 1 기반 모듈 (geography, npc, item).
"""

import logging
from typing import List

from src.core.item.restock import (
    ShopRestockConfig,
    check_restock_needed,
    calculate_restock_deficit,
)
from src.modules.base import Action, GameContext, GameModule
from src.services.item_service import ItemService

logger = logging.getLogger(__name__)


class ItemModule(GameModule):
    """아이템 시스템 모듈

    담당:
    - 바닥/NPC 아이템 정보를 context.extra에 공급
    - 아이템 관련 액션 제공 (inventory, pickup, drop, use, browse)
    - 임시 자동보충 (TEMPORARY)

    의존성: [] (Layer 1 기반 모듈)
    """

    def __init__(self, item_service: ItemService) -> None:
        super().__init__()
        self._service = item_service
        self._restock_configs: list[ShopRestockConfig] = []

    @property
    def name(self) -> str:
        return "item"

    @property
    def dependencies(self) -> List[str]:
        return []

    def register_restock_config(self, config: ShopRestockConfig) -> None:
        """상인 NPC 보충 설정 등록. TEMPORARY."""
        self._restock_configs.append(config)

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        """턴 처리: 임시 자동보충 실행 (TEMPORARY)."""
        for config in self._restock_configs:
            if check_restock_needed(config, context.current_turn):
                self._execute_restock(config)

    def _execute_restock(self, config: ShopRestockConfig) -> None:
        """보충 실행. TEMPORARY: Phase B 자율행동 구현 시 제거."""
        current_stock: dict[str, int] = {}
        for proto_id in config.stock_template:
            count = self._service.count_instances(
                "container", config.shelf_instance_id, proto_id
            )
            current_stock[proto_id] = count

        deficit = calculate_restock_deficit(config, current_stock)
        for proto_id, needed in deficit.items():
            for _ in range(needed):
                self._service.create_instance(
                    prototype_id=proto_id,
                    owner_type="container",
                    owner_id=config.shelf_instance_id,
                )
            logger.debug(
                "Restocked %d x %s to shelf %s",
                needed,
                proto_id,
                config.shelf_instance_id,
            )

    def on_node_enter(self, context: GameContext) -> None:
        """노드 진입 시 바닥 아이템 정보를 context.extra에 추가."""
        node_items = self._service.get_instances_by_owner(
            "node", context.current_node_id
        )
        context.extra["item"] = {
            "node_items": [
                {"instance_id": i.instance_id, "prototype_id": i.prototype_id}
                for i in node_items
            ],
        }

    def get_available_actions(self, context: GameContext) -> List[Action]:
        """아이템 관련 액션 반환."""
        return [
            Action(
                name="inventory",
                display_name="Inventory",
                module_name="item",
                description="인벤토리 확인",
            ),
            Action(
                name="pickup",
                display_name="Pick Up",
                module_name="item",
                description="바닥 아이템 줍기",
                params={"instance_id": "str"},
            ),
            Action(
                name="drop",
                display_name="Drop",
                module_name="item",
                description="아이템 버리기",
                params={"instance_id": "str"},
            ),
            Action(
                name="use",
                display_name="Use",
                module_name="item",
                description="아이템 사용",
                params={"instance_id": "str"},
            ),
            Action(
                name="browse",
                display_name="Browse",
                module_name="item",
                description="상점 선반 둘러보기",
                params={"container_id": "str"},
            ),
        ]
