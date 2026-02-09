# ITW 아이템 시스템 설계서

**버전**: 1.0  
**작성일**: 2026-02-10  
**상태**: 확정  
**관련**: dialogue-system.md, quest-system.md, relationship-system.md, npc-system.md, axiom-system.md

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 아이템 시스템을 정의한다. 아이템은 게임 경제의 매개체이자, NPC 거래·선물·퀘스트 보상·공리 활용의 물리적 기반이다.

### 1.2 핵심 원칙

- **Prototype + Instance 분리**: 불변 원형(Prototype)과 가변 개체(Instance)를 분리
- **데이터 드리븐**: 아이템 추가는 JSON 데이터 추가만으로 완료, 코드 변경 불필요
- **확장성 최우선**: 초기 43종에서 수백~수천 종으로 확장 가능한 구조. 공리 조합 생성 아이템(동적 Prototype)도 수용 가능할 것
- **공리 연동**: 아이템의 힘은 자유 태그(axiom_tags)로 표현, 매핑 테이블로 214 Divine Axioms에 연결
- **Hybrid Architecture**: 거래 판정·인벤토리 관리·내구도는 Python, 서술·흥정 연기는 LLM

### 1.3 모듈 위치

- **Layer**: 1 (기반 모듈, npc/geography와 동급)
- **의존성**: axiom_system (매핑 테이블 참조)
- **위치**: `src/modules/item/`

### 1.4 Gemini 기획 대비 변경 사항

| Gemini 기획 | ITW 설계 | 이유 |
|------------|---------|------|
| EntropyData (absorb/repel/emit/propagation) | max_durability + broken_result만 유지 | 물리 엔진 수준의 복잡성은 Phase 2에서 과도 |
| potency_tags (자체 태그 체계) | axiom_tags + 매핑 테이블 | 기존 214 Axiom 시스템과 통합 |
| Pydantic BaseModel | @dataclass | Core 레이어 기존 패턴 |
| src/data/seed_items.py (Python) | src/data/seed_items.json (JSON) | 정적 데이터는 JSON 패턴 |
| Environment 카테고리 (10종) | 제거 | 환경물은 MapNode/오버레이에서 처리 |
| 5종 분류 | 4종 분류 (단순화) | EQUIPMENT/CONSUMABLE/MATERIAL/MISC |
| Garbage Collection / Decay Cycle | 제거 | simulation-scope.md의 Zone 처리 원칙과 충돌 |

---

## 2. 데이터 모델

### 2.1 ItemPrototype (원형 — 불변)

서버 시작 시 `src/data/seed_items.json`에서 로드, 메모리 캐싱. 런타임 불변.

```python
class ItemType(str, Enum):
    EQUIPMENT = "equipment"     # 장비 (무기/방어구/도구)
    CONSUMABLE = "consumable"   # 소모품 (약초, 붕대, 음식)
    MATERIAL = "material"       # 원자재/제작 재료
    MISC = "misc"               # 기타 (용기, 정보, 제작 설비)

@dataclass(frozen=True)
class ItemPrototype:
    """
    아이템 원형. seed_items.json에서 로드.
    확장: 공리 조합 생성 시 동적 Prototype을 런타임에 등록할 수 있다.
    """
    item_id: str                    # "wpn_rusty_sword"
    name_kr: str                    # "녹슨 철검"
    item_type: ItemType

    # 물리
    weight: float                   # kg (이동/피로 시스템 연동 예정)
    bulk: int                       # 1~10, 인벤토리 슬롯 점유
    base_value: int                 # 기본 거래가

    # 재질 & 공리 연동
    primary_material: str           # "Iron", "Wood", "Cloth", ...
    axiom_tags: dict[str, int]      # 자유 태그 + 강도 {"Ignis": 1, "Lux": 2}
                                    # 매핑 테이블로 Divine Axiom에 연결

    # 내구도
    max_durability: int             # 최대 내구도 (0 = 파괴 불가)
    durability_loss_per_use: int    # 사용당 감소량
    broken_result: Optional[str]    # 파괴 시 변환 아이템 ID (None = 소멸)

    # 용기 기능
    container_capacity: int = 0     # 0 = 용기 아님, 1+ = 담을 수 있는 bulk 합계

    # 서술 & 검색
    flavor_text: str = ""           # AI 묘사 힌트
    tags: list[str] = field(default_factory=list)  # 검색/필터용 ["flammable", "fragile"]
```

