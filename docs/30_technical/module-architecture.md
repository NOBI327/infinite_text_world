# ITW 모듈식 아키텍처 설계서

**버전**: 1.0  
**작성일**: 2025-02-07  
**상태**: 확정

---

## 1. 개요

### 1.1 목적

이 문서는 ITW(Infinite Text World) 프로젝트의 모듈식 개발 구조를 정의한다. 핵심 게임 루프를 기반으로 기능별 모듈을 독립적으로 개발하고 테스트할 수 있는 아키텍처를 수립한다.

### 1.2 설계 원칙

- **모듈 격리**: 각 모듈은 독립적으로 활성화/비활성화 가능
- **명시적 의존성**: 모듈 간 의존 관계를 명확히 정의
- **점진적 복잡도**: 기반 모듈부터 순차적으로 고급 기능 추가
- **테스트 용이성**: 모듈 단위 테스트 및 통합 테스트 지원

### 1.3 개발 전략

수직 슬라이스가 아닌 **모듈 기반 하이브리드 접근**을 채택한다:

1. 기본 게임 루프 완성
2. 각 기능 모듈을 완전히 구현
3. 모듈을 붙였다 떼면서 검증
4. 검증 완료 후 다음 모듈 개발

---

## 2. 레이어 구조

### 2.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Core (항상 활성)                                  │
│    - 이동, 기본 상호작용, AI 서술                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 기반 시스템                                       │
│    [A] geography    [B] time_core                           │
│    [C] npc_core     [D] item_core                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 오버레이 시스템                                   │
│    [E] overlay_core                                         │
│    [F] weather_overlay   [G] territory_overlay              │
│    [H] quest_overlay     [I] event_overlay                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 상호작용 모듈                                     │
│    [J] dialogue     [K] memory      [L] relationship        │
│    [M] combat       [N] crafting                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: 고급 시스템                                       │
│    [O] quest_engine    [P] npc_behavior                     │
│    [Q] worldpool       [R] economy                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 의존성 다이어그램

```
                    ┌─────────────┐
                    │    Core     │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
   ┌─────────┐       ┌──────────┐       ┌──────────┐
   │geography│       │time_core │       │ npc_core │
   │         │       │          │       │          │
   └────┬────┘       └────┬─────┘       └────┬─────┘
        │                 │                  │
        └────────┬────────┘                  │
                 ↓                           │
          ┌─────────────┐                    │
          │overlay_core │←───────────────────┘
          └──────┬──────┘
                 │
     ┌───────────┼───────────┬───────────┐
     ↓           ↓           ↓           ↓
┌─────────┐┌──────────┐┌──────────┐┌─────────┐
│ weather ││territory ││  quest   ││  event  │
│ overlay ││ overlay  ││ overlay  ││ overlay │
└─────────┘└────┬─────┘└────┬─────┘└─────────┘
                │           │
                ↓           ↓
          ┌──────────┐┌──────────┐
          │ economy  ││  quest   │
          │          ││  engine  │
          └──────────┘└──────────┘
```

### 2.3 기존 코드와의 관계

#### 공존 전략

기존 `src/core/`와 `src/services/`는 유지하며, `src/modules/`가 추가된다.
```
src/
├── core/           # 순수 로직 (DB 무관) - 유지
├── services/       # 기존 서비스 - 점진적 모듈화
├── modules/        # 새 모듈 구조 - 신규
├── db/             # ORM 모델 - 유지
└── api/            # FastAPI - 유지
```

#### 마이그레이션 방침

| 기존 파일 | 처리 방식 |
|-----------|-----------|
| core/engine.py | 유지 (Core 게임 루프) |
| core/navigator.py | 유지 → geography 모듈이 래핑 |
| core/dice.py | 유지 (공용 유틸리티) |
| services/narrative_service.py | 유지 (Core에서 직접 사용) |
| services/ai_service.py | 유지 (공용 인프라) |

#### 원칙

