# NPC 시스템 설계서

**버전**: 1.0  
**작성일**: 2025-02-07  
**상태**: 확정

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 NPC 시스템을 정의한다. 배경인물의 동적 생성부터 NPC로의 승격, 성격 시스템, 기억, 자율 행동까지 전체 생명주기를 다룬다.

### 1.2 핵심 게임 루프에서의 역할

```
배경인물 등장 → PC와 상호작용 → 관계 확립 → NPC화
      ↑                                    ↓
   월드 탐험                            대화 발생
      ↑                                    ↓
   캠페인 ← 연작 퀘스트 ← 단일 퀘스트 ← 자연 발생
```

NPC 시스템은 이 루프의 **시작점**으로, 플레이어가 월드와 의미 있는 관계를 형성하는 기반이 된다.

### 1.3 설계 원칙

- **LLM 최소화**: 계산 가능한 것은 Python으로 처리, LLM은 서술 생성만
- **동적 생성**: 스크립트된 NPC가 아닌 절차적 생성
- **관계 중심**: 단순 상호작용이 아닌 의미 있는 관계 형성
- **일관된 성격**: HEXACO 기반 행동 예측 가능성

---

## 2. 배경 존재 유형

### 2.1 3가지 유형

| 유형 | 영문 | 추적 방식 | 특성 |
|------|------|-----------|------|
| 거주형 | Resident | 시설 슬롯 | 위치 고정, 리셋 시 보호 |
| 유랑형 | Wanderer | WorldPool | 동적 생성, 재조우 가능 |
| 적대형 | Hostile | CombatTracker → WorldPool | 전투 시 임시 ID, 도주/생존 시 영속화 |

### 2.2 데이터 모델

```python
from enum import Enum
from typing import Optional, Dict, List, Set
from pydantic import BaseModel

class EntityType(str, Enum):
    RESIDENT = "resident"   # 거주형
    WANDERER = "wanderer"   # 유랑형
    HOSTILE = "hostile"     # 적대형

class BackgroundEntity(BaseModel):
    """승격 전 배경 존재"""
    
    entity_id: str
    entity_type: EntityType
    
    # 위치
    current_node: str
    home_node: Optional[str] = None  # 거주형만
    
    # 역할/외형
    role: str                    # "innkeeper", "traveler", "goblin"
    appearance_seed: Dict        # AI 서술용 시드
    
    # 승격 진행
    promotion_score: int = 0
    temp_combat_id: Optional[str] = None  # 적대형 전투 중
    
    # 이름 시드 (결정화 전 수집)
    name_seed: Optional["NPCNameSeed"] = None
```

---

## 3. 슬롯 시스템 (거주형)

### 3.1 개요

거주형 배경인물은 시설 기반 슬롯에서 관리된다.

```
노드 (여관)
├── 슬롯 1: 여관주인 (필수 역할)
├── 슬롯 2: 손님 A
├── 슬롯 3: 손님 B
└── 슬롯 4: (빈 슬롯)
```

### 3.2 슬롯 규칙

| 항목 | 규칙 |
|------|------|
| 슬롯 단위 | 노드 기본 + 서브그리드 진입 시 추가 |
| 슬롯 개수 | 시설 기본값 + 규모 보정 |
| 역할 정의 | 시설별 필수 역할 + AI 추가 생성 |
| 리셋 조건 | 시간 기반 + 승격 진행도 보호 |

### 3.3 슬롯 개수 계산

```python
# 시설별 기본 슬롯
FACILITY_BASE_SLOTS = {
    "inn": 4,
    "smithy": 2,
    "market": 6,
    "temple": 3,
    "tavern": 5,
    "farm": 2,
    "mine": 3,
}

def calculate_slot_count(facility_type: str, facility_size: int) -> int:
    """슬롯 개수 = 기본값 + 규모 보정"""
    base = FACILITY_BASE_SLOTS.get(facility_type, 2)
    size_modifier = facility_size // 2
    return base + size_modifier
```

### 3.4 리셋 규칙

```python
def should_reset_slot(slot: "BackgroundSlot", turns_passed: int) -> bool:
    """슬롯 리셋 여부 판정"""
    
    # 승격 진행 중이면 보호
    if slot.entity and slot.entity.promotion_score > 0:
        return False
    
    # 시간 기반 리셋 (기본 24턴)
    if turns_passed >= slot.reset_interval:
        return True
    
    return False
```

### 3.5 데이터 모델

```python
class BackgroundSlot(BaseModel):
    """거주형 배경인물 슬롯"""
    
    slot_id: str
    node_id: str
    facility_id: str
    
    # 역할
    role: str                    # "innkeeper", "patron", "servant"
    is_required: bool = False    # 필수 역할 여부
    
    # 현재 배치된 개체
    entity: Optional[BackgroundEntity] = None
    
    # 리셋 관리
    reset_interval: int = 24     # 턴
    last_reset_turn: int = 0

class FacilitySlots(BaseModel):
    """시설별 슬롯 관리"""
    
    facility_id: str
    node_id: str
    facility_type: str
    
    slots: List[BackgroundSlot]
    
    def get_available_slot(self) -> Optional[BackgroundSlot]:
        """빈 슬롯 반환"""
        for slot in self.slots:
            if slot.entity is None:
                return slot
        return None
```