### 2.2 ItemInstance (개별체 — 가변)

게임 내 실제 존재하는 아이템 개체. DB에 저장.

```python
@dataclass
class ItemInstance:
    """게임 내 아이템 개체. Prototype의 Delta(변화값)만 저장."""
    instance_id: str                # UUID
    prototype_id: str               # ItemPrototype.item_id 참조

    # 위치 (택 1)
    owner_type: str                 # "player" | "npc" | "node" | "container"
    owner_id: str                   # player_id, npc_id, node_id, 또는 부모 instance_id

    # 상태
    current_durability: int         # 현재 내구도
    state_tags: list[str] = field(default_factory=list)  # ["wet", "rusty"]

    # 메타
    acquired_turn: int = 0          # 획득 턴
    custom_name: Optional[str] = None  # PC/NPC가 이름 붙인 경우
```

### 2.3 위치 모델

아이템의 위치를 `owner_type + owner_id` 조합으로 통일한다:

| owner_type | owner_id | 의미 | 예시 |
|-----------|---------|------|------|
| `"player"` | player_id | PC 인벤토리 | PC가 들고 있는 철검 |
| `"npc"` | npc_id | NPC 소유 | 대장장이가 판매용으로 보유 |
| `"node"` | node_id | 바닥/환경에 놓임 | 던전 바닥의 보물 |
| `"container"` | instance_id | 다른 아이템(용기) 안 | 나무상자 안의 약초 |

container 체이닝 예시 (점포 구조):

```
# 가게 선반 (노드에 배치된 container)
ItemInstance(prototype_id="misc_shop_shelf", owner_type="node", owner_id="3_5")

# 선반 위의 철검
ItemInstance(prototype_id="wpn_rusty_sword", owner_type="container", owner_id="shelf_instance_01")

# 창고 상자 (서브그리드 노드에 배치)
ItemInstance(prototype_id="misc_wooden_box", owner_type="node", owner_id="3_5_sub_0_0_-1")
```

### 2.4 Prototype Registry (확장성 핵심)

```python
class PrototypeRegistry:
    """
    아이템 원형 저장소. 초기 데이터(JSON) + 동적 생성 Prototype을 모두 관리.
    수백~수천 종 스케일에 대응.
    """
    _prototypes: dict[str, ItemPrototype]  # item_id → Prototype

    def load_from_json(self, path: str) -> None:
        """서버 시작 시 seed_items.json 로드"""
        ...

    def register(self, prototype: ItemPrototype) -> None:
        """동적 Prototype 등록 (공리 조합 생성 등)"""
        ...

    def get(self, item_id: str) -> Optional[ItemPrototype]:
        """O(1) 조회"""
        ...

    def search_by_tags(self, tags: list[str]) -> list[ItemPrototype]:
        """태그 기반 검색 (NPC 욕구 매칭, 상점 필터 등)"""
        ...

    def search_by_axiom(self, axiom_tag: str) -> list[ItemPrototype]:
        """공리 태그 기반 검색"""
        ...
```

동적 Prototype은 공리 조합으로 새로운 아이템을 생성할 때 사용한다. 예: PC가 "거미줄 + 뼈 단검"을 조합해서 새로운 무기를 만들면, 런타임에 Prototype이 등록되고 해당 플레이 세션에서 유효하다. 상세 조합 규칙은 추후 설계.

---

## 3. Axiom 태그 매핑

### 3.1 구조

아이템의 axiom_tags는 자유 태그(가독성)이고, 매핑 테이블을 통해 214 Divine Axioms에 연결된다.