- **기존 core/**: 순수 로직으로 유지, 모듈에서 import 가능
- **기존 services/**: 신규 기능은 modules/로, 기존은 점진적 이관
- **modules/**: 토글 가능한 기능 단위, GameModule 인터페이스 구현

---

## 3. 모듈 상세 정의

### 3.1 Layer 0: Core (항상 활성)

Core는 모듈이 아니라 항상 활성화된 기반 시스템이다.

**포함 기능:**
- 플레이어 이동
- 노드 진입/이탈
- 기본 상호작용 (조사, 대기)
- AI 서술 생성 (NarrativeService)
- 게임 루프 관리

**위치:** `src/core/`, `src/services/narrative_service.py`

---

### 3.2 Layer 1: 기반 시스템

#### [A] geography

**역할:** 맵, 노드, 서브그리드, 바이옴 관리

**의존성:** 없음

**포함 기능:**
- 맵 노드 그래프
- 서브그리드 (L3 Depth)
- 바이옴 정의 및 속성
- 노드 간 이동 경로
- 기본 지형 효과

**데이터 모델:**
```python
class MapNode:
    node_id: str
    biome: BiomeType
    connected_nodes: List[str]
    subgrid: Optional[SubGrid]
    facilities: List[Facility]
```

---

#### [B] time_core

**역할:** 시간 경과, 시간대, 계절 관리

**의존성:** 없음

**포함 기능:**
- 게임 턴/시간 관리
- 시간대 (Dawn, Morning, Afternoon, Evening, Night)
- 계절 변화
- 시간 기반 이벤트 트리거

**데이터 모델:**
```python
class TimeOfDay(str, Enum):
    DAWN = "Dawn"           # 04~08
    MORNING = "Morning"     # 08~12
    AFTERNOON = "Afternoon" # 12~16
    EVENING = "Evening"     # 16~20
    NIGHT = "Night"         # 20~04

class GameTime:
    turn: int
    hour: int
    day: int
    season: Season
```

---

#### [C] npc_core

**역할:** 배경인물 슬롯, NPC 결정화, NPC 저장

**의존성:** 없음

**포함 기능:**
- 배경인물 슬롯 시스템 (거주형)
- 승격 점수 관리
- NPC 결정화 (이름, HEXACO, CharacterSheet)
- NPC DB 영속화

**데이터 모델:**
```python
class BackgroundCharacterSlot:
    slot_id: str
    node_id: str
    role: str
    promotion_score: int
    name_seed: NPCNameSeed

class NPC:
    npc_id: str
    full_name: NPCFullName
    hexaco: Dict[str, float]  # 0.0~1.0
    character_sheet: CharacterSheet
    axiom_proficiencies: Dict[str, int]  # 0~100
```

---

#### [D] item_core

**역할:** 아이템 프로토타입/인스턴스 관리

**의존성:** 없음

**포함 기능:**
- 아이템 프로토타입 정의
- 아이템 인스턴스 생성/관리
- 소유권 다형성 (player, node, container, npc)
- 8대 공명 저항력

**데이터 모델:**
```python
class ItemPrototype:
    proto_id: str
    name: str
    item_type: ItemType
    resonance_shield: ResonanceShield
    axiom_tags: List[str]

class ItemInstance:
    instance_id: str
    proto_id: str
    owner_type: str  # "player" | "node" | "container" | "npc"
    owner_id: str
    current_states: List[str]
```

---

### 3.3 Layer 2: 오버레이 시스템

#### [E] overlay_core

**역할:** 오버레이 기반 인터페이스 및 병합 시스템

**의존성:** geography

**포함 기능:**
- BaseOverlay 인터페이스
- OverlayManager (병합, 충돌 처리)
- 노드별 효과 조회
- 창발적 효과 생성

**데이터 모델:**
```python
class BaseOverlay(ABC):
    overlay_id: str
    overlay_type: OverlayType
    priority: int
    affected_nodes: Set[str]
    is_active: bool
    severity: float  # 0.0~1.0

class OverlayEffects:
    weather_override: Optional[str]
    dialogue_tags: List[str]
    encounter_bias: Dict[str, float]
    economy_modifier: Dict[str, float]
    narrative_tags: List[str]

class MergedEffects:
    # 병합된 최종 효과
    weather: Optional[str]
    dialogue_tags: List[str]
    encounter_bias: Dict[str, float]
    economy_modifier: Dict[str, float]
    emergent_effects: Dict[str, Any]  # 충돌로 인한 창발적 효과
```

---

#### [F] weather_overlay

**역할:** 날씨 시스템

**의존성:** overlay_core, time_core

**포함 기능:**
- Global 날씨 상태
- 바이옴별 Local 해석
- 시간/계절에 따른 날씨 변화
- 날씨 효과 (이동 비용, 조우 확률)

---

#### [G] territory_overlay

**역할:** 영유권 시스템

**의존성:** overlay_core

**포함 기능:**
- 영역 소유권 정의
- 정책 적용 (세금, 통행료)
- 다중 노드 영역 관리
- 중첩 우선순위

---

#### [H] quest_overlay

**역할:** 퀘스트가 월드에 미치는 영향권

**의존성:** overlay_core

**포함 기능:**
- 퀘스트 활성화 시 오버레이 생성
- severity 기반 영향권 확장/축소
- NPC 대화 태그 주입
- 경제/조우 수정자

**데이터 모델:**
```python
class QuestOverlay(BaseOverlay):
    quest_id: str
    quest_title: str
    severity_growth_rate: float  # 방치 시 증가율
    severity_decay_rate: float   # 해결 시 감소율
    effects_template: Dict[str, Any]
```

---

#### [I] event_overlay

**역할:** 일시적 이벤트 (축제, 재난)

**의존성:** overlay_core

**포함 기능:**
- 시간 제한 이벤트
- 자동 만료
- 특수 조우/상점

---

### 3.4 Layer 3: 상호작용 모듈

#### [J] dialogue

**역할:** NPC 대화 시스템

**의존성:** npc_core

**포함 기능:**
- 대화 컨텍스트 생성
- HEXACO → 톤 태그 변환
- LLM 대화 생성
- 대화 결과 처리

**데이터 모델:**
```python
class ToneContext:
    emotion: str
    emotion_intensity: float
    manner_tags: List[str]
    attitude_tags: List[str]
    intent: str

class DialogueContext:
    npc: NPC
    tone: ToneContext
    overlay_tags: List[str]  # 오버레이에서 주입
    relationship: Optional[Relationship]
    relevant_memories: List[NPCMemory]
```

---

#### [K] memory

**역할:** NPC 기억 시스템

**의존성:** npc_core

**포함 기능:**
- 3계층 기억 (Tier 1/2/3)
- 기억 생성/검색
- 로컬 embedding (sentence-transformers)
- 기억 승격/강등

**데이터 모델:**
```python
class NPCMemory:
    memory_id: str
    npc_id: str
    tier: int  # 1, 2, 3
    summary: str
    embedding: Optional[List[float]]
    importance: float
    emotional_valence: float
    turn_created: int
    is_fixed: bool  # Tier 1 고정 슬롯 여부
```

---

#### [L] relationship

**역할:** NPC-PC 관계 시스템

**의존성:** npc_core

**포함 기능:**
- 관계 수치 (호감도, 신뢰도, 친밀도)
- 관계 상태 전이
- 관계 기반 기억 용량 결정

**데이터 모델:**
```python
class Relationship:
    relationship_id: str
    source_id: str
    target_id: str
    affinity: float      # -100 ~ +100
    trust: float         # 0 ~ 100
    familiarity: int     # 상호작용 횟수
    status: RelationshipStatus  # stranger, acquaintance, friend, ...
    tags: List[str]      # ["debt_owed", "life_saved", ...]
```

---

#### [M] combat

**역할:** 전투 시스템

**의존성:** item_core, geography

**포함 기능:**
- d6 Dice Pool 전투 판정
- 8대 공명 피해 시스템
- 적대형 개체 추적 (CombatTracker)
- 도주/생존 시 영속화

---

#### [N] crafting

**역할:** 제작 시스템

**의존성:** item_core

**포함 기능:**
- 공리 조합 판정
- 통합 판정 공식 (기하평균)
- 품질 등급 결정
- 장비/협력자/상황 보정

---

### 3.5 Layer 4: 고급 시스템

#### [O] quest_engine

**역할:** 퀘스트 생성 및 관리

**의존성:** quest_overlay, npc_core, dialogue

**포함 기능:**
- 퀘스트 생성 (대화에서 자연 발생)
- 퀘스트 상태 관리
- 연작 퀘스트/캠페인
- quest_overlay 자동 생성

---

#### [P] npc_behavior

**역할:** NPC 자율 행동

**의존성:** npc_core, time_core

**포함 기능:**
- Phase A: 역할 기반 스케줄
- Phase B: 욕구 시스템 (7종)
- Phase C: 완전 자율 + 충성/반란

**욕구 목록:**
| 계층 | 욕구 |
|------|------|
| 생존 | Hunger, Fatigue, Safety |
| 경제 | Profit |
| 사회 | Social, Belonging |
| 자아 | Achievement |

---

#### [Q] worldpool

**역할:** 유랑형/적대형 재조우 시스템

**의존성:** npc_core, geography

**포함 기능:**
- WorldPool 관리 (유랑형 10개, 적대형 10개)
- 재조우 확률 계산 (승격 점수 + 거리)
- 점수 감쇠 + 풀 크기 제한

---

#### [R] economy

**역할:** 경제 시스템

**의존성:** item_core, npc_core, territory_overlay

**포함 기능:**
- 상점/거래
- 세금 시스템
- 오버레이 경제 수정자 적용

---

## 4. 모듈 인터페이스

### 4.1 기반 인터페이스

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class GameModule(ABC):
    """모든 모듈의 기반 인터페이스"""
    
    name: str
    enabled: bool = False
    dependencies: List[str] = []
    
    @abstractmethod
    def on_enable(self) -> None:
        """모듈 활성화 시 초기화"""
        pass
    
    @abstractmethod
    def on_disable(self) -> None:
        """모듈 비활성화 시 정리"""
        pass
    
    @abstractmethod
    def on_turn(self, context: "GameContext") -> None:
        """턴 진행 시 처리"""
        pass
    
    @abstractmethod
    def on_node_enter(self, node_id: str, context: "GameContext") -> None:
        """노드 진입 시 처리"""
        pass
    
    @abstractmethod
    def get_available_actions(self, context: "GameContext") -> List["Action"]:
        """현재 상황에서 가능한 행동 반환"""
        pass
```

### 4.2 모듈 관리자

```python
class ModuleManager:
    """모듈 토글 및 관리"""
    
    modules: Dict[str, GameModule] = {}
    
    def register(self, module: GameModule) -> None:
        """모듈 등록"""
        self.modules[module.name] = module
    
    def enable(self, name: str) -> bool:
        """모듈 활성화 (의존성 체크 포함)"""
        module = self.modules.get(name)
        if not module:
            return False
        
        # 의존성 체크
        for dep in module.dependencies:
            if dep not in self.modules or not self.modules[dep].enabled:
                logging.warning(f"의존성 미충족: {name} requires {dep}")
                return False
        
        module.enabled = True
        module.on_enable()
        logging.info(f"모듈 활성화: {name}")
        return True
    
    def disable(self, name: str) -> None:
        """모듈 비활성화"""
        module = self.modules.get(name)
        if module and module.enabled:
            # 이 모듈에 의존하는 모듈 먼저 비활성화
            for other in self.modules.values():
                if name in other.dependencies and other.enabled:
                    self.disable(other.name)
            
            module.on_disable()
            module.enabled = False
            logging.info(f"모듈 비활성화: {name}")
    
    def process_turn(self, context: "GameContext") -> None:
        """모든 활성 모듈의 턴 처리"""
        for module in self.modules.values():
            if module.enabled:
                module.on_turn(context)
    
    def process_node_enter(self, node_id: str, context: "GameContext") -> None:
        """모든 활성 모듈의 노드 진입 처리"""
        for module in self.modules.values():
            if module.enabled:
                module.on_node_enter(node_id, context)
    
    def get_all_actions(self, context: "GameContext") -> List["Action"]:
        """모든 활성 모듈에서 가능한 행동 수집"""
        actions = []
        for module in self.modules.values():
            if module.enabled:
                actions.extend(module.get_available_actions(context))
        return actions
```

### 4.3 모듈 간 이벤트 통신

#### 원칙

architecture.md의 "서비스 간 직접 호출 금지" 원칙을 모듈에도 적용한다.

- 모듈은 다른 모듈을 직접 import하거나 호출하지 않는다
- 모듈 간 통신은 EventBus를 경유한다
- 이벤트는 식별자(ID)만 전달한다

#### 이벤트 흐름 예시

**NPC 승격 시**:
```
npc_core.promote_to_npc()
    → emit("npc_promoted", {npc_id, origin_type})
    
memory 모듈 구독 → create_initial_memory()
relationship 모듈 구독 → create_initial_relationship()
```

**퀘스트 생성 시**:
```
quest_engine.create_quest()
    → emit("quest_created", {quest_id, affected_nodes})
    
overlay_core 모듈 구독 → create_quest_overlay()
```

#### 허용되는 의존

| 방향 | 예시 | 허용 |
|------|------|------|
| Module → Core | npc_core → core/dice | ✅ |
| Module → DB | npc_core → db/models | ✅ |
| Module → EventBus | npc_core → event_bus | ✅ |
| Module → Module | npc_core → relationship | ❌ |

---

## 5. 노드 진입 처리 흐름

```python
def on_node_enter(player: Player, node_id: str) -> NodeContext:
    """노드 진입 시 전체 처리 흐름"""
    
    # 1. 기반 지리 정보 (geography 모듈)
    geography = modules.geography.get_node(node_id)
    
    # 2. 오버레이 효과 병합 (overlay_core 모듈)
    overlay_effects = MergedEffects()
    if modules.overlay_core.enabled:
        overlay_effects = modules.overlay_core.get_merged_effects(node_id)
    
    # 3. NPC 목록 (npc_core 모듈)
    npcs = []
    if modules.npc_core.enabled:
        npcs = modules.npc_core.get_npcs_at_node(node_id)
        # 오버레이 태그 주입
        for npc in npcs:
            npc.dialogue_context.overlay_tags = overlay_effects.dialogue_tags
    
    # 4. 조우 판정 (combat 모듈)
    encounter = None
    if modules.combat.enabled:
        encounter = modules.combat.roll_encounter(
            node_id,
            geography.base_encounters,
            overlay_effects.encounter_bias
        )
    
    # 5. 서술 컨텍스트 생성
    narrative_context = NarrativeContext(
        geography=geography,
        weather=overlay_effects.weather or geography.default_weather,
        narrative_tags=overlay_effects.narrative_tags,
        emergent_effects=overlay_effects.emergent_effects,
        npcs=npcs,
        encounter=encounter,
    )
    
    # 6. AI 서술 생성 (Core)
    description = narrative_service.describe_node(narrative_context)
    
    return NodeContext(
        geography=geography,
        overlay_effects=overlay_effects,
        npcs=npcs,
        encounter=encounter,
        description=description,
    )
```

---

## 6. 개발 로드맵

### Phase 1: Core 확인 + 기반 모듈 (1~2주)

```
목표: 모듈 시스템 구축 + 기반 4개 완성

Week 1:
- ModuleManager 구현
- [A] geography 모듈
- [B] time_core 모듈

Week 2:
- [C] npc_core 모듈
- [D] item_core 모듈
- 통합 테스트
```

### Phase 2: 오버레이 시스템 (1~2주)

```
목표: 오버레이 기반 구조 완성

Week 3:
- [E] overlay_core 모듈
- [H] quest_overlay 모듈

Week 4:
- [F] weather_overlay 모듈
- [G] territory_overlay 모듈
- 오버레이 병합 테스트
```

### Phase 3: 핵심 상호작용 (2주)

```
목표: "대화하고 관계 맺기" 검증

Week 5:
- [J] dialogue 모듈
- [K] memory 모듈 (Tier 1만)

Week 6:
- [L] relationship 모듈
- 핵심 루프 검증
```

### Phase 4: 게임플레이 (2주)

```
목표: "전투하고 퀘스트 수행" 검증

Week 7:
- [M] combat 모듈
- [O] quest_engine 모듈 (단순 버전)

Week 8:
- [N] crafting 모듈
- 통합 테스트
```

### Phase 5: 고급 시스템 (이후)

```
목표: 세계 깊이 추가

Week 9~:
- [P] npc_behavior (Phase A → B)
- [Q] worldpool
- [R] economy
- 나머지 모듈 순차 추가
```

---

## 7. 테스트 전략

### 7.1 모듈별 격리 테스트

각 모듈은 해당 모듈만 활성화한 상태에서 테스트한다.

**예시: [C] npc_core만 활성화**

```python
def test_npc_core_only():
    manager = ModuleManager()
    manager.register(NPCCoreModule())
    manager.enable("npc_core")
    
    # 테스트
    # - 여관 진입 → 배경인물 슬롯에 인물 존재 확인
    # - 말 걸기 → 승격 점수 증가 확인
    # - 임계값 도달 → NPC 생성 확인
    # - DB 저장/로드 확인
    
    # 다른 모듈 OFF이므로:
    # - 대화 내용 없음 (기본 서술만)
    # - 기억 없음
    # - 관계 수치 없음
```

### 7.2 모듈 조합 테스트

의존 관계에 따라 모듈을 조합하여 테스트한다.

**예시: npc_core + dialogue + memory**

```python
def test_npc_dialogue_memory():
    manager = ModuleManager()
    manager.register(NPCCoreModule())
    manager.register(DialogueModule())
    manager.register(MemoryModule())
    
    manager.enable("npc_core")
    manager.enable("dialogue")
    manager.enable("memory")
    
    # 테스트
    # - NPC와 대화 → 톤 태그 생성 확인
    # - 대화 후 기억 생성 확인
    # - 재대화 시 기억 참조 확인
```

### 7.3 전체 통합 테스트

모든 모듈 활성화 상태에서 E2E 시나리오 테스트.

---

## 8. 파일 구조

```
src/
├── core/
│   ├── game_loop.py          # Core 게임 루프
│   └── module_manager.py     # 모듈 관리자
├── modules/
│   ├── base.py               # GameModule ABC
│   ├── geography/
│   │   ├── __init__.py
│   │   ├── module.py         # GeographyModule
│   │   └── models.py
│   ├── time_core/
│   ├── npc_core/
│   ├── item_core/
│   ├── overlay_core/
│   ├── weather_overlay/
│   ├── territory_overlay/
│   ├── quest_overlay/
│   ├── event_overlay/
│   ├── dialogue/
│   ├── memory/
│   ├── relationship/
│   ├── combat/
│   ├── crafting/
│   ├── quest_engine/
│   ├── npc_behavior/
│   ├── worldpool/
│   └── economy/
├── services/
│   └── narrative_service.py  # AI 서술 (Core)
└── db/
    └── models.py             # DB 모델
```

---

## 9. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2025-02-07 | 최초 작성 |