---

## 4. 승격 시스템

### 4.1 개요

배경 존재가 NPC로 승격되는 통일된 점수 시스템.

- **임계값**: 50점
- **WorldPool 등록**: 15점 이상 (30%)
- **3유형 동일 로직**, 트리거만 다름

### 4.2 승격 점수 테이블

| 행동 | 점수 | 적용 유형 |
|------|------|-----------|
| 단순 조우 (같은 공간) | +5 | 전체 |
| 말 걸기 (인사 수준) | +15 | 거주형, 유랑형 |
| 실질적 대화 (정보 교환) | +30 | 거주형, 유랑형 |
| 거래 | +20 | 거주형, 유랑형 |
| 공동 전투 (아군) | +40 | 유랑형 |
| 도움 주기/받기 | +35 | 전체 |
| 이름 묻기 | +50 | 거주형, 유랑형 |
| 전투 발생 | +20 | 적대형 |
| 전투 중 생존 | +15 | 적대형 |
| 도주 성공 | +25 | 적대형 |

### 4.3 승격 처리

```python
PROMOTION_THRESHOLD = 50
WORLDPOOL_THRESHOLD = 15  # 30%

def add_promotion_score(entity: BackgroundEntity, action: str) -> bool:
    """
    승격 점수 추가
    Returns: True if promoted to NPC
    """
    score = PROMOTION_SCORE_TABLE.get(action, 0)
    entity.promotion_score += score
    
    # WorldPool 등록 체크
    if entity.promotion_score >= WORLDPOOL_THRESHOLD:
        if entity.entity_type in [EntityType.WANDERER, EntityType.HOSTILE]:
            world_pool.register(entity)
    
    # 승격 체크
    if entity.promotion_score >= PROMOTION_THRESHOLD:
        npc = promote_to_npc(entity)
        return True
    
    return False

def promote_to_npc(entity: BackgroundEntity) -> "NPC":
    """배경 존재 → NPC 승격"""
    
    # 1. 이름 생성
    full_name = generate_name(entity.name_seed)
    
    # 2. HEXACO 생성
    hexaco = generate_hexaco(entity.role)
    
    # 3. CharacterSheet 생성
    character_sheet = generate_character_sheet(entity.role)
    
    # 4. 공리 숙련도 생성
    axiom_proficiencies = generate_axiom_proficiencies(entity.role)
    
    # 5. NPC 레코드 생성
    npc = NPC(
        npc_id=generate_uuid(),
        full_name=full_name,
        hexaco=hexaco,
        character_sheet=character_sheet,
        axiom_proficiencies=axiom_proficiencies,
        origin_type="promoted",
        origin_entity_type=entity.entity_type,
        home_node=entity.home_node,
        current_node=entity.current_node,
    )
    
    # 6. DB 저장
    db.save_npc(npc)
    
# 7. 승격 이벤트 발행 (다른 모듈이 구독)
    event_bus.emit("npc_promoted", {
        "npc_id": npc.npc_id,
        "origin_type": entity.entity_type,
        "node_id": entity.current_node,
    })
    # → memory 모듈: create_initial_memory() 호출
    # → relationship 모듈: create_initial_relationship() 호출
    
    return npc
```

---

## 5. 적대형 전투 추적

### 5.1 CombatTracker

전투 중 적대형 개체를 임시 추적하고, 도주/생존 시 영속화한다.

```python
class CombatTracker:
    """전투 중 적대형 임시 추적"""
    
    active_combats: Dict[str, BackgroundEntity] = {}
    
    def on_combat_start(self, entity: BackgroundEntity) -> str:
        """전투 시작 시 임시 ID 부여"""
        temp_id = f"combat_{generate_short_id()}"
        entity.temp_combat_id = temp_id
        self.active_combats[temp_id] = entity
        
        # 전투 시작만으로 승격 점수 추가
        add_promotion_score(entity, "combat_engaged")
        
        return temp_id
    
    def on_combat_end(self, temp_id: str, outcome: str) -> Optional["NPC"]:
        """
        전투 종료 처리
        
        Args:
            outcome: "killed" | "fled" | "survived" | "pc_fled"
        
        Returns:
            NPC if promoted, None otherwise
        """
        entity = self.active_combats.get(temp_id)
        if not entity:
            return None
        
        if outcome == "killed":
            # 사망 - 폐기
            del self.active_combats[temp_id]
            return None
        
        elif outcome in ["fled", "survived", "pc_fled"]:
            # 생존 - 승격 점수 추가
            if outcome == "fled":
                add_promotion_score(entity, "fled_combat")
            else:
                add_promotion_score(entity, "survived_combat")
            
            # 임계값 도달 시 즉시 승격
            if entity.promotion_score >= PROMOTION_THRESHOLD:
                npc = promote_to_npc(entity)
                del self.active_combats[temp_id]
                return npc
            
            # 미달이어도 WorldPool 등록
            world_pool.register(entity)
            del self.active_combats[temp_id]
        
        return None
```

