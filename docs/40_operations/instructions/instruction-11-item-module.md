# 구현 지시서 #11: 아이템 시스템 (Item Module)

**발행일**: 2026-02-14
**발행자**: 사령탑 세션
**수행자**: Claude Code
**의존**: #08(NPC), #09(관계), #10(대화) 완료 전제

---

## 실행 전 필수 사항

1. `docs/INDEX.md`, `docs/SRC_INDEX.md` 를 읽고 현재 프로젝트 구조를 파악할 것
2. 각 블록 시작 전 참조 문서를 반드시 읽을 것
3. 각 블록은 **단독 실행/테스트 가능**해야 한다
4. 블록 순서: #11-0 → A → B → C → D (역순 금지)
5. `ruff check src/ tests/` + `pytest -v` 통과 후 다음 블록 진행

---

## 아키텍처 원칙 (위반 금지)

- 의존 방향: API → Service → Core → DB (역방향 금지)
- Service간 직접 호출 금지, EventBus 경유
- Core는 DB를 모른다 (SQLAlchemy import 금지)
- print() 사용 금지, logging 모듈 사용

---

# #11-0: 메타 정비 + 데이터 배치

## 목적
시드 데이터 배치, event_types 갱신, INDEX 갱신

## 작업

### 0-1. 데이터 파일 배치

아래 파일을 프로젝트에 배치한다:

- `src/data/seed_items.json` — 함께 제공되는 파일을 배치
- `src/data/axiom_tag_mapping.json` — 함께 제공되는 파일을 배치

### 0-2. event_types.py 갱신

참조: `src/core/event_types.py`

기존 EventTypes 클래스에 아래 상수를 추가 (기존 중복 확인 후):

```python
# Item events
ITEM_TRANSFERRED = "item_transferred"
ITEM_BROKEN = "item_broken"
ITEM_CREATED = "item_created"
```

### 0-3. docs/INDEX.md 갱신

`20_design/` 섹션의 item-system.md 항목에 코드 구현 상태를 반영:

```
### item-system.md
- **목적:** 아이템 체계, 거래, 선물, 인벤토리, 내구도 시스템 설계
- **핵심:** Prototype(불변) + Instance(가변) 분리, axiom_tags 매핑, bulk 기반 인벤토리, 4종 분류, 거래/흥정/선물 시스템, 임시 자동보충
- **상태:** 확정 (v1.0), 시드 데이터 60종
```

### 0-4. item-system.md 배치

함께 제공되는 수정된 item-system.md를 `docs/20_design/item-system.md`에 배치(기존 교체).

## 검증
- `ruff check src/`
- `pytest -v` (기존 테스트 깨지지 않음)
- `python -c "import json; json.load(open('src/data/seed_items.json'))"` — JSON 유효성
- `python -c "import json; json.load(open('src/data/axiom_tag_mapping.json'))"` — JSON 유효성

---

# #11-A: Item Core 모델

## 목적
아이템 시스템의 순수 Python 도메인 모델과 PrototypeRegistry 구현

## 참조 문서
- `docs/20_design/item-system.md` — 섹션 2(데이터 모델), 섹션 3(Axiom 태그 매핑)

## 산출물

### A-1. `src/core/item/__init__.py`

패키지 초기화 + re-export.

### A-2. `src/core/item/models.py`

item-system.md 섹션 2.1, 2.2 기반.