```json
// src/data/axiom_tag_mapping.json
{
  "Ignis": {
    "domain": "Force",
    "resonance": "Destruction",
    "axiom_ids": ["AXM_042", "AXM_043"],
    "description": "화염, 연소, 열"
  },
  "Scindere": {
    "domain": "Force",
    "resonance": "Destruction",
    "axiom_ids": ["AXM_045"],
    "description": "베기, 절단"
  },
  "Aqua": {
    "domain": "Primordial",
    "resonance": "Creation",
    "axiom_ids": ["AXM_012"],
    "description": "물, 액체, 습기"
  },
  "Cura": {
    "domain": "Organic",
    "resonance": "Creation",
    "axiom_ids": ["AXM_098"],
    "description": "치유, 회복"
  }
  // ... 30~40종
}
```

### 3.2 활용

- **Constraints 연동**: PC가 "화염 공리로 공격"하면, 보유 아이템의 axiom_tags에 "Ignis"가 있는지 확인
- **공리 역학**: 아이템 간 Domain 매칭 (같은 Domain = amplify, 같은 Resonance = resist)
- **NPC 욕구 매칭**: 대장장이가 "Ferrum" 태그 아이템을 원함

### 3.3 확장 원칙

- 신규 아이템 추가 시 기존 태그 재사용 우선
- 신규 태그 필요 시 매핑 테이블에 1줄 추가
- 매핑 테이블은 단방향 (태그 → Axiom), 역방향 조회는 PrototypeRegistry.search_by_axiom()

---

## 4. 인벤토리 시스템

### 4.1 용량 계산

PC와 NPC는 동일한 인벤토리 시스템을 사용한다.

```python
BASE_INVENTORY_CAPACITY = 50  # bulk 합계 기본값

def calculate_inventory_capacity(stats: dict[str, int]) -> int:
    """PC/NPC 공통. 능력치에 따라 증감."""
    base = BASE_INVENTORY_CAPACITY
    # EXEC(실행력)이 운반력과 가장 가까움
    base += (stats.get("EXEC", 2) - 2) * 5  # EXEC 2 기준, 1당 ±5
    return max(30, base)  # 최소 30
```

### 4.2 인벤토리 조회

```python
def get_inventory_bulk(owner_type: str, owner_id: str) -> int:
    """현재 소유 아이템의 bulk 합계"""
    instances = query_items(owner_type=owner_type, owner_id=owner_id)
    return sum(get_prototype(i.prototype_id).bulk for i in instances)

def can_add_item(owner_type: str, owner_id: str, prototype: ItemPrototype) -> bool:
    """아이템 추가 가능 여부"""
    current_bulk = get_inventory_bulk(owner_type, owner_id)
    capacity = calculate_inventory_capacity(get_stats(owner_type, owner_id))
    return current_bulk + prototype.bulk <= capacity
```

### 4.3 weight 필드

weight는 데이터에 포함하되, 이동/피로 시스템이 미설계이므로 로직 연동은 추후로 미룬다. 데이터만 확보해두면 나중에 로직을 붙이기 쉽다.

---

## 5. 점포 구조

### 5.1 물건의 흐름

```
[생산자 NPC] ──구매──→ [창고(서브그리드)] ──진열──→ [선반(노드 container)] ──휴대──→ [가게 주인 인벤토리]
                          (대형 점포만)           (PC 열람 가능)              (실제 거래 시 여기서 전달)
```

### 5.2 데이터 표현

모든 구조가 ItemInstance의 owner_type/owner_id로 표현된다:

```
# 가게 선반 = 노드에 배치된 대용량 container
ItemInstance(
    prototype_id="misc_shop_shelf",     # container_capacity: 30 등
    owner_type="node",
    owner_id="3_5"
)

# 선반 위의 상품
ItemInstance(
    prototype_id="wpn_rusty_sword",
    owner_type="container",
    owner_id="{shelf_instance_id}"
)

# 창고 = 서브그리드 노드의 container
ItemInstance(
    prototype_id="misc_warehouse_shelf",
    owner_type="node",
    owner_id="3_5_sub_0_0_-1"          # 서브그리드 좌표
)
```