---

## 6. WorldPool

### 6.1 개요

유랑형/적대형 개체의 재조우를 관리하는 풀.

| 항목 | 값 |
|------|-----|
| 유랑형 최대 | 10개 |
| 적대형 최대 | 10개 |
| 등록 조건 | 승격 점수 ≥ 15 (30%) |
| 재조우 확률 | 승격 점수 × 거리 보정 |
| 만료 | 점수 감쇠 + 풀 크기 제한 |

### 6.2 데이터 모델

```python
class WorldPool:
    """재조우 가능 개체 풀"""
    
    wanderers: Dict[str, BackgroundEntity] = {}  # 최대 10
    hostiles: Dict[str, BackgroundEntity] = {}   # 최대 10
    
    WANDERER_MAX = 10
    HOSTILE_MAX = 10
    SCORE_DECAY_RATE = 0.95  # 턴당 5% 감쇠
    
    def register(self, entity: BackgroundEntity) -> bool:
        """개체 등록"""
        pool = self._get_pool(entity.entity_type)
        max_size = self._get_max_size(entity.entity_type)
        
        # 풀 크기 제한 체크
        if len(pool) >= max_size:
            # 가장 점수 낮은 것 제거
            lowest = min(pool.values(), key=lambda e: e.promotion_score)
            del pool[lowest.entity_id]
        
        pool[entity.entity_id] = entity
        return True
    
    def maybe_reencounter(
        self, 
        node_id: str, 
        entity_type: EntityType
    ) -> Optional[BackgroundEntity]:
        """재조우 판정"""
        pool = self._get_pool(entity_type)
        
        candidates = []
        for entity in pool.values():
            # 재조우 확률 계산
            distance = calculate_node_distance(entity.current_node, node_id)
            distance_mod = max(0.1, 1.0 - (distance * 0.1))
            probability = (entity.promotion_score / 100) * distance_mod
            
            if random.random() < probability:
                candidates.append(entity)
        
        if candidates:
            return random.choice(candidates)
        return None
    
    def tick(self) -> None:
        """턴 경과 시 점수 감쇠"""
        for pool in [self.wanderers, self.hostiles]:
            to_remove = []
            for entity_id, entity in pool.items():
                entity.promotion_score = int(
                    entity.promotion_score * self.SCORE_DECAY_RATE
                )
                # 등록 임계값 이하로 떨어지면 제거
                if entity.promotion_score < WORLDPOOL_THRESHOLD:
                    to_remove.append(entity_id)
            
            for entity_id in to_remove:
                del pool[entity_id]
```

---

## 7. 명명 시스템

### 7.1 이름 구조

```
[영지/지역명]의 [바이옴 특성] [시설/직업] [이름]

예시:
- "타르고스 영지의 언덕 대장간 대장장이 탈라"
- "화염 산맥의 자유 상인 엘라르"
- "푸른 숲의 외딴 오두막 약초사 미렌"
```

### 7.2 데이터 모델

```python
class NPCNameSeed(BaseModel):
    """이름 생성용 시드 (결정화 전 수집)"""
    
    region_name: str          # "타르고스 영지"
    biome_descriptor: str     # "언덕", "화염 산맥"
    facility_type: str        # "smithy", "market"
    role: str                 # "blacksmith", "merchant"
    gender: str               # "M", "F", "N"

class NPCFullName(BaseModel):
    """NPC 전체 명칭"""
    
    # 정식 명칭 구성 요소
    region_name: str
    biome_descriptor: str
    facility_name: str
    occupation: str
    given_name: str
    gender: str
    
    # 현재 상태 (변경 가능)
    current_occupation: str
    
    def formal_name(self) -> str:
        """정식 명칭"""
        return (f"{self.region_name}의 {self.biome_descriptor} "
                f"{self.facility_name} {self.occupation} {self.given_name}")
    
    def current_name(self) -> str:
        """현재 상태 반영 명칭"""
        if self.current_occupation != self.occupation:
            return f"{self.current_occupation} {self.given_name}"
        return f"{self.occupation} {self.given_name}"
    
    def short_name(self) -> str:
        """짧은 호칭"""
        return self.given_name
```

### 7.3 이름 풀