```python
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
    item_id: str                        # "wpn_rusty_sword"
    item_type: ItemType
    
    # 물리
    weight: float                       # kg
    bulk: int                           # 1~10
    base_value: int                     # 기본 거래가
    
    # 재질 & 공리
    primary_material: str               # "Iron", "Wood", ...
    axiom_tags: dict[str, int]          # {"Scindere": 2, "Ferrum": 1}
    
    # 내구도
    max_durability: int                 # 0 = 파괴 불가
    durability_loss_per_use: int
    broken_result: Optional[str]        # 파괴 시 변환 item_id (None = 소멸)
    
    # 용기
    container_capacity: int = 0         # 0 = 용기 아님
    
    # 서술 & 검색
    flavor_text: str = ""               # AI 묘사 힌트 (i18n 일괄 치환 예정)
    tags: tuple[str, ...] = ()          # frozen이므로 tuple 사용
    
    # 표시용 (i18n 일괄 치환 예정)
    name_kr: str = ""


@dataclass
class ItemInstance:
    """게임 내 아이템 개체. Prototype의 Delta만 저장."""
    instance_id: str                    # UUID
    prototype_id: str                   # ItemPrototype.item_id 참조
    
    # 위치
    owner_type: str                     # "player"|"npc"|"node"|"container"
    owner_id: str                       # 소유자/위치 ID
    
    # 상태
    current_durability: int
    state_tags: list[str] = field(default_factory=list)  # ["wet", "rusty"]
    
    # 메타
    acquired_turn: int = 0
    custom_name: Optional[str] = None
```

**주의**: `ItemPrototype`은 `frozen=True`이므로 `tags` 필드는 `list`가 아닌 `tuple`을 사용한다. JSON 로드 시 변환 필요.

### A-3. `src/core/item/registry.py`

item-system.md 섹션 2.4 기반.

```python
"""아이템 원형 저장소 — JSON 로드 + 동적 등록"""
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
    
    def register(self, prototype: ItemPrototype) -> None:
        """동적 Prototype 등록 (공리 조합 생성 등).
        이미 존재하는 item_id면 경고 로그 후 덮어쓴다.
        """
    
    def get(self, item_id: str) -> Optional[ItemPrototype]:
        """O(1) 조회. 없으면 None."""
    
    def get_all(self) -> list[ItemPrototype]:
        """전체 Prototype 반환."""
    
    def search_by_tags(self, tags: list[str]) -> list[ItemPrototype]:
        """tags 중 하나라도 포함하는 Prototype 반환."""
    
    def search_by_axiom(self, axiom_tag: str) -> list[ItemPrototype]:
        """axiom_tags에 해당 태그가 있는 Prototype 반환."""
    
    def count(self) -> int:
        """등록된 Prototype 수."""
```

### A-4. `src/core/item/axiom_mapping.py`

item-system.md 섹션 3 기반.

```python
"""Axiom 태그 매핑 — 자유 태그 → Divine Axiom 연결"""
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class AxiomTagInfo:
    """태그 매핑 정보"""
    tag: str                    # "Ignis"
    domain: str                 # "Primordial"
    resonance: str              # "Destruction"
    axiom_ids: tuple[str, ...]  # ("AXM_042", "AXM_043")
    description: str            # "화염, 연소, 열"

class AxiomTagMapping:
    """axiom_tag_mapping.json 로더"""
    
    def __init__(self) -> None:
        self._mapping: dict[str, AxiomTagInfo] = {}
    
    def load_from_json(self, path: str | Path) -> int:
        """매핑 파일 로드. 반환: 로드된 태그 수."""
    
    def get(self, tag: str) -> Optional[AxiomTagInfo]:
        """태그 정보 조회."""
    
    def get_domain(self, tag: str) -> Optional[str]:
        """태그의 Domain 반환."""
    
    def get_resonance(self, tag: str) -> Optional[str]:
        """태그의 Resonance 반환."""
    
    def get_all_tags(self) -> list[str]:
        """등록된 모든 태그명 반환."""
```

### A-5. 테스트: `tests/core/item/test_item_models.py`

