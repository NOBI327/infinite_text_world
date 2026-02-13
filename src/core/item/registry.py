"""아이템 원형 저장소 — JSON 로드 + 동적 등록"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .models import ItemPrototype, ItemType

logger = logging.getLogger(__name__)


class PrototypeRegistry:
    """
    아이템 원형 저장소.
    초기 데이터(JSON) + 동적 생성 Prototype 관리.
    """

    def __init__(self) -> None:
        self._prototypes: dict[str, ItemPrototype] = {}

    def load_from_json(self, path: str | Path) -> int:
        """seed_items.json 로드. 반환: 로드된 수량.

        JSON 배열의 각 객체를 ItemPrototype으로 변환.
        tags는 list → tuple 변환.
        item_type은 문자열 → ItemType enum 변환.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw_list: list[dict] = json.load(f)

        count = 0
        for raw in raw_list:
            try:
                proto = ItemPrototype(
                    item_id=raw["item_id"],
                    item_type=ItemType(raw["item_type"]),
                    weight=float(raw["weight"]),
                    bulk=int(raw["bulk"]),
                    base_value=int(raw["base_value"]),
                    primary_material=raw["primary_material"],
                    axiom_tags=dict(raw.get("axiom_tags", {})),
                    max_durability=int(raw["max_durability"]),
                    durability_loss_per_use=int(raw["durability_loss_per_use"]),
                    broken_result=raw.get("broken_result"),
                    container_capacity=int(raw.get("container_capacity", 0)),
                    flavor_text=raw.get("flavor_text", ""),
                    tags=tuple(raw.get("tags", [])),
                    name_kr=raw.get("name_kr", ""),
                )
                self._prototypes[proto.item_id] = proto
                count += 1
            except (KeyError, ValueError) as e:
                logger.warning(
                    "Failed to load prototype: %s — %s", raw.get("item_id", "?"), e
                )

        logger.info("Loaded %d prototypes from %s", count, path)
        return count

    def register(self, prototype: ItemPrototype) -> None:
        """동적 Prototype 등록 (공리 조합 생성 등).
        이미 존재하는 item_id면 경고 로그 후 덮어쓴다.
        """
        if prototype.item_id in self._prototypes:
            logger.warning("Overwriting existing prototype: %s", prototype.item_id)
        self._prototypes[prototype.item_id] = prototype

    def get(self, item_id: str) -> Optional[ItemPrototype]:
        """O(1) 조회. 없으면 None."""
        return self._prototypes.get(item_id)

    def get_all(self) -> list[ItemPrototype]:
        """전체 Prototype 반환."""
        return list(self._prototypes.values())

    def search_by_tags(self, tags: list[str]) -> list[ItemPrototype]:
        """tags 중 하나라도 포함하는 Prototype 반환."""
        tag_set = set(tags)
        return [p for p in self._prototypes.values() if tag_set & set(p.tags)]

    def search_by_axiom(self, axiom_tag: str) -> list[ItemPrototype]:
        """axiom_tags에 해당 태그가 있는 Prototype 반환."""
        return [p for p in self._prototypes.values() if axiom_tag in p.axiom_tags]

    def count(self) -> int:
        """등록된 Prototype 수."""
        return len(self._prototypes)