```python
# data/names/pool.json
NAME_POOLS = {
    "biome_descriptors": {
        "temperate_forest": ["푸른 숲", "고요한 숲", "이끼낀 골짜기"],
        "volcanic": ["화염 산맥", "재의 평원", "용암 기슭"],
        "hills": ["언덕", "구릉지", "바위 고원"],
        "desert": ["모래벌판", "메마른 땅", "태양의 길"],
    },
    
    "given_names": {
        "M": ["엘라르", "토린", "발더", "카엘", "드레이크", "로건", "에릭"],
        "F": ["탈라", "미렌", "세라", "아이린", "릴리아", "엘레나", "이사벨"],
        "N": ["아쉬", "로완", "퀸", "사이러스", "모건", "테일러", "조던"],
    },
    
    "occupations": {
        "blacksmith": {"title": "대장장이", "facility": "대장간"},
        "merchant": {"title": "상인", "facility": "상점"},
        "herbalist": {"title": "약초사", "facility": "오두막"},
        "innkeeper": {"title": "여관주인", "facility": "여관"},
        "guard": {"title": "경비병", "facility": "초소"},
        "farmer": {"title": "농부", "facility": "농장"},
        "miner": {"title": "광부", "facility": "광산"},
    },
}

def generate_name(seed: NPCNameSeed) -> NPCFullName:
    """시드로부터 이름 생성"""
    occupation_data = NAME_POOLS["occupations"].get(seed.role, {})
    given_names = NAME_POOLS["given_names"].get(seed.gender, [])
    
    return NPCFullName(
        region_name=seed.region_name,
        biome_descriptor=seed.biome_descriptor,
        facility_name=occupation_data.get("facility", ""),
        occupation=occupation_data.get("title", seed.role),
        given_name=random.choice(given_names),
        gender=seed.gender,
        current_occupation=occupation_data.get("title", seed.role),
    )
```

### 7.4 직업 불일치 서사

```python
def get_introduction_context(npc: "NPC") -> Dict[str, Any]:
    """통성명 시 서사 컨텍스트"""
    
    context = {
        "formal_name": npc.full_name.formal_name(),
        "current_name": npc.full_name.current_name(),
        "has_occupation_change": (
            npc.full_name.occupation != npc.full_name.current_occupation
        ),
    }
    
    if context["has_occupation_change"]:
        context["narrative_hint"] = (
            f"과거 {npc.full_name.occupation}였으나 "
            f"현재 {npc.full_name.current_occupation}. 사연이 있을 수 있음."
        )
    
    return context
```

---

## 8. HEXACO 성격 시스템

### 8.1 6요인

| 요인 | 약자 | 고득점 성향 | 저득점 성향 |
|------|------|-------------|-------------|
| Honesty-Humility | H | 정직, 겸손 | 교활, 탐욕 |
| Emotionality | E | 감정적, 불안 | 냉정, 대담 |
| eXtraversion | X | 사교적, 활발 | 내향적, 과묵 |
| Agreeableness | A | 온화, 관용 | 완고, 비판적 |
| Conscientiousness | C | 체계적, 신중 | 충동적, 유연 |
| Openness | O | 호기심, 창의 | 보수적, 실용 |

### 8.2 값 범위

- **범위**: 0.0 ~ 1.0 (연속값)
- **중립**: 0.5
- **극단**: < 0.3 또는 > 0.7

### 8.3 역할 기반 생성

```python
# 역할별 HEXACO 기본값 (±0.15 랜덤 보정)
ROLE_HEXACO_TEMPLATES = {
    "blacksmith": {"H": 0.6, "E": 0.4, "X": 0.4, "A": 0.5, "C": 0.7, "O": 0.4},
    "merchant": {"H": 0.4, "E": 0.5, "X": 0.7, "A": 0.5, "C": 0.6, "O": 0.5},
    "guard": {"H": 0.6, "E": 0.3, "X": 0.5, "A": 0.4, "C": 0.7, "O": 0.3},
    "innkeeper": {"H": 0.5, "E": 0.5, "X": 0.8, "A": 0.7, "C": 0.5, "O": 0.5},
    "scholar": {"H": 0.7, "E": 0.6, "X": 0.3, "A": 0.5, "C": 0.7, "O": 0.9},
    "bandit": {"H": 0.2, "E": 0.4, "X": 0.5, "A": 0.3, "C": 0.4, "O": 0.4},
    "goblin": {"H": 0.2, "E": 0.6, "X": 0.5, "A": 0.2, "C": 0.3, "O": 0.3},
}

def generate_hexaco(role: str) -> Dict[str, float]:
    """역할 기반 HEXACO 생성"""
    template = ROLE_HEXACO_TEMPLATES.get(role, {
        "H": 0.5, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5
    })
    
    hexaco = {}
    for factor, base_value in template.items():
        # ±0.15 랜덤 보정
        variance = random.uniform(-0.15, 0.15)
        hexaco[factor] = max(0.0, min(1.0, base_value + variance))
    
    return hexaco
```

### 8.4 행동 매핑 테이블