```
테스트 항목:
1. ItemPrototype 생성 (frozen 확인 — 변경 시도 시 에러)
2. ItemInstance 생성 + 필드 변경 가능 확인
3. ItemType enum 값 확인
4. PrototypeRegistry.load_from_json — seed_items.json 로드, 60종 확인
5. PrototypeRegistry.get — 존재하는 ID
6. PrototypeRegistry.get — 존재하지 않는 ID → None
7. PrototypeRegistry.register — 동적 등록
8. PrototypeRegistry.search_by_tags — 단일 태그
9. PrototypeRegistry.search_by_tags — 다중 태그 (OR)
10. PrototypeRegistry.search_by_axiom — "Ferrum" 검색
11. AxiomTagMapping.load_from_json — 23종 로드
12. AxiomTagMapping.get — 존재하는 태그
13. AxiomTagMapping.get — 존재하지 않는 태그 → None
14. AxiomTagMapping.get_domain — 정상 반환
```

최소 14개 테스트 케이스.

## 검증
- `ruff check src/ tests/`
- `pytest tests/core/item/ -v`
- `pytest -v`

---

# #11-B: 인벤토리 + 내구도 + 거래 + 선물

## 목적
인벤토리 용량 계산, 내구도 처리, 거래가 계산, 흥정 판정, 선물 affinity 계산 — 모두 순수 Python Core 로직

## 참조 문서
- `docs/20_design/item-system.md` — 섹션 4(인벤토리), 섹션 6(거래), 섹션 7(선물), 섹션 9(내구도), 섹션 13(Constraints)

## 산출물

### B-1. `src/core/item/inventory.py`

item-system.md 섹션 4 기반.

```python
"""인벤토리 용량 관리"""
import logging

logger = logging.getLogger(__name__)

BASE_INVENTORY_CAPACITY = 50

def calculate_inventory_capacity(stats: dict[str, int]) -> int:
    """PC/NPC 공통. EXEC 기준 ±5.
    최소 30.
    """
    base = BASE_INVENTORY_CAPACITY
    base += (stats.get("EXEC", 2) - 2) * 5
    return max(30, base)

def calculate_current_bulk(items: list[tuple[int, ...]]) -> int:
    """아이템 목록의 bulk 합계.
    items: [(bulk, ...), ...] — 최소한 bulk 값만 있으면 됨.
    실제 구현에서는 ItemInstance + Prototype 조합으로 계산.
    """

def can_add_item(current_bulk: int, capacity: int, item_bulk: int) -> bool:
    """아이템 추가 가능 여부"""
    return current_bulk + item_bulk <= capacity
```

### B-2. `src/core/item/durability.py`

item-system.md 섹션 9 기반.

```python
"""내구도 시스템"""
import logging
from typing import Optional
from .models import ItemInstance, ItemPrototype

logger = logging.getLogger(__name__)

def apply_durability_loss(
    instance: ItemInstance,
    prototype: ItemPrototype,
) -> dict:
    """아이템 사용 시 내구도 감소.
    
    Returns:
        {
            "broken": bool,
            "new_durability": int,
            "broken_result": str | None  # 파괴 시 생성할 prototype_id
        }
    
    max_durability == 0: 파괴 불가, 변화 없음.
    current_durability <= 0 시:
        broken_result != None → 변환 아이템 생성 필요
        broken_result == None → 소멸
    """

def get_durability_ratio(instance: ItemInstance, prototype: ItemPrototype) -> float:
    """현재 내구도 비율 (0.0~1.0).
    max_durability == 0 이면 1.0 (파괴 불가).
    """
```

### B-3. `src/core/item/trade.py`

item-system.md 섹션 6 기반.

