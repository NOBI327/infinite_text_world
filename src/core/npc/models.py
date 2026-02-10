"""NPC Core 도메인 모델

npc-system.md 섹션 2, 8, 13 대응.
DB 무관 순수 데이터 클래스.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EntityType(str, Enum):
    """배경 존재 유형 (npc-system.md 섹션 2.1)"""

    RESIDENT = "resident"  # 거주형
    WANDERER = "wanderer"  # 유랑형
    HOSTILE = "hostile"  # 적대형


@dataclass
class BackgroundEntity:
    """승격 전 배경 존재 (npc-system.md 섹션 2.2)"""

    entity_id: str
    entity_type: EntityType

    # 위치
    current_node: str
    home_node: Optional[str] = None  # 거주형만

    # 역할/외형
    role: str = ""
    appearance_seed: Dict = field(default_factory=dict)

    # 승격 진행
    promotion_score: int = 0
    promoted: bool = False

    # 이름 시드
    name_seed: Optional[Dict] = None

    # 슬롯 (거주형)
    slot_id: Optional[str] = None

    # 전투 추적 (적대형)
    temp_combat_id: Optional[str] = None

    created_turn: int = 0


@dataclass
class BackgroundSlot:
    """거주형 배경인물 슬롯 (npc-system.md 섹션 3.5)"""

    slot_id: str
    node_id: str
    facility_id: str
    facility_type: str

    # 역할
    role: str = ""
    is_required: bool = False

    # 현재 배치된 개체 ID
    entity_id: Optional[str] = None

    # 리셋 관리
    reset_interval: int = 24
    last_reset_turn: int = 0


@dataclass
class HEXACO:
    """HEXACO 성격 6요인 (npc-system.md 섹션 8.1)

    각 값: 0.0 ~ 1.0 (중립 = 0.5)
    """

    H: float = 0.5  # Honesty-Humility
    E: float = 0.5  # Emotionality
    X: float = 0.5  # eXtraversion
    A: float = 0.5  # Agreeableness
    C: float = 0.5  # Conscientiousness
    O: float = 0.5  # Openness  # noqa: E741

    def to_dict(self) -> Dict[str, float]:
        return {
            "H": self.H,
            "E": self.E,
            "X": self.X,
            "A": self.A,
            "C": self.C,
            "O": self.O,
        }


@dataclass
class NPCData:
    """NPC 완전 데이터 (npc-system.md 섹션 13)

    Core 레이어용 순수 데이터. DB ORM(NPCModel)과 별개.
    """

    npc_id: str

    # 명칭
    full_name: Dict = field(default_factory=dict)  # NPCFullName 직렬화
    given_name: str = ""

    # 성격
    hexaco: HEXACO = field(default_factory=HEXACO)

    # 능력치
    character_sheet: Dict = field(default_factory=dict)
    resonance_shield: Dict = field(default_factory=dict)
    axiom_proficiencies: Dict[str, int] = field(default_factory=dict)

    # 위치
    home_node: Optional[str] = None
    current_node: str = ""

    # 자율 행동
    routine: Optional[Dict] = None
    state: Dict = field(default_factory=dict)

    # 소속
    lord_id: Optional[str] = None
    faction_id: Optional[str] = None
    loyalty: float = 0.5

    # 경제
    currency: int = 0

    # 메타
    origin_type: str = "promoted"  # "promoted" | "scripted"
    origin_entity_type: Optional[str] = None
    role: str = ""
    tags: List[str] = field(default_factory=list)
