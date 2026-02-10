# NPC 모듈 구현 지시서 패키지

5개 블록으로 분할. 각 블록은 **독립 실행 + 독립 테스트** 가능.
앞 블록의 커밋이 완료된 상태에서 다음 블록을 실행할 것.

---

# 지시서 #08-A: NPC Core 데이터 모델 + HEXACO 생성

**예상 시간**: 20분  
**선행**: 지시서 #07 (models_v2.py) 완료

## 참조 문서 (반드시 읽을 것)

- `docs/20_design/npc-system.md` — 섹션 2 (배경 존재), 섹션 8 (HEXACO), 섹션 11 (공명/숙련도), 섹션 13 (완전 데이터 모델)
- `docs/30_technical/db-schema-v2.md` — 섹션 2 (NPC 테이블군)
- `src/db/models_v2.py` — 이미 구현된 ORM 모델 확인
- `src/modules/base.py` — GameModule ABC 확인
- `src/core/event_bus.py` — GameEvent, EventBus 인터페이스 확인

## 작업 내용

### 1. Core 도메인 모델 생성

**파일**: `src/core/npc/models.py`

DB 모델(ORM)과 별개로, Core 레이어에서 사용하는 순수 데이터 클래스를 정의한다.
Core는 DB를 모르므로, 여기서는 SQLAlchemy를 import하지 않는다.

```python
"""NPC Core 도메인 모델

npc-system.md 섹션 2, 8, 13 대응.
DB 무관 순수 데이터 클래스.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
```

구현할 클래스:

| 클래스 | 출처 | 비고 |
|--------|------|------|
| `EntityType(str, Enum)` | 섹션 2.1 | "resident", "wanderer", "hostile" |
| `BackgroundEntity` (dataclass) | 섹션 2.2 | entity_id, entity_type, current_node, home_node, role, appearance_seed, promotion_score, promoted, name_seed, slot_id, temp_combat_id, created_turn |
| `BackgroundSlot` (dataclass) | 섹션 3.5 | slot_id, node_id, facility_id, facility_type, role, is_required, entity_id, reset_interval, last_reset_turn |
| `HEXACO` (dataclass) | 섹션 8.1 | H, E, X, A, C, O (전부 float) |
| `NPCData` (dataclass) | 섹션 13 | npc_id, full_name, given_name, hexaco, character_sheet, resonance_shield, axiom_proficiencies, home_node, current_node, routine, state, lord_id, faction_id, loyalty, currency, origin_type, origin_entity_type, role, tags |

**규칙**:
- Pydantic이 아닌 `dataclass` 사용 (Core 레이어는 외부 의존성 최소화)
- JSON 직렬화가 필요한 필드(full_name, hexaco 등)는 `Dict` 또는 전용 dataclass 타입
- `__init__.py`에 공개 API export

### 2. HEXACO 생성 로직

**파일**: `src/core/npc/hexaco.py`

```python
"""HEXACO 성격 생성 및 행동 매핑

npc-system.md 섹션 8 대응.
"""
```

구현할 함수/상수:

| 항목 | 출처 |
|------|------|
| `ROLE_HEXACO_TEMPLATES: Dict[str, Dict[str, float]]` | 섹션 8.3 (7개 역할 템플릿) |
| `generate_hexaco(role: str, seed: Optional[int] = None) -> HEXACO` | 섹션 8.3 (±0.15 랜덤, 0.0~1.0 클램프) |
| `HEXACO_BEHAVIOR_MAP: Dict[str, Dict[str, Dict[str, Any]]]` | 섹션 8.4 전체 테이블 |
| `get_behavior_modifier(hexaco: HEXACO, factor: str, modifier: str) -> Any` | 섹션 8.4 하단 |

**seed 파라미터**: 테스트 재현성을 위해 `random.Random(seed)`로 로컬 RNG 사용.

### 3. 톤 태그 생성 로직

**파일**: `src/core/npc/tone.py`