```python
"""거래 시스템 — 가격 계산 + 흥정 판정"""
import logging

logger = logging.getLogger(__name__)

RELATIONSHIP_DISCOUNT: dict[str, float] = {
    "stranger": 1.0,
    "acquaintance": 0.95,
    "friend": 0.85,
    "bonded": 0.75,
    "rival": 1.1,
    "nemesis": 1.3,
}

def calculate_trade_price(
    base_value: int,
    relationship_status: str,
    is_buying: bool,
    npc_hexaco_h: float,
    durability_ratio: float,
) -> int:
    """거래가 계산. 최소 1.
    
    is_buying=True: NPC 판매 (50% 마진)
    is_buying=False: NPC 구매 (50% 할인)
    관계 보정, HEXACO H 보정, 내구도 반영.
    """

def evaluate_haggle(
    proposed_price: int,
    calculated_price: int,
    relationship_status: str,
    npc_hexaco_a: float,
) -> str:
    """흥정 결과: "accept" | "counter" | "reject"
    
    A(관용성) 기반 threshold:
    - A >= 0.7: threshold 0.7
    - A >= 0.3: threshold 0.8
    - A < 0.3: threshold 0.9
    
    discount_ratio >= threshold → accept
    discount_ratio >= threshold - 0.15 → counter
    else → reject
    """

def calculate_counter_price(
    proposed_price: int,
    calculated_price: int,
) -> int:
    """counter 시 역제안 가격. 중간값."""
    return round((proposed_price + calculated_price) / 2)
```

### B-4. `src/core/item/gift.py`

item-system.md 섹션 7 기반.

```python
"""선물 시스템 — affinity 변동 계산"""
import logging

logger = logging.getLogger(__name__)

def calculate_gift_affinity(
    item_base_value: int,
    npc_desire_tags: list[str],
    item_tags: list[str],
) -> int:
    """선물에 의한 affinity 변동 계산.
    
    기본 +1 (선물 자체)
    + 가치 보정 (100+ → +2, 40+ → +1)
    + 욕구 매칭 (겹치는 태그 수)
    최대 5 (relationship_delta 클램핑).
    """
```

### B-5. `src/core/item/constraints.py`

item-system.md 섹션 13 기반.

```python
"""Constraints 빌드 — PC 보유 아이템 → 대화 시스템 Constraints"""
import logging
from .models import ItemPrototype, ItemInstance

logger = logging.getLogger(__name__)

def build_item_constraints(
    instances: list[ItemInstance],
    get_prototype: callable,  # item_id → ItemPrototype
) -> dict:
    """PC 보유 아이템에서 Constraints dict 생성.
    
    Returns:
        {
            "pc_items": ["wpn_rusty_sword", ...],
            "pc_axiom_powers": {"Ignis": 1, "Scindere": 2, ...}
        }
    
    get_prototype: Core는 DB를 모르므로, 호출자가 조회 함수를 주입.
    """
```

### B-6. 테스트: `tests/core/item/test_item_mechanics.py`

```
테스트 항목:
1. calculate_inventory_capacity — EXEC 보정, 최소 30
2. can_add_item — 가능/불가능
3. apply_durability_loss — 정상 감소
4. apply_durability_loss — 파괴 → broken_result 반환
5. apply_durability_loss — 파괴 → 소멸 (broken_result=None)
6. apply_durability_loss — 파괴 불가 (max_durability=0)
7. get_durability_ratio — 정상, 파괴 불가
8. calculate_trade_price — 구매/판매 기본
9. calculate_trade_price — 관계 보정 (friend vs nemesis)
10. calculate_trade_price — HEXACO H 보정
11. calculate_trade_price — 내구도 반영, 최소 1
12. evaluate_haggle — accept
13. evaluate_haggle — counter
14. evaluate_haggle — reject
15. calculate_counter_price — 중간값
16. calculate_gift_affinity — 기본, 가치 보정, 욕구 매칭, 최대 5
17. build_item_constraints — 정상 빌드
18. build_item_constraints — 빈 인벤토리
```

최소 18개 테스트 케이스.

## 검증
- `ruff check src/ tests/`
- `pytest tests/core/item/ -v`
- `pytest -v`

---

# #11-C: Item Service (DB + EventBus)

## 목적
아이템 CRUD, Prototype 로드, 소유권 이전, 내구도 처리의 DB 영속화 + EventBus 통신