### 5.3 구매 흐름

#### 경로 A: browse → 선택 → 거래 대화

```
[대화 밖]
PC: "browse" 또는 "look shelf"
  → Python: 선반 container의 아이템 목록 조회
  → narrative_service: "철검과 목검이 진열되어 있다. 무언가 사겠는가?"

PC: "철검" (아이템 선택)
  → Python: 해당 아이템 + NPC 정보로 거래 대화 세션 자동 시작
  → 거래용 짧은 budget (2~3턴)

[대화 진입 — 거래 모드]
NPC: "철검 살 건가? 꽤 좋은 물건이지, 안그래? 30 동전이야."
PC: "산다" → 거래 완료, 선반 → PC 인벤토리
PC: "깎아줘" → 흥정 1~2턴 → 합의/거절
```

#### 경로 B: 일반 대화 중 거래

```
PC: "talk hans"
  → 일반 대화 진행 (budget 6턴 등)

PC: "그 철검 사고 싶은데"
  → LLM META에 trade_request 발생
  → 기존 대화 흐름 안에서 거래 처리
```

#### 두 경로의 차이

| | 경로 A (browse) | 경로 B (talk 중) |
|--|----------------|----------------|
| 진입 | browse → 아이템 선택 | talk 중 자연 발생 |
| budget | 짧은 고정 (2~3턴) | 일반 대화 budget 내 |
| 시드 판정 | 없음 | 일반 대화이므로 5% 판정 |
| 컨텍스트 | 거래 특화 | 전체 NPC 컨텍스트 |

### 5.4 재고 보충

#### 최종 목표 (Phase B 자율행동 구현 후)

NPC 자율행동 Phase B의 "재고 관리" 욕구로 처리한다:

```
거래 완료 → 선반에서 아이템 빠짐
  → NPC 자율행동 턴:
    ├─ 선반 빈 슬롯 확인
    ├─ 본인 인벤토리에 해당 품목 → 선반으로 이동
    ├─ 본인 인벤토리에도 없음 → 창고에서 가져옴
    └─ 창고에도 없음 → 생산자 NPC에게 구매 (NPC간 거래)
```

#### 임시 자동 보충 시스템 (Phase B 미구현 시)

> **⚠ TEMPORARY**: NPC 자율행동 Phase B 구현 시 이 시스템을 제거하고 욕구 기반 재고 관리로 교체할 것.

Phase B가 없는 동안, 턴 처리 시 상인 NPC의 선반과 인벤토리를 자동으로 보충한다.

```python
# --- TEMPORARY: Phase B 자율행동 구현 시 제거 ---

@dataclass
class ShopRestockConfig:
    """상인 NPC별 자동 보충 설정"""
    npc_id: str
    shelf_instance_id: str              # 선반 container의 instance_id
    stock_template: list[str]           # 보충할 prototype_id 목록
    restock_cooldown: int = 5           # N턴마다 보충
    max_stock_per_item: int = 3         # 아이템당 최대 재고

def auto_restock(config: ShopRestockConfig, current_turn: int) -> None:
    """
    턴 처리 시 호출. 선반과 NPC 인벤토리를 template 기준으로 보충.
    TEMPORARY: Phase B 구현 후 제거.
    """
    if current_turn % config.restock_cooldown != 0:
        return

    for proto_id in config.stock_template:
        # 선반 재고 확인
        shelf_count = count_items(
            owner_type="container",
            owner_id=config.shelf_instance_id,
            prototype_id=proto_id,
        )
        # 부족분 생성 (선반에 직접 배치)
        deficit = config.max_stock_per_item - shelf_count
        for _ in range(deficit):
            create_item_instance(
                prototype_id=proto_id,
                owner_type="container",
                owner_id=config.shelf_instance_id,
            )

    # NPC 인벤토리도 동일하게 보충 (휴대 판매분)
    for proto_id in config.stock_template:
        npc_count = count_items(
            owner_type="npc",
            owner_id=config.npc_id,
            prototype_id=proto_id,
        )
        deficit = max(1, config.max_stock_per_item // 2) - npc_count
        for _ in range(deficit):
            create_item_instance(
                prototype_id=proto_id,
                owner_type="npc",
                owner_id=config.npc_id,
            )

# --- END TEMPORARY ---
```