```python
"""HEXACO → 톤 태그 변환

npc-system.md 섹션 9 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `ToneContext` (dataclass) | 섹션 9.2 |
| `derive_manner_tags(hexaco: HEXACO) -> List[str]` | 섹션 9.3 |
| `EVENT_EMOTION_MAP: Dict[str, str]` | 섹션 9.4 |
| `calculate_emotion(event: str, affinity: float, hexaco: HEXACO) -> Tuple[str, float]` | 섹션 9.4 (relationship 대신 affinity float 받기 — 모듈 간 직접 의존 방지) |

### 4. 패키지 구조

```
src/core/npc/
    __init__.py          # 공개 API export
    models.py            # 도메인 모델
    hexaco.py            # HEXACO 생성 + 행동 매핑
    tone.py              # 톤 태그 생성
```

### 5. 테스트

**파일**: `tests/test_npc_core.py`

```python
"""NPC Core 도메인 모델, HEXACO, 톤 태그 테스트"""
```

테스트 항목:

- `test_entity_type_enum`: EntityType 3종 값 확인
- `test_background_entity_creation`: BackgroundEntity 기본 생성
- `test_hexaco_generate_with_seed`: 동일 seed → 동일 결과
- `test_hexaco_generate_clamp`: 모든 값이 0.0~1.0 범위
- `test_hexaco_known_role`: "innkeeper" 템플릿 기반 생성 확인 (X > 0.5 등)
- `test_hexaco_unknown_role`: 미등록 역할 → 중립 0.5 기반
- `test_behavior_modifier_high`: H=0.8 → lie_chance 낮음
- `test_behavior_modifier_low`: H=0.2 → lie_chance 높음
- `test_derive_manner_tags`: X=0.9 → "verbose", "energetic" 포함
- `test_calculate_emotion_basic`: "betrayed" → "angry", intensity 높음
- `test_calculate_emotion_hexaco_modulation`: A=0.8 → angry 강도 약화

### 6. 검증 및 커밋

```bash
ruff check src/core/npc/ tests/test_npc_core.py
pytest tests/test_npc_core.py -v
pytest tests/ -v  # 기존 테스트 무파손
git add src/core/npc/ tests/test_npc_core.py
git commit -m "feat(npc): add core domain models, HEXACO generation, tone tags

- EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData
- Role-based HEXACO generation with seed support
- HEXACO behavior modifier mapping
- Tone tag derivation (manner_tags, emotion calculation)

Ref: npc-system.md sections 2, 8, 9, 13"
```

---

# 지시서 #08-B: 승격 시스템 + 슬롯 시스템

**예상 시간**: 20분  
**선행**: #08-A 완료

## 참조 문서

- `docs/20_design/npc-system.md` — 섹션 3 (슬롯), 섹션 4 (승격), 섹션 7 (명명)
- `src/core/npc/models.py` — #08-A에서 만든 도메인 모델
- `src/db/models_v2.py` — BackgroundEntityModel, BackgroundSlotModel, NPCModel

## 작업 내용

### 1. 슬롯 관리 로직

**파일**: `src/core/npc/slots.py`

```python
"""배경인물 슬롯 시스템

npc-system.md 섹션 3 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `FACILITY_BASE_SLOTS: Dict[str, int]` | 섹션 3.3 (7개 시설 기본 슬롯) |
| `FACILITY_REQUIRED_ROLES: Dict[str, List[str]]` | 섹션 3.1 기반 (시설별 필수 역할 매핑) |
| `calculate_slot_count(facility_type: str, facility_size: int) -> int` | 섹션 3.3 |
| `should_reset_slot(promotion_score: int, turns_since_reset: int, reset_interval: int) -> bool` | 섹션 3.4 |

### 2. 승격 시스템

**파일**: `src/core/npc/promotion.py`

```python
"""배경인물 → NPC 승격 시스템

npc-system.md 섹션 4 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `PROMOTION_THRESHOLD = 50` | 섹션 4.1 |
| `WORLDPOOL_THRESHOLD = 15` | 섹션 4.1 |
| `PROMOTION_SCORE_TABLE: Dict[str, int]` | 섹션 4.2 전체 테이블 (10종 행동) |
| `calculate_new_score(current_score: int, action: str) -> int` | 점수 계산 (순수 함수) |
| `check_promotion_status(score: int) -> str` | "none" / "worldpool" / "promoted" 반환 |
| `build_npc_from_entity(entity: BackgroundEntity, hexaco: HEXACO) -> NPCData` | 섹션 4.3 — 엔티티 → NPCData 변환. DB 저장/이벤트 발행은 하지 않음 (Service 책임) |