```python
HEXACO_BEHAVIOR_MAP = {
    "H": {  # Honesty-Humility
        "high": {"trade_price_mod": -0.1, "lie_chance": 0.05, "betray_chance": 0.02},
        "low": {"trade_price_mod": +0.2, "lie_chance": 0.40, "betray_chance": 0.25},
    },
    "E": {  # Emotionality
        "high": {"flee_threshold": 0.5, "panic_chance": 0.3, "empathy_bonus": +20},
        "low": {"flee_threshold": 0.2, "panic_chance": 0.05, "empathy_bonus": -10},
    },
    "X": {  # eXtraversion
        "high": {"talk_initiative": 0.8, "group_seek": True, "info_share": 0.7},
        "low": {"talk_initiative": 0.2, "group_seek": False, "info_share": 0.3},
    },
    "A": {  # Agreeableness
        "high": {"forgive_chance": 0.7, "conflict_avoid": True, "favor_threshold": 20},
        "low": {"forgive_chance": 0.2, "conflict_avoid": False, "favor_threshold": 50},
    },
    "C": {  # Conscientiousness
        "high": {"quest_complete_bonus": 1.2, "promise_keep": 0.95, "punctual": True},
        "low": {"quest_complete_bonus": 0.8, "promise_keep": 0.5, "punctual": False},
    },
    "O": {  # Openness
        "high": {"unusual_accept": 0.8, "new_idea_bonus": +15, "tradition_respect": 0.3},
        "low": {"unusual_accept": 0.2, "new_idea_bonus": -5, "tradition_respect": 0.9},
    },
}

def get_behavior_modifier(hexaco: Dict[str, float], factor: str, modifier: str) -> Any:
    """HEXACO 값에 따른 행동 수정자 조회"""
    value = hexaco.get(factor, 0.5)
    
    if value > 0.7:
        return HEXACO_BEHAVIOR_MAP[factor]["high"].get(modifier)
    elif value < 0.3:
        return HEXACO_BEHAVIOR_MAP[factor]["low"].get(modifier)
    else:
        # 중간값은 두 극단의 평균
        high_val = HEXACO_BEHAVIOR_MAP[factor]["high"].get(modifier)
        low_val = HEXACO_BEHAVIOR_MAP[factor]["low"].get(modifier)
        if isinstance(high_val, (int, float)) and isinstance(low_val, (int, float)):
            return (high_val + low_val) / 2
        return high_val  # bool 등은 high 기준
```

---

## 9. 톤 태그 시스템

### 9.1 개요

HEXACO와 상황을 Python으로 분석하여 톤 태그를 생성하고, LLM에 전달한다.

### 9.2 ToneContext 구조

```python
@dataclass
class ToneContext:
    """Python이 계산하여 LLM에 전달하는 톤 컨텍스트"""
    
    # 감정 상태
    emotion: str              # "neutral", "happy", "angry", "fearful", "sad"
    emotion_intensity: float  # 0.0 ~ 1.0
    
    # 말투 태그 (HEXACO에서 도출)
    manner_tags: List[str]    # ["formal", "blunt", "verbose", ...]
    
    # 태도 태그 (관계 + HEXACO 조합)
    attitude_tags: List[str]  # ["respectful", "dismissive", "curious", ...]
    
    # 의도
    intent: str               # "inform", "request", "refuse", "warn", ...
```

### 9.3 HEXACO → manner_tags 변환

```python
def derive_manner_tags(hexaco: Dict[str, float]) -> List[str]:
    """HEXACO에서 말투 태그 도출"""
    tags = []
    
    # Extraversion → 말의 양/에너지
    if hexaco["X"] > 0.7:
        tags.extend(["verbose", "energetic"])
    elif hexaco["X"] < 0.3:
        tags.extend(["terse", "quiet"])
    
    # Agreeableness → 어조
    if hexaco["A"] > 0.7:
        tags.extend(["gentle", "polite"])
    elif hexaco["A"] < 0.3:
        tags.extend(["blunt", "confrontational"])
    
    # Honesty-Humility → 표현 방식
    if hexaco["H"] > 0.7:
        tags.extend(["direct", "sincere"])
    elif hexaco["H"] < 0.3:
        tags.extend(["evasive", "flattering"])
    
    # Conscientiousness → 구조화
    if hexaco["C"] > 0.7:
        tags.extend(["formal", "precise"])
    elif hexaco["C"] < 0.3:
        tags.extend(["casual", "rambling"])
    
    # Emotionality → 감정 표현
    if hexaco["E"] > 0.7:
        tags.extend(["expressive", "dramatic"])
    elif hexaco["E"] < 0.3:
        tags.extend(["stoic", "matter-of-fact"])
    
    # Openness → 어휘/비유
    if hexaco["O"] > 0.7:
        tags.extend(["colorful", "metaphorical"])
    elif hexaco["O"] < 0.3:
        tags.extend(["plain", "literal"])
    
    return tags
```