임시 시스템의 특징:
- **turn_processed 이벤트 구독**: N턴마다 자동 실행
- **template 기반**: 상인별로 판매 품목을 ShopRestockConfig에 정의
- **허공에서 생성**: 생산자 NPC 구매 과정 없이 즉시 생성 (임시)
- **Phase B 교체 시**: ShopRestockConfig 제거, 대신 NPC 욕구 "재고 관리"가 창고→선반→인벤토리 흐름을 담당

---

## 6. 거래 시스템

### 6.1 통화

통화는 아이템이 아닌 Player/NPC의 수치 속성으로 관리한다.

```python
# Player.currency: int = 0
# NPC.currency: int = 500
```

아이템으로 통화를 만들면 bulk 계산·인벤토리 점유 등 불필요한 복잡성이 생긴다.

### 6.2 거래가 계산

```python
RELATIONSHIP_DISCOUNT = {
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
    """거래가 계산. PC/NPC 공통."""
    # 기본 마진
    if is_buying:
        price = base_value * 1.5    # NPC 판매: 50% 마진
    else:
        price = base_value * 0.5    # NPC 구매: 50% 할인

    # 관계 보정
    price *= RELATIONSHIP_DISCOUNT.get(relationship_status, 1.0)

    # HEXACO H(정직성) 보정
    if npc_hexaco_h <= 0.3:
        price *= 1.2    # 실리적 NPC = 비싸게
    elif npc_hexaco_h >= 0.7:
        price *= 0.9    # 정직한 NPC = 약간 할인

    # 내구도 반영
    price *= max(0.3, durability_ratio)  # 최소 30%

    return max(1, round(price))
```

### 6.3 흥정 판정

PC가 흥정을 시도하면 Python이 수락 여부를 판정한다:

```python
def evaluate_haggle(
    proposed_price: int,
    calculated_price: int,
    relationship_status: str,
    npc_hexaco_a: float,
) -> str:
    """흥정 결과: "accept" | "counter" | "reject" """
    discount_ratio = proposed_price / calculated_price

    # A(관용성) 높으면 양보 잘 함
    threshold = 0.7 if npc_hexaco_a >= 0.7 else 0.8 if npc_hexaco_a >= 0.3 else 0.9

    if discount_ratio >= threshold:
        return "accept"
    elif discount_ratio >= threshold - 0.15:
        return "counter"    # 중간 가격 역제안
    else:
        return "reject"
```

### 6.4 META 확장: trade_request

dialogue-system.md의 META JSON에 선택적 필드로 추가:

```json
{
  "meta": {
    "trade_request": {
      "action": "buy",
      "item_instance_id": "shelf_sword_01",
      "proposed_price": null,
      "final_price": 30
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | str | "buy" \| "sell" \| "negotiate" \| "confirm" \| "reject" |
| `item_instance_id` | str | 거래 대상 아이템 |
| `proposed_price` | int \| null | PC/NPC 제안가 |
| `final_price` | int \| null | 최종 합의가 (confirm 시) |

Python 검증: action이 허용 값인지, 아이템이 실제 존재하는지, 통화 잔고 충분한지 확인.

---

## 7. 선물과 관계 변동

### 7.1 선물 affinity 계산

```python
def calculate_gift_affinity(
    item_base_value: int,
    npc_desire_tags: list[str],
    item_tags: list[str],
) -> int:
    """선물에 의한 affinity 변동 계산"""
    base = 1  # 선물 자체로 +1

    # 가치 보정
    if item_base_value >= 100:
        base += 2
    elif item_base_value >= 40:
        base += 1

    # 욕구 매칭 보너스
    matching = set(npc_desire_tags) & set(item_tags)
    if matching:
        base += len(matching)

    return min(base, 5)  # relationship_delta 클램핑
