"""아이템 도메인 모델 (DB 무관)"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ItemType(str, Enum):
    EQUIPMENT = "equipment"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    MISC = "misc"


@dataclass(frozen=True)
class ItemPrototype:
    """아이템 원형 — 불변. seed_items.json에서 로드."""

    item_id: str  # "wpn_rusty_sword"
    item_type: ItemType

    # 물리
    weight: float  # kg
    bulk: int  # 1~10
    base_value: int  # 기본 거래가

    # 재질 & 공리
    primary_material: str  # "Iron", "Wood", ...
    axiom_tags: dict[str, int]  # {"Scindere": 2, "Ferrum": 1}

    # 내구도
    max_durability: int  # 0 = 파괴 불가
    durability_loss_per_use: int
    broken_result: Optional[str]  # 파괴 시 변환 item_id (None = 소멸)

    # 용기
    container_capacity: int = 0  # 0 = 용기 아님

    # 서술 & 검색
    flavor_text: str = ""  # AI 묘사 힌트 (i18n 일괄 치환 예정)
    tags: tuple[str, ...] = ()  # frozen이므로 tuple 사용

    # 표시용 (i18n 일괄 치환 예정)
    name_kr: str = ""


@dataclass
class ItemInstance:
    """게임 내 아이템 개체. Prototype의 Delta만 저장."""

    instance_id: str  # UUID
    prototype_id: str  # ItemPrototype.item_id 참조

    # 위치
    owner_type: str  # "player"|"npc"|"node"|"container"
    owner_id: str  # 소유자/위치 ID

    # 상태
    current_durability: int
    state_tags: list[str] = field(default_factory=list)  # ["wet", "rusty"]

    # 메타
    acquired_turn: int = 0
    custom_name: Optional[str] = None