### 9.4 감정 계산

```python
EVENT_EMOTION_MAP = {
    "greeting": "neutral",
    "helped": "happy",
    "betrayed": "angry",
    "threatened": "fearful",
    "lost_item": "sad",
    "insulted": "angry",
    "complimented": "happy",
}

def calculate_emotion(
    event: str, 
    relationship: "Relationship", 
    hexaco: Dict[str, float]
) -> Tuple[str, float]:
    """상황 + 관계 + 성격 → 감정 계산"""
    
    base_emotion = EVENT_EMOTION_MAP.get(event, "neutral")
    intensity = 0.5
    
    # 이벤트별 기본 강도
    if event in ["betrayed", "threatened"]:
        intensity = 0.8
    elif event in ["helped", "complimented"]:
        intensity = 0.6
    
    # HEXACO 보정
    if base_emotion == "angry" and hexaco["A"] > 0.7:
        intensity *= 0.7  # 온화한 성격은 분노 약화
    if base_emotion == "fearful" and hexaco["E"] < 0.3:
        intensity *= 0.5  # 냉정한 성격은 공포 약화
    if base_emotion == "happy" and hexaco["X"] > 0.7:
        intensity *= 1.2  # 외향적 성격은 기쁨 증폭
    
    # 관계 보정
    if relationship:
        if relationship.affinity > 50 and base_emotion == "angry":
            intensity *= 0.8  # 친한 사이면 분노 약화
        if relationship.affinity < -30 and base_emotion == "angry":
            intensity *= 1.2  # 적대 관계면 분노 증폭
    
    intensity = max(0.0, min(1.0, intensity))
    return (base_emotion, intensity)
```

### 9.5 LLM 프롬프트 생성

```python
def build_dialogue_prompt(
    npc: "NPC", 
    tone: ToneContext, 
    situation: str,
    overlay_tags: List[str]
) -> str:
    """대화 생성용 LLM 프롬프트"""
    
    return f"""
NPC: {npc.full_name.current_name()} ({npc.current_role})
성격 요약: {summarize_hexaco(npc.hexaco)}
감정: {tone.emotion} (강도 {tone.emotion_intensity:.1f})
말투: {', '.join(tone.manner_tags)}
태도: {', '.join(tone.attitude_tags)}
의도: {tone.intent}
상황: {situation}
환경 태그: {', '.join(overlay_tags)}

위 조건에 맞는 NPC의 대사를 1-2문장으로 생성하세요.
"""
```

---

## 10. 기억 시스템

### 10.1 3계층 구조

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 1: 핵심 기억 (Core)                                   │
│  - 항상 로드                                                │
│  - NPC당 최대 5개 (고정 2 + 교체 3)                         │
│  - 관계 정의 이벤트                                         │
│  - 토큰: ~100-150                                           │
├─────────────────────────────────────────────────────────────┤
│  Tier 2: 최근 기억 (Recent)                                 │
│  - 관계도 기반 슬라이딩 윈도우                              │
│  - 친밀: 20개 / 소원: 3-5개                                │
│  - 토큰: ~100-400                                           │
├─────────────────────────────────────────────────────────────┤
│  Tier 3: 아카이브 (Archive)                                 │
│  - 평소 로드 안 함                                          │
│  - 키워드/유사도 트리거 시에만                              │
│  - 토큰: 0 (평소) / ~50-100 (트리거 시)                    │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Tier 1 슬롯 구조

```
Tier 1 핵심 기억 (5개):
├── 고정 슬롯 (2개, 교체 불가)
│   ├── [1] 첫 조우 기억 (결정화 시작 사건)
│   └── [2] 첫 고임팩트 기억 (importance 첫 0.8+ 돌파)
│
└── 교체 슬롯 (3개)
    ├── [3] 최근 고임팩트 기억
    ├── [4] 최근 고임팩트 기억
    └── [5] 최근 고임팩트 기억
    
    * 새 고임팩트 기억 발생 시:
      → 교체 슬롯 중 가장 오래된 것을 Tier 2로 강등
      → 새 기억이 교체 슬롯에 진입
```

### 10.3 관계도 기반 용량

| 관계 단계 | Tier 2 상한 |
|-----------|-------------|
| stranger | 3 |
| acquaintance | 7 |
| friend | 15 |
| ally / rival | 20 |

### 10.4 데이터 모델

```python
class NPCMemory(BaseModel):
    """NPC 기억"""
    
    memory_id: str
    npc_id: str
    
    # 계층
    tier: int  # 1, 2, 3
    
    # 내용
    memory_type: str  # "encounter", "trade", "combat", "quest", "betrayal", "favor"
    summary: str      # 1-2문장 요약
    
    # 감정/중요도
    emotional_valence: float  # -1.0 ~ +1.0
    importance: float         # 0.0 ~ 1.0
    
    # 벡터 검색용 (Tier 3)
    embedding: Optional[List[float]] = None
    
    # 메타
    turn_created: int
    related_node: Optional[str] = None
    
    # Tier 1 고정 여부
    is_fixed: bool = False
    fixed_slot: Optional[int] = None  # 1 또는 2 (고정 슬롯 번호)
```