```

### 7.2 대화 시스템 연동

선물은 대화 중에 이루어진다. dialogue-system의 META에 gift 필드 추가:

```json
{
  "meta": {
    "gift_offered": {
      "item_instance_id": "herb_01",
      "npc_reaction": "grateful"
    }
  }
}
```

Python이 calculate_gift_affinity()로 relationship_delta를 계산하고, 세션 종료 시 일괄 적용.

---

## 8. 퀘스트 보상

### 8.1 아이템 보상 구조

quest-system.md의 보상 유형 중 하나:

```python
@dataclass
class ItemReward:
    prototype_id: str               # 아이템 원형 ID
    durability_ratio: float = 1.0   # 0.0~1.0, 상태
    custom_name: Optional[str] = None  # "한스의 감사 선물"
```

### 8.2 전달 방식

- NPC가 직접 건네는 경우: 대화 중 META에 포함, 거래와 유사하지만 무료
- 환경에서 획득: 퀘스트 완료 시 특정 노드에 아이템 배치

---

## 9. 내구도 시스템

### 9.1 단순 모델

```
아이템 사용 → current_durability -= durability_loss_per_use
  ├─ current_durability > 0 → 정상
  └─ current_durability <= 0 → 파괴
        ├─ broken_result != null → 변환 아이템 생성
        └─ broken_result == null → 소멸