## 참조 문서
- `docs/20_design/item-system.md` — 섹션 5(점포), 섹션 10(EventBus), 섹션 11(DB)
- `docs/30_technical/db-schema-v2.md` — item_prototypes, item_instances 테이블
- `src/db/models_v2.py` — ItemPrototypeModel, ItemInstanceModel 확인
- `src/services/npc_service.py` — 참고: Service 패턴

## 산출물

### C-1. `src/services/item_service.py` (신규)

```python
"""아이템 Service — Core↔DB 연결, EventBus 통신"""
import logging
import uuid
from sqlalchemy.orm import Session

from src.core.item.models import ItemPrototype, ItemInstance, ItemType
from src.core.item.registry import PrototypeRegistry
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.inventory import calculate_inventory_capacity, can_add_item
from src.core.item.durability import apply_durability_loss, get_durability_ratio
from src.core.item.trade import calculate_trade_price, evaluate_haggle, calculate_counter_price
from src.core.item.gift import calculate_gift_affinity
from src.core.item.constraints import build_item_constraints
from src.core.event_bus import EventBus
from src.core.event_types import EventTypes
from src.db.models_v2 import ItemPrototypeModel, ItemInstanceModel

logger = logging.getLogger(__name__)

class ItemService:
    """아이템 CRUD + 비즈니스 로직"""

    def __init__(
        self,
        db: Session,
        event_bus: EventBus,
        registry: PrototypeRegistry,
        axiom_mapping: AxiomTagMapping,
    ):
        self._db = db
        self._bus = event_bus
        self._registry = registry
        self._axiom_mapping = axiom_mapping
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독"""
        self._bus.subscribe(EventTypes.DIALOGUE_ENDED, self._on_dialogue_ended)
        # npc_created, quest_completed, turn_processed는 해당 모듈 구현 시 추가

    # === Prototype 관리 ===

    def get_prototype(self, item_id: str) -> ItemPrototype | None:
        """Registry에서 조회."""
        return self._registry.get(item_id)

    def sync_prototypes_to_db(self) -> int:
        """Registry → DB 동기화. 서버 시작 시 호출.
        seed_items.json의 정적 데이터를 DB에도 저장.
        반환: 동기화된 수량.
        """

    # === Instance CRUD ===

    def create_instance(
        self,
        prototype_id: str,
        owner_type: str,
        owner_id: str,
        current_durability: int | None = None,
        acquired_turn: int = 0,
    ) -> ItemInstance:
        """아이템 인스턴스 생성 + DB 저장.
        current_durability 미지정 시 prototype.max_durability 사용.
        item_created 이벤트 발행.
        """

    def get_instance(self, instance_id: str) -> ItemInstance | None:
        """인스턴스 조회."""

    def get_instances_by_owner(
        self, owner_type: str, owner_id: str
    ) -> list[ItemInstance]:
        """소유자별 인스턴스 목록."""

    def count_instances(
        self, owner_type: str, owner_id: str, prototype_id: str | None = None
    ) -> int:
        """소유자별 아이템 수 (prototype 필터 선택)."""

    # === 소유권 이전 ===

    def transfer_item(
        self,
        instance_id: str,
        to_type: str,
        to_id: str,
        reason: str = "manual",
    ) -> bool:
        """아이템 소유권 이전.
        item_transferred 이벤트 발행.
        반환: 성공 여부.
        """

    # === 내구도 ===

    def use_item(self, instance_id: str) -> dict:
        """아이템 사용 → 내구도 감소.
        파괴 시 broken_result 아이템 자동 생성.
        item_broken 이벤트 발행 (파괴 시).
        
        Returns: apply_durability_loss 결과 dict
        """

    # === 거래 ===

    def calculate_price(
        self,
        instance_id: str,
        relationship_status: str,
        is_buying: bool,
        npc_hexaco_h: float,
    ) -> int:
        """거래가 계산. 내구도 자동 반영."""

    def process_haggle(
        self,
        proposed_price: int,
        calculated_price: int,
        relationship_status: str,
        npc_hexaco_a: float,
    ) -> dict:
        """흥정 처리. Returns: {"result": str, "counter_price": int|None}"""

    def execute_trade(
        self,
        instance_id: str,
        buyer_type: str,
        buyer_id: str,
        seller_type: str,
        seller_id: str,
        price: int,
    ) -> bool:
        """거래 실행 — 아이템 이전 + 통화 처리.
        통화는 Player/NPC의 currency 필드 (DB 직접 갱신).
        잔고 부족 시 False 반환.
        """

    # === 선물 ===

    def process_gift(
        self,
        instance_id: str,
        from_type: str,
        from_id: str,
        to_npc_id: str,
        npc_desire_tags: list[str],
    ) -> dict:
        """선물 처리.
        Returns: {"affinity_delta": int, "transferred": bool}
        """

    # === Constraints ===

    def get_item_constraints(self, player_id: str) -> dict:
        """PC 보유 아이템 → Constraints dict.
        build_item_constraints()에 get_prototype 주입.
        """

    # === 인벤토리 ===

    def get_inventory_bulk(self, owner_type: str, owner_id: str) -> int:
        """소유자의 현재 bulk 합계."""

    def get_inventory_capacity(self, owner_type: str, owner_id: str, stats: dict[str, int]) -> int:
        """소유자의 인벤토리 용량."""

    def can_add_to_inventory(
        self, owner_type: str, owner_id: str, prototype_id: str, stats: dict[str, int]
    ) -> bool:
        """아이템 추가 가능 여부."""

    # === EventBus 핸들러 ===

    def _on_dialogue_ended(self, event) -> None:
        """대화 종료 시 거래/선물 아이템 이동 처리.
        event.data에 trade_request, gift_offered가 있으면 처리.
        Alpha에서는 예비 구현 — 실제 데이터 흐름은 dialogue_service가 전달.
        """

    # === ORM ↔ Core 변환 ===

    def _instance_to_core(self, orm: ItemInstanceModel) -> ItemInstance:
        """ORM → Core"""

    def _instance_to_orm(self, core: ItemInstance) -> ItemInstanceModel:
        """Core → ORM"""

    def _prototype_to_orm(self, core: ItemPrototype) -> ItemPrototypeModel:
        """Core → ORM (sync용)"""
```