### 10.5 중요도(importance) 초기값

| 상호작용 유형 | importance |
|---------------|------------|
| 단순 조우 | 0.2 |
| 일반 대화 | 0.3 |
| 거래 | 0.4 |
| 호의 제공/수령 | 0.6 |
| 공동 전투 | 0.7 |
| 생명 구함/위협 | 0.9 |
| 배신/약속 파기 | 0.95 |

### 10.6 Embedding

- **방식**: 로컬 sentence-transformers
- **모델**: all-MiniLM-L6-v2
- **용도**: Tier 3 검색 (코사인 유사도)
- **설치 용량**: ~100MB

```python
from sentence_transformers import SentenceTransformer

class MemoryEmbedder:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def embed(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()
    
    def search_similar(
        self, 
        query: str, 
        memories: List[NPCMemory], 
        top_k: int = 3
    ) -> List[NPCMemory]:
        query_embedding = self.embed(query)
        
        scored = []
        for memory in memories:
            if memory.embedding:
                similarity = cosine_similarity(query_embedding, memory.embedding)
                scored.append((memory, similarity))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:top_k]]
```

---

## 11. 8대 공명 속성 + 공리 숙련도

### 11.1 8대 공명 속성 (Resonance Types)

| 공명 속성 | 영문 | 개념 영역 |
|-----------|------|-----------|
| 열/에너지 | Thermal | 온도, 연소, 빛 |
| 운동/물리 | Kinetic | 힘, 속도, 충격 |
| 물질/구조 | Structural | 형태, 경도, 물성 |
| 생체/독 | Bio | 생명, 치유, 독 |
| 정신/감정 | Psyche | 의지, 감정, 인지 |
| 논리/기계 | Data | 정보, 계산, 체계 |
| 사회/규율 | Social | 관계, 권위, 약속 |
| 신비/초월 | Esoteric | 운명, 차원, 본질 |

### 11.2 저항력 (Resonance Shield)

```python
class ResonanceShield(BaseModel):
    """8대 공명 속성별 내구도 (HP 대체)"""
    
    thermal: Optional[int] = 10
    kinetic: Optional[int] = 10
    structural: Optional[int] = 10
    bio: Optional[int] = 10
    psyche: Optional[int] = 10
    data: Optional[int] = 10
    social: Optional[int] = 10
    esoteric: Optional[int] = 10
    
    # None = 면역, 0 = 붕괴(Break)
```

### 11.3 공리 숙련도

- **범위**: 0 ~ 100
- **곡선**: 지수 (level ^ 2.2)
- **NPC 보유**: 주력 1~2개 + 부수 4~5개 + 기타 1~3개

```python
def exp_to_next_level(level: int) -> int:
    """다음 레벨까지 필요 경험치"""
    return int(5 * ((level + 1) ** 2.2))
```

### 11.4 NPC 등급별 숙련도

| NPC 등급 | 주력 | 부수 (4~5개) | 기타 |
|----------|------|--------------|------|
| 일반 | 30~40 | 15~25 | 5~10 |
| 희귀 (장인) | 50~60 | 30~40 | 10~20 |
| 전설급 (대가) | 75~85 | 50~60 | 25~35 |
| 마스터 | 95~100 | 70~80 | 40~50 |

### 11.5 역할 기반 템플릿

```python
ROLE_AXIOM_TEMPLATES = {
    "blacksmith": {
        "primary": ["Ignis", "Ferrum"],
        "secondary": ["Forma", "Kinetic", "Structural", "Terra"],
        "stat_template": {"WRITE": 8, "READ": 10, "EXEC": 14, "SUDO": 8},
    },
    "scholar": {
        "primary": ["Cognito", "Veritas"],
        "secondary": ["Memoria", "Lingua", "Data", "Ratio"],
        "stat_template": {"WRITE": 14, "READ": 16, "EXEC": 8, "SUDO": 10},
    },
    "merchant": {
        "primary": ["Commercium"],
        "secondary": ["Lingua", "Social", "Fortuna", "Via"],
        "stat_template": {"WRITE": 12, "READ": 12, "EXEC": 10, "SUDO": 12},
    },
    "guard": {
        "primary": ["Ferrum", "Kinetic"],
        "secondary": ["Structural", "Custodia", "Vigor"],
        "stat_template": {"WRITE": 8, "READ": 10, "EXEC": 14, "SUDO": 10},
    },
}
```

---

## 12. 자율 행동 시스템

### 12.1 3단계 도입