```

### 9.2 파괴 결과물

파괴 시 broken_result가 기존 Prototype ID를 참조:

| 파괴 아이템 | broken_result | 결과 |
|-----------|--------------|------|
| 녹슨 철검 | mat_iron_scrap | 고철 조각 |
| 삼베 로프 | item_ash | 재 |
| 나무 원형 방패 | item_broken_wood | 부러진 나무 |
| 말린 약초 | item_rotten_remains | 썩은 잔해 |
| 붕대 | null | 소멸 |

파괴 결과물 Prototype (3종 추가):

| ID | 이름 | 타입 | base_value |
|----|------|------|-----------|
| item_ash | 재 | MATERIAL | 1 |
| item_broken_wood | 부러진 나무 | MATERIAL | 2 |
| item_rotten_remains | 썩은 잔해 | MATERIAL | 0 |

### 9.3 max_durability = 0

파괴 불가 아이템: 부싯돌, 쇠지렛대 등. 사용해도 내구도가 줄지 않는다.

---

## 10. EventBus 인터페이스

### 10.1 item 모듈이 발행하는 이벤트

| 이벤트 | 데이터 | 구독 예상 |
|--------|--------|----------|
| `item_transferred` | `{instance_id, from_type, from_id, to_type, to_id, reason}` | relationship (선물 시), quest (보상 확인) |
| `item_broken` | `{instance_id, prototype_id, owner_type, owner_id, broken_result}` | narrative (파괴 서술) |
| `item_created` | `{instance_id, prototype_id, owner_type, owner_id, source}` | quest (보상 지급), npc (인벤토리 갱신) |

### 10.2 item 모듈이 구독하는 이벤트

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `dialogue_ended` | dialogue | 거래/선물 아이템 이동 |
| `quest_completed` | quest | 보상 아이템 생성 |
| `npc_created` | npc | 직업별 초기 인벤토리 생성 |
| `turn_processed` | engine | 내구도 자연 감쇠 (해당 시) |

---

## 11. DB 테이블

### 11.1 item_prototypes

정적 데이터. 서버 시작 시 seed_items.json에서 로드. DB에도 저장하여 동적 Prototype 영속화.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| item_id | TEXT PK | 원형 ID |
| name_kr | TEXT | 한국어 이름 |
| item_type | TEXT | EQUIPMENT/CONSUMABLE/MATERIAL/MISC |
| weight | REAL | kg |
| bulk | INTEGER | 1~10 |
| base_value | INTEGER | 기본 거래가 |
| primary_material | TEXT | 주재질 |
| axiom_tags | TEXT (JSON) | {"Ignis": 1, "Lux": 2} |
| max_durability | INTEGER | 0 = 파괴 불가 |
| durability_loss_per_use | INTEGER | |
| broken_result | TEXT NULL | 파괴 시 변환 ID |
| container_capacity | INTEGER | 0 = 용기 아님 |
| flavor_text | TEXT | AI 묘사 힌트 |
| tags | TEXT (JSON) | ["flammable", "fragile"] |
| is_dynamic | BOOLEAN | false = 시드, true = 런타임 생성 |

### 11.2 item_instances

동적 데이터. Prototype의 Delta만 저장.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| instance_id | TEXT PK | UUID |
| prototype_id | TEXT FK | item_prototypes.item_id |
| owner_type | TEXT | "player"/"npc"/"node"/"container" |
| owner_id | TEXT | 소유자/위치 ID |
| current_durability | INTEGER | 현재 내구도 |
| state_tags | TEXT (JSON) | ["wet", "rusty"] |
| acquired_turn | INTEGER | 획득 턴 |
| custom_name | TEXT NULL | 커스텀 이름 |

인덱스: `(owner_type, owner_id)` — 인벤토리 조회 최적화.

---

## 12. 시드 데이터 요약

### 12.1 분류별 수량

| 카테고리 | 수량 | 포함 |
|---------|------|------|
| EQUIPMENT | 18종 | 도구 9 + 무기 5 + 방어구/방패/망토 4 |
| CONSUMABLE | 5종 | 붕대, 약초, 생고기, 지방, 소금 |
| MATERIAL | 6종 | 헝겊, 고철, 장작, 담즙, 거미줄, 목탄 |
| MISC | 11종 | 용기 5 + 제작 도구 3 + 정보 3 |
| 파괴 결과물 | 3종 | 재, 부러진 나무, 썩은 잔해 |
| **합계** | **43종** | |

### 12.2 확장 계획

- **Phase 2 완료 시**: ~100종 (NPC 직업별 전용 아이템 추가)
- **Phase 3 목표**: ~400종 (10배 증량, 바이옴별/던전별 고유 아이템)
- **공리 조합 생성**: 수량 제한 없음 (동적 Prototype)

### 12.3 확장 시 지켜야 할 규칙

1. 새 아이템은 seed_items.json에 JSON 객체 추가만으로 완료
2. 기존 axiom_tags 재사용 우선, 신규 태그 시 매핑 테이블 갱신
3. item_id 네이밍 규칙: `{카테고리접두사}_{설명}` (wpn_, arm_, mat_, misc_, fac_, info_, item_)
4. 파괴 결과물은 기존 Prototype 재사용 우선 (mat_iron_scrap 등)

---

## 13. Constraints 연동

item 시스템은 dialogue-system.md의 Constraints에 직접 기여한다.

대화 세션 시작 시 Python이 PC 보유 아이템을 Constraints로 조립:

```python
def build_item_constraints(player_id: str) -> dict:
    """PC 보유 아이템에서 Constraints 생성"""
    instances = query_items(owner_type="player", owner_id=player_id)

    pc_items = []
    pc_axiom_powers = {}  # 태그별 최대 강도

    for inst in instances:
        proto = get_prototype(inst.prototype_id)
        pc_items.append(proto.item_id)

        for tag, power in proto.axiom_tags.items():
            if tag not in pc_axiom_powers or power > pc_axiom_powers[tag]:
                pc_axiom_powers[tag] = power

    return {
        "pc_items": pc_items,
        "pc_axiom_powers": pc_axiom_powers,
    }
```

이 정보가 dialogue-system의 Constraints에 합류:

```json
{
  "constraints": {
    "pc_axioms": ["Fire_01", "Water_03"],
    "pc_stats": {"WRITE": 3, "READ": 4, "EXEC": 2, "SUDO": 1},
    "pc_items": ["wpn_rusty_sword", "tool_torch", "mat_dry_herb"],
    "pc_axiom_powers": {"Ignis": 1, "Scindere": 2, "Lux": 2, "Cura": 1}
  }
}
```

---

## 14. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-10 | 최초 작성 (Gemini 기획 기반 재설계) |