### C-2. 테스트: `tests/services/test_item_service.py`

```
테스트 항목:
1. create_instance — 정상 생성 + DB 저장
2. create_instance — item_created 이벤트 발행
3. get_instance — 존재/미존재
4. get_instances_by_owner — 복수 아이템
5. transfer_item — 소유권 이전 + 이벤트
6. use_item — 내구도 감소
7. use_item — 파괴 → broken_result 아이템 생성
8. use_item — 파괴 불가 아이템
9. calculate_price — 정상 계산
10. process_haggle — accept/counter/reject
11. execute_trade — 정상 거래 (통화 차감/증가)
12. execute_trade — 잔고 부족 → False
13. process_gift — 정상 선물 + affinity 계산
14. get_item_constraints — 정상 빌드
15. sync_prototypes_to_db — 60종 동기화
16. get_inventory_bulk — 합계 계산
17. can_add_to_inventory — 가능/불가능
```

최소 17개 테스트 케이스. in-memory SQLite + seed_items.json 로드.

## 검증
- `ruff check src/ tests/`
- `pytest tests/services/test_item_service.py -v`
- `pytest -v`

---

# #11-D: ItemModule 래핑 + API + 임시 자동보충

## 목적
ItemService를 GameModule로 래핑, API 엔드포인트 추가, 임시 자동보충 시스템 구현