**중요**: `build_npc_from_entity`는 순수 변환 함수다. UUID 생성, DB 저장, EventBus emit은 포함하지 않는다. 이것들은 Service 레이어(#08-D)에서 처리.

### 3. 명명 시스템 (기초)

**파일**: `src/core/npc/naming.py`

```python
"""NPC 명명 시스템

npc-system.md 섹션 7 대응.
Alpha 단계: 간단한 이름 풀 기반 생성.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `NPCNameSeed` (dataclass) | 섹션 7.1 |
| `NPCFullName` (dataclass) | 섹션 7.2 |
| `NAME_POOLS: Dict[str, List[str]]` | 섹션 7.3 기반 — given_names, family_names 각 20개 이상 |
| `generate_name(seed: Optional[NPCNameSeed] = None, rng_seed: Optional[int] = None) -> NPCFullName` | 이름 풀에서 랜덤 선택 |

### 4. 테스트

**파일**: `tests/test_npc_promotion.py`

- `test_promotion_score_table`: 전체 10종 행동 점수 확인
- `test_check_promotion_status_none`: 14점 → "none"
- `test_check_promotion_status_worldpool`: 15점 → "worldpool"
- `test_check_promotion_status_promoted`: 50점 → "promoted"
- `test_build_npc_from_entity`: BackgroundEntity → NPCData 변환, 필드 매핑 확인
- `test_slot_count_calculation`: inn → 4 + size 보정
- `test_should_reset_slot_protected`: promotion_score > 0 → False
- `test_should_reset_slot_expired`: 24턴 경과 → True
- `test_generate_name_with_seed`: 동일 seed → 동일 이름
- `test_generate_name_structure`: given_name, family_name 존재 확인

### 5. 검증 및 커밋

```bash
ruff check src/core/npc/ tests/test_npc_promotion.py
pytest tests/test_npc_promotion.py -v
pytest tests/ -v
git add src/core/npc/slots.py src/core/npc/promotion.py src/core/npc/naming.py tests/test_npc_promotion.py
git commit -m "feat(npc): add promotion system, slot management, naming

- Promotion score table (10 actions), threshold checks
- Slot calculation per facility type, reset rules
- Name pool based generation with seed support
- build_npc_from_entity pure transformation

Ref: npc-system.md sections 3, 4, 7"
```

---

# 지시서 #08-C: NPC 기억 시스템

**예상 시간**: 20분  
**선행**: #08-A 완료 (B와는 독립, 병행 불가하지만 순서 유연)

## 참조 문서

- `docs/20_design/npc-system.md` — 섹션 10 (기억 시스템)
- `src/db/models_v2.py` — NPCMemoryModel

## 작업 내용

### 1. 기억 Core 로직

**파일**: `src/core/npc/memory.py`

```python
"""NPC 기억 시스템

npc-system.md 섹션 10 대응.
Alpha: Tier 1 + Tier 2. Tier 3 (embedding)은 Alpha 후.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `IMPORTANCE_TABLE: Dict[str, float]` | 섹션 10.5 (7종 상호작용 → importance) |
| `TIER2_CAPACITY: Dict[str, int]` | 섹션 10.3 (관계 단계별 Tier 2 상한) |
| `NPCMemory` (dataclass) | 섹션 10.4 — Core용 (embedding 필드는 Optional[bytes]) |
| `create_memory(npc_id, memory_type, summary, turn, importance=None, emotional_valence=0.0) -> NPCMemory` | 기억 생성 (importance 자동 계산) |
| `assign_tier1_slot(memories: List[NPCMemory], new_memory: NPCMemory) -> Optional[NPCMemory]` | Tier 1 슬롯 배치. 고정 2 + 교체 3. 교체 시 밀려나는 기억 반환 (→ Tier 2로 강등) |
| `enforce_tier2_capacity(memories: List[NPCMemory], relationship_status: str) -> List[NPCMemory]` | 관계 단계별 상한 초과 시 가장 오래된 것 → Tier 3 강등. 강등 대상 리스트 반환 |
| `get_memories_for_context(all_memories: List[NPCMemory], relationship_status: str) -> List[NPCMemory]` | LLM 컨텍스트용 기억 선택: Tier 1 전부 + Tier 2 전부 (Tier 3 제외) |

### 2. 테스트

**파일**: `tests/test_npc_memory.py`

- `test_importance_auto_assign`: memory_type="betrayal" → importance=0.95
- `test_tier1_fixed_slots`: 고정 슬롯(1,2)은 교체 불가
- `test_tier1_replacement`: 교체 슬롯 3개 꽉 찬 상태에서 새 기억 → 가장 오래된 것 반환
- `test_tier2_capacity_stranger`: stranger → 상한 3, 4개 기억 시 1개 강등 대상
- `test_tier2_capacity_friend`: friend → 상한 15
- `test_get_memories_for_context`: Tier 1+2만 반환, Tier 3 제외
- `test_create_memory_defaults`: 기본값 확인 (valence=0.0 등)

### 3. 검증 및 커밋

```bash
ruff check src/core/npc/memory.py tests/test_npc_memory.py
pytest tests/test_npc_memory.py -v
pytest tests/ -v
git add src/core/npc/memory.py tests/test_npc_memory.py
git commit -m "feat(npc): add memory system (Tier 1 + Tier 2)

- Importance auto-calculation from interaction type
- Tier 1 slot management (fixed 2 + rotating 3)
- Tier 2 capacity enforcement per relationship status
- Context memory selection for LLM prompt

Ref: npc-system.md section 10"
```

---

# 지시서 #08-D: NPC Service (DB 연동 + EventBus)

**예상 시간**: 25분  
**선행**: #08-A, #08-B, #08-C 전부 완료

## 참조 문서

- `docs/20_design/npc-system.md` — 섹션 14 (API 인터페이스, 이벤트)
- `docs/30_technical/architecture.md` — Service 레이어 규칙
- `docs/30_technical/event-bus.md` — npc_core 관련 이벤트
- `src/modules/base.py` — GameModule ABC, GameContext
- `src/core/event_bus.py` — EventBus, GameEvent
- `src/db/models_v2.py` — BackgroundEntityModel, BackgroundSlotModel, NPCModel, NPCMemoryModel, WorldPoolModel

## 작업 내용

### 1. NPC Service

**파일**: `src/services/npc_service.py`

```python
"""NPC Service — Core 로직과 DB를 연결

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""
```

구현할 메서드:

| 메서드 | 역할 |
|--------|------|
| `__init__(self, db_session, event_bus)` | DI |
| `get_background_entities_at_node(node_id) -> List[BackgroundEntity]` | DB 조회 → Core 모델 변환 |
| `get_npcs_at_node(node_id) -> List[NPCData]` | DB 조회 → Core 모델 변환 |
| `get_npc_by_id(npc_id) -> Optional[NPCData]` | 단일 NPC 조회 |
| `add_promotion_score(entity_id, action) -> str` | 점수 추가 → "none"/"worldpool"/"promoted" 반환. promoted면 승격 실행 |
| `_promote_entity(entity_id) -> NPCData` | 내부: 승격 처리 — HEXACO 생성, 이름 생성, NPCModel 저장, background_entities.promoted=True, EventBus npc_promoted 발행 |
| `_register_worldpool(entity_id)` | 내부: WorldPool 등록 |
| `create_npc_for_quest(role, node_id) -> NPCData` | 퀘스트용 NPC 직접 생성, EventBus npc_created 발행 |
| `save_memory(npc_id, memory_type, summary, turn, emotional_valence) -> NPCMemory` | 기억 저장 + Tier 관리 |
| `get_memories_for_context(npc_id, relationship_status) -> List[NPCMemory]` | LLM 컨텍스트용 기억 |

**ORM ↔ Core 변환 헬퍼**: Service 내부에 `_entity_from_orm(model) -> BackgroundEntity`, `_npc_from_orm(model) -> NPCData` 등 변환 함수를 private으로 구현.

### 2. event_types.py 생성

**파일**: `src/core/event_types.py`

event-bus.md 섹션 6의 EventTypes 클래스를 구현한다. **npc_core 관련 4개만 먼저 정의하고**, 나머지는 각 모듈 구현 시 추가:

```python
class EventTypes:
    # npc_core
    NPC_PROMOTED = "npc_promoted"
    NPC_CREATED = "npc_created"
    NPC_DIED = "npc_died"
    NPC_MOVED = "npc_moved"

    # engine
    TURN_PROCESSED = "turn_processed"

    # (나머지는 해당 모듈 구현 시 추가)
```

### 3. 테스트

**파일**: `tests/test_npc_service.py`

인메모리 SQLite + EventBus mock으로 통합 테스트:

```python
@pytest.fixture
def setup():
    """인메모리 DB + EventBus + NPC Service"""
    engine = create_engine("sqlite:///:memory:")
    # PRAGMA foreign_keys=ON
    Base.metadata.create_all(engine)
    session = Session(engine)
    bus = EventBus()
    service = NPCService(session, bus)
    return service, session, bus
```

테스트 항목:

- `test_create_background_entity_and_query`: 엔티티 생성 → get_background_entities_at_node 조회
- `test_promotion_flow`: 엔티티 생성 → add_promotion_score("ask_name") → 즉시 승격 → NPCModel 존재 확인 + promoted=True
- `test_promotion_event_emitted`: 승격 시 EventBus에 npc_promoted 이벤트 수신 확인
- `test_worldpool_registration`: 15점 이상 wanderer → WorldPool 레코드 존재
- `test_create_npc_for_quest`: 퀘스트용 NPC 생성 → npc_created 이벤트 확인
- `test_save_and_get_memories`: 기억 저장 → 컨텍스트 조회 → Tier 1+2만 반환
- `test_tier1_slot_management_via_service`: 고임팩트 기억 6개 저장 → 고정 2 + 교체 3 + 강등 1

### 4. 검증 및 커밋

```bash
ruff check src/services/npc_service.py src/core/event_types.py tests/test_npc_service.py
pytest tests/test_npc_service.py -v
pytest tests/ -v
git add src/services/npc_service.py src/core/event_types.py src/core/npc/__init__.py tests/test_npc_service.py
git commit -m "feat(npc): add NPC service with DB integration and EventBus

- NPCService: CRUD, promotion flow, WorldPool, memory management
- ORM ↔ Core model conversion
- EventTypes constants (npc_core subset)
- Integration tests with in-memory SQLite

Ref: npc-system.md section 14, architecture.md, event-bus.md"
```

---

# 지시서 #08-E: NPCCoreModule (GameModule 래핑)

**예상 시간**: 15분  
**선행**: #08-D 완료

## 참조 문서

- `docs/20_design/npc-system.md` — 섹션 14.1 (NPCCoreModule 인터페이스)
- `src/modules/base.py` — GameModule ABC
- `src/modules/module_manager.py` — ModuleManager
- `docs/30_technical/event-bus.md` — npc_core 구독 이벤트

## 작업 내용

### 1. NPCCoreModule

**파일**: `src/modules/npc/module.py`

```python
"""NPC Core 모듈 — GameModule 인터페이스 구현

npc-system.md 섹션 14.1 대응.
NPCService를 래핑하여 ModuleManager에 등록.
"""
```

구현:

```python
class NPCCoreModule(GameModule):
    name = "npc_core"
    dependencies = []  # Phase 2 Alpha: 의존 없음

    def initialize(self, context: GameContext) -> None:
        """EventBus 구독 등록, NPCService 초기화"""
        self.service = NPCService(context.db_session, context.event_bus)
        context.event_bus.subscribe(EventTypes.NPC_NEEDED, self._handle_npc_needed)
        # combat_entity_survived는 Phase 3

    def process_turn(self, context: GameContext) -> None:
        """턴 처리: 슬롯 리셋 체크 등"""
        pass  # Alpha 최소: 슬롯 리셋은 후속 구현

    def shutdown(self, context: GameContext) -> None:
        pass

    # --- 공개 API (다른 모듈이 EventBus 없이 사용 가능한 조회 메서드) ---
    def get_npcs_at_node(self, node_id: str) -> list:
        return self.service.get_npcs_at_node(node_id)

    def get_background_entities_at_node(self, node_id: str) -> list:
        return self.service.get_background_entities_at_node(node_id)

    def get_npc_by_id(self, npc_id: str):
        return self.service.get_npc_by_id(npc_id)

    # --- EventBus 핸들러 ---
    def _handle_npc_needed(self, event: GameEvent) -> None:
        role = event.data["npc_role"]
        node_id = event.data["node_id"]
        self.service.create_npc_for_quest(role, node_id)
```

### 2. 패키지 구조

```
src/modules/npc/
    __init__.py          # NPCCoreModule export
    module.py            # GameModule 구현
```

### 3. ModuleManager 등록 테스트

**파일**: `tests/test_npc_module.py`

- `test_module_register_and_initialize`: ModuleManager에 등록 → initialize 성공
- `test_npc_needed_event_handling`: npc_needed 이벤트 발행 → NPC 생성 확인
- `test_public_api_after_init`: initialize 후 get_npcs_at_node 호출 가능

### 4. SRC_INDEX.md 갱신

아래 항목 추가:

```markdown
## modules/npc/ - NPC 모듈

### modules/npc/module.py
- **목적:** NPCCoreModule — GameModule 인터페이스 구현
- **핵심:** NPCService 래핑, EventBus 구독 (npc_needed), 공개 조회 API 제공
- **의존:** services/npc_service.py, core/npc/

## core/npc/ - NPC Core 로직

### core/npc/models.py
- **목적:** NPC 도메인 모델 (DB 무관)
- **핵심:** EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData

### core/npc/hexaco.py
- **목적:** HEXACO 생성 + 행동 매핑
- **핵심:** 역할 기반 템플릿, ±0.15 랜덤, 행동 수정자 조회

### core/npc/tone.py
- **목적:** 톤 태그 생성
- **핵심:** HEXACO → manner_tags, 감정 계산

### core/npc/slots.py
- **목적:** 배경인물 슬롯 관리
- **핵심:** 시설별 슬롯 계산, 리셋 규칙

### core/npc/promotion.py
- **목적:** 승격 시스템
- **핵심:** 점수 테이블, 임계값 체크, 엔티티→NPC 변환

### core/npc/naming.py
- **목적:** NPC 명명
- **핵심:** 이름 풀 기반 생성

### core/npc/memory.py
- **목적:** NPC 기억 시스템
- **핵심:** Tier 1 슬롯 관리, Tier 2 용량 제한, 컨텍스트 기억 선택

## services/npc_service.py
- **목적:** NPC Service — Core와 DB 연결
- **핵심:** 승격 흐름, WorldPool, 기억 관리, EventBus 이벤트 발행
```

### 5. 검증 및 커밋

```bash
ruff check src/modules/npc/ tests/test_npc_module.py
pytest tests/test_npc_module.py -v
pytest tests/ -v
git add src/modules/npc/ tests/test_npc_module.py docs/SRC_INDEX.md
git commit -m "feat(npc): add NPCCoreModule with ModuleManager integration

- NPCCoreModule: GameModule ABC implementation
- EventBus subscription (npc_needed)
- Public query API (get_npcs_at_node, get_npc_by_id)
- Update SRC_INDEX.md

Ref: npc-system.md section 14.1"
```

---

# 실행 순서 요약

```
#08-A (Core 모델 + HEXACO + 톤)     ~20분
  ↓
#08-B (승격 + 슬롯 + 명명)           ~20분
  ↓
#08-C (기억 시스템)                   ~20분
  ↓
#08-D (Service + DB + EventBus)      ~25분
  ↓
#08-E (Module 래핑 + 등록)            ~15분
```

총 예상: ~100분 (각 블록 사이 검증 포함)

각 블록은 이전 블록의 커밋이 완료된 상태에서 실행한다.
#08-B와 #08-C는 서로 독립이지만, #08-D가 둘 다 필요하므로 순서대로 실행하는 것을 권장.