| Phase | 단계 | 내용 |
|-------|------|------|
| A | Alpha | 역할 기반 스케줄 |
| B | Beta | 욕구 시스템 기초 |
| C | 정식 | 완전 자율 + 충성/반란 |

### 12.2 욕구 체계 (7종)

| 계층 | 욕구 | 설명 |
|------|------|------|
| 생존 | Hunger | 식량 필요 |
| 생존 | Fatigue | 휴식 필요 |
| 생존 | Safety | 위협 감지 |
| 경제 | Profit | 자원/돈 욕구 |
| 사회 | Social | 관계 욕구 |
| 사회 | Belonging | 집단 귀속 |
| 자아 | Achievement | 목표 달성 |

### 12.3 욕구 우선순위

```python
def get_priority_need(npc: "NPC") -> NeedType:
    """욕구 우선순위 결정"""
    needs = npc.state.needs
    
    # 1차: 위기 체크
    if needs[NeedType.SAFETY] < 20:
        return NeedType.SAFETY
    
    # 2차: 생존 체크
    if needs[NeedType.HUNGER] > 80:
        return NeedType.HUNGER
    if needs[NeedType.FATIGUE] > 80:
        return NeedType.FATIGUE
    
    # 3차: 성격 기반 가중치 적용
    weighted_needs = apply_hexaco_weights(npc.hexaco, needs)
    return max(weighted_needs, key=weighted_needs.get)
```

### 12.4 Phase A: 스케줄 시스템

```python
class TimeOfDay(str, Enum):
    DAWN = "Dawn"           # 04~08
    MORNING = "Morning"     # 08~12
    AFTERNOON = "Afternoon" # 12~16
    EVENING = "Evening"     # 16~20
    NIGHT = "Night"         # 20~04

class DailyRoutine(BaseModel):
    job: str
    workplace_id: str
    home_id: str
    schedule: Dict[TimeOfDay, ScheduleEntry]

class ScheduleEntry(BaseModel):
    location: str
    activity: str
    variance: float  # 이탈 확률 (0.0~0.3)
    alternatives: List[str]
```

---

## 13. NPC 완전 데이터 모델

```python
class NPC(BaseModel):
    """완전한 NPC 데이터"""
    
    # 식별
    npc_id: str
    
    # 명칭
    full_name: NPCFullName
    
    # 성격
    hexaco: Dict[str, float]  # 0.0~1.0
    
    # 능력치
    character_sheet: CharacterSheet
    resonance_shield: ResonanceShield
    axiom_proficiencies: Dict[str, int]  # 공리명 → 숙련도 (0~100)
    
    # 위치
    home_node: Optional[str]
    current_node: str
    
    # 자율 행동
    routine: Optional[DailyRoutine]
    state: NPCState
    
    # 소속
    lord_id: Optional[str]
    faction_id: Optional[str]
    loyalty: float = 0.5
    
    # 메타
    origin_type: str  # "promoted", "scripted"
    origin_entity_type: Optional[EntityType]
    created_at: datetime
    last_interaction: Optional[datetime]
```

---

## 14. API 인터페이스

### 14.1 NPCCoreModule

```python
class NPCCoreModule(GameModule):
    name = "npc_core"
    dependencies = []
    
    def get_npcs_at_node(self, node_id: str) -> List[NPC]:
        """노드의 NPC 목록"""
        pass
    
    def get_background_entities_at_node(self, node_id: str) -> List[BackgroundEntity]:
        """노드의 배경 존재 목록"""
        pass
    
    def interact_with_entity(
        self, 
        entity: BackgroundEntity, 
        action: str
    ) -> InteractionResult:
        """배경 존재와 상호작용, 승격 체크 포함"""
        pass
    
    def get_npc_by_id(self, npc_id: str) -> Optional[NPC]:
        """ID로 NPC 조회"""
        pass
```

### 14.2 이벤트 정의

npc_core 모듈이 발행하는 이벤트:

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `npc_promoted` | npc_id, origin_type, node_id | memory, relationship |
| `npc_died` | npc_id, cause, node_id | relationship, quest_engine |
| `npc_moved` | npc_id, from_node, to_node | - |

npc_core 모듈이 구독하는 이벤트:

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `quest_npc_needed` | quest_engine | 퀘스트용 NPC 생성 |
| `combat_entity_survived` | combat | 적대형 영속화 |

---

## 15. 구현 우선순위

### Alpha 필수

- 배경인물 슬롯 (거주형)
- 승격 시스템 (기본)
- NPC 저장/로드
- HEXACO 생성
- 톤 태그 생성
- 기억 Tier 1

### Alpha 후

- 유랑형/적대형
- WorldPool
- CombatTracker
- 기억 Tier 2, 3
- Embedding 검색
- 자율 행동 Phase A

### 미래 확장

- 자율 행동 Phase B, C
- 충성/반란 시스템
- NPC 간 관계

---

## 16. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2025-02-07 | 최초 작성 |