## 참조 문서
- `docs/20_design/item-system.md` — 섹션 1.3(모듈 위치), 섹션 5(점포, 자동보충), 섹션 10(EventBus)
- `src/modules/npc/module.py` — 참고: 모듈 래핑 패턴
- `src/api/game.py` — 기존 API 라우터

## 산출물

### D-1. `src/core/item/restock.py`

item-system.md 섹션 5.4 기반. **임시 자동보충 시스템**.

```python
"""TEMPORARY: Phase B 자율행동 구현 시 제거.
상인 NPC의 선반/인벤토리 자동 보충.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ShopRestockConfig:
    """상인 NPC별 자동 보충 설정"""
    npc_id: str
    shelf_instance_id: str
    stock_template: list[str] = field(default_factory=list)  # prototype_id 목록
    restock_cooldown: int = 5           # N턴마다 보충
    max_stock_per_item: int = 3

def check_restock_needed(config: ShopRestockConfig, current_turn: int) -> bool:
    """보충 필요 여부 판정."""
    return current_turn % config.restock_cooldown == 0

def calculate_restock_deficit(
    config: ShopRestockConfig,
    current_stock: dict[str, int],  # {prototype_id: count}
) -> dict[str, int]:
    """보충 필요 수량 계산. Returns: {prototype_id: deficit}"""
```

코드 전체에 `# TEMPORARY: Phase B 자율행동 구현 시 제거` 주석을 명시할 것.

### D-2. `src/modules/item/__init__.py`

패키지 초기화.

### D-3. `src/modules/item/module.py`

```python
"""ItemModule — GameModule 인터페이스"""
import logging
from src.modules.base import GameModule, GameContext, Action
from src.services.item_service import ItemService
from src.core.item.restock import ShopRestockConfig, check_restock_needed

logger = logging.getLogger(__name__)

class ItemModule(GameModule):
    name = "item"
    dependencies = []  # Layer 1 기반 모듈

    def __init__(self, item_service: ItemService):
        self._service = item_service
        self._restock_configs: list[ShopRestockConfig] = []

    def register_restock_config(self, config: ShopRestockConfig) -> None:
        """상인 NPC 보충 설정 등록. TEMPORARY."""
        self._restock_configs.append(config)

    def on_enable(self, event_bus) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        """턴 처리: 임시 자동보충 실행 (TEMPORARY)."""
        for config in self._restock_configs:
            if check_restock_needed(config, context.current_turn):
                self._execute_restock(config)

    def _execute_restock(self, config: ShopRestockConfig) -> None:
        """보충 실행. TEMPORARY."""

    def on_node_enter(self, context: GameContext) -> None:
        """노드 진입 시 바닥 아이템 정보를 context.extra에 추가."""
        node_items = self._service.get_instances_by_owner("node", context.current_node_id)
        context.extra["item"] = {
            "node_items": [
                {"instance_id": i.instance_id, "prototype_id": i.prototype_id}
                for i in node_items
            ],
        }

    def get_available_actions(self, context: GameContext) -> list[Action]:
        """아이템 관련 액션 반환."""
        actions = [
            Action(name="inventory", display_name="Inventory",
                   module_name="item", description="인벤토리 확인"),
            Action(name="pickup", display_name="Pick Up",
                   module_name="item", description="바닥 아이템 줍기",
                   params={"instance_id": "str"}),
            Action(name="drop", display_name="Drop",
                   module_name="item", description="아이템 버리기",
                   params={"instance_id": "str"}),
            Action(name="use", display_name="Use",
                   module_name="item", description="아이템 사용",
                   params={"instance_id": "str"}),
            Action(name="browse", display_name="Browse",
                   module_name="item", description="상점 선반 둘러보기",
                   params={"container_id": "str"}),
        ]
        return actions
```

### D-4. `src/api/game.py` 확장

기존 액션 디스패치에 아이템 관련 액션 추가:

- **inventory**: `GET`-like — PC 인벤토리 목록 반환
- **pickup**: 바닥 아이템 → PC 인벤토리 (용량 확인)
- **drop**: PC 인벤토리 → 바닥 (현재 노드)
- **use**: 아이템 사용 → 내구도 감소 + 파괴 처리
- **browse**: container 내 아이템 목록 반환

기존 game.py의 액션 디스패치 패턴을 따를 것.

### D-5. `src/main.py` 수정

lifespan에서 PrototypeRegistry, AxiomTagMapping, ItemService, ItemModule 초기화.

```python
# 서버 시작 시:
registry = PrototypeRegistry()
registry.load_from_json("src/data/seed_items.json")

axiom_mapping = AxiomTagMapping()
axiom_mapping.load_from_json("src/data/axiom_tag_mapping.json")

item_service = ItemService(
    db=session,
    event_bus=module_manager.event_bus,
    registry=registry,
    axiom_mapping=axiom_mapping,
)
item_service.sync_prototypes_to_db()

item_module = ItemModule(item_service)
module_manager.register(item_module)
module_manager.enable("item")
```

### D-6. SRC_INDEX.md 최종 갱신

#11 시리즈에서 추가/수정된 모든 파일 반영:

```
# 추가:
core/item/__init__.py
core/item/models.py
core/item/registry.py
core/item/axiom_mapping.py
core/item/inventory.py
core/item/durability.py
core/item/trade.py
core/item/gift.py
core/item/constraints.py
core/item/restock.py          # TEMPORARY
services/item_service.py
modules/item/__init__.py
modules/item/module.py
data/seed_items.json           # 60종
data/axiom_tag_mapping.json    # 23 태그

# 수정:
core/event_types.py (아이템 이벤트 추가)
api/game.py (inventory/pickup/drop/use/browse 액션)
main.py (ItemService/Module 초기화)
```

의존 흐름 요약 추가:
```
modules/item/module.py → services/item_service.py → core/item/* + db/models_v2.py
```

### D-7. 테스트: `tests/modules/item/test_item_module.py`

```
테스트 항목:
1. ItemModule 생성 + dependencies 확인
2. get_available_actions — 5개 액션
3. on_node_enter — context.extra["item"] 설정
4. on_turn — 자동보충 (TEMPORARY)
5. ShopRestockConfig + check_restock_needed
6. calculate_restock_deficit
```

### D-8. 테스트: `tests/api/test_item_api.py`

```
테스트 항목:
1. inventory 액션 — PC 인벤토리 반환
2. pickup 액션 — 바닥 → PC
3. pickup 액션 — 용량 초과 → 에러
4. drop 액션 — PC → 바닥
5. use 액션 — 내구도 감소
6. use 액션 — 파괴
7. browse 액션 — container 목록 반환
```

최소 7개 API 테스트. TestClient + in-memory SQLite + MockProvider.

## 검증
- `ruff check src/ tests/`
- `pytest -v` (전체 테스트 통과)
- `pytest --cov` (커버리지 70%+)

---

# 블록 실행 요약

| 순서 | 블록 | 핵심 산출물 | 예상 테스트 수 |
|------|------|------------|--------------|
| 1 | #11-0 | 데이터 배치, event_types 갱신 | 0 (기존 통과) |
| 2 | #11-A | core/item/ (models, registry, axiom_mapping) | 14+ |
| 3 | #11-B | core/item/ (inventory, durability, trade, gift, constraints) | 18+ |
| 4 | #11-C | services/item_service.py | 17+ |
| 5 | #11-D | modules/item/, API, restock, main.py, SRC_INDEX | 13+ |
| **합계** | | | **62+** |

투입 순서: **0 → A → B → C → D**. 각 블록 완료 후 `pytest -v` 통과 확인 후 다음 진행.

**⚠️ 주의**: #11-0 실행 시 seed_items.json, axiom_tag_mapping.json, 수정된 item-system.md를 함께 Claude Code에 첨부할 것.
