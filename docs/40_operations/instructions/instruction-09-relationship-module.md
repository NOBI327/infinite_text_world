# 세션 A 통합 지시서: 메타 정리 + 관계 시스템 구현

5개 블록으로 분할. 각 블록은 독립 실행 + 독립 테스트 가능.
앞 블록의 커밋이 완료된 상태에서 다음 블록을 실행할 것.

---

# 지시서 #09-0: INDEX / SRC_INDEX / STATUS 갱신

**예상 시간**: 10분
**선행**: 없음

## 참조 문서

- `docs/INDEX.md` — 현재 설계 문서 인덱스
- `docs/SRC_INDEX.md` — 현재 소스 코드 인덱스
- `docs/STATUS.md` — 프로젝트 상태 (있다면)

## 작업 내용

### 1. INDEX.md에 신규 문서 추가

아래 문서들이 INDEX.md에 누락되어 있다면 추가:

**docs/10_product/ 섹션:**
```markdown
### worldbuilding-and-tone.md
- **목적:** 세계관 기초 + 서술 톤앤매너 + LLM 프롬프트 가이드
- **핵심:** "건조한 경이" 톤, 4종족, 만신전, 경제, 명명 규칙
- **상태:** 확정 (v1.4)

### content-safety.md
- **목적:** 콘텐츠 안전 정책 — 페이드 아웃 방식
- **핵심:** 묘사 레벨 3단계, 폴백 체인, 카테고리별 캐싱
- **상태:** 초안 (v0.3)
```

**docs/20_design/ 섹션:**
```markdown
### quest-action-integration.md
- **목적:** 퀘스트 목표 달성 판정 + 액션 연동
- **핵심:** ObjectiveWatcher, 5종 Objective, 대체 목표 생성
- **상태:** 확정 (v1.1)

### companion-system.md
- **목적:** NPC 동행 시스템
- **핵심:** 퀘스트/자발적 동행 2유형, escort 연동, 해산 후 귀환
- **상태:** 확정 (v1.1)
```

**docs/30_technical/ 섹션:**
```markdown
### event-bus.md
- **목적:** EventBus 통합 설계 — 전 모듈 이벤트 매트릭스
- **핵심:** 37개 이벤트, 구독 매트릭스, 순환 방어, 모듈 초기화 순서
- **상태:** 확정 (v1.1)

### i18n-policy.md
- **목적:** 다언어 대응 방침
- **핵심:** 일본어 최우선, Phase 2 후반 i18n 인프라 선투입
- **상태:** 방침 확정
```

기존 항목(quest-system.md 등)의 버전 번호도 갱신하라.

### 2. SRC_INDEX.md에 NPC 모듈 코드 추가

현재 SRC_INDEX.md에 NPC 관련 코드가 없다. 실제 파일을 확인하고 아래 항목을 추가:

```markdown
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
- **핵심:** 점수 테이블, 임계값 체크, 엔티티 → NPC 변환

### core/npc/naming.py
- **목적:** NPC 명명
- **핵심:** 이름 풀 기반 생성

### core/npc/memory.py
- **목적:** NPC 기억 시스템
- **핵심:** Tier 1 슬롯 관리, Tier 2 용량 제한, 컨텍스트 기억 선택

## core/event_types.py
- **목적:** 이벤트 타입 상수
- **핵심:** EventTypes 클래스 (모듈별 이벤트 이름 정의)

## services/npc_service.py
- **목적:** NPC Service — Core와 DB 연결
- **핵심:** 승격 흐름, WorldPool, 기억 관리, EventBus 이벤트 발행

## modules/npc/module.py
- **목적:** NPCCoreModule — GameModule 인터페이스 구현
- **핵심:** NPCService 래핑, EventBus 구독, 공개 조회 API 제공
```

**중요**: 실제 파일이 존재하는지 `ls` 등으로 확인한 후 추가하라. 파일이 없는 항목은 추가하지 마라.

### 3. 검증 및 커밋

```bash
ruff check src/ tests/  # 기존 코드 무파손 확인
pytest tests/ -v
git add docs/INDEX.md docs/SRC_INDEX.md
git commit -m "docs: update INDEX.md and SRC_INDEX.md with NPC module and new design docs"
```

---

# 지시서 #09-A: 관계 Core 모델 + 3축 계산

**예상 시간**: 20분
**선행**: #09-0 완료

## 참조 문서 (반드시 읽을 것)

- `docs/20_design/relationship-system.md` — 전체
- `src/core/npc/models.py` — HEXACO dataclass 확인
- `src/core/event_bus.py` — GameEvent, EventBus 인터페이스
- `src/core/event_types.py` — 기존 이벤트 타입 확인

## 작업 내용

### 1. Core 도메인 모델

**파일**: `src/core/relationship/models.py`

```python
"""관계 시스템 도메인 모델

relationship-system.md 섹션 9 대응.
DB 무관 순수 데이터 클래스.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
```

구현할 클래스:

| 클래스 | 출처 | 비고 |
|--------|------|------|
| `RelationshipStatus(str, Enum)` | 섹션 9.2 | 6종: stranger, acquaintance, friend, bonded, rival, nemesis |
| `Relationship` (dataclass) | 섹션 9.1 | relationship_id, source_type, source_id, target_type, target_id, affinity, trust, familiarity, status, tags, last_interaction_turn |
| `AttitudeContext` (dataclass) | 섹션 9.3 | target_npc_id, attitude_tags, relationship_status, npc_opinions |

### 2. 3축 수치 계산

**파일**: `src/core/relationship/calculations.py`

```python
"""3축 수치 변동 계산

relationship-system.md 섹션 4 대응.
전부 순수 함수 — 외부 의존 없음.
"""
```

구현할 함수/상수:

| 항목 | 출처 |
|------|------|
| `apply_affinity_damping(current: float, raw_change: float) -> float` | 섹션 4.3 — 지수 1.2 감쇠, 최소 10% |
| `apply_trust_damping(current: float, raw_change: float) -> float` | 섹션 4.3 — 비대칭: 상승은 감쇠, 하락은 감쇠 없음 |
| `apply_familiarity_decay(current: int, days_since_last: int) -> int` | 섹션 4.3 — 30일마다 -1, 최소 0 |
| `clamp_affinity(value: float) -> float` | -100 ~ +100 클램프 |
| `clamp_trust(value: float) -> float` | 0 ~ 100 클램프 |
| `clamp_meta_delta(value: float) -> float` | LLM META 제안 범위 -5 ~ +5 클램프 |

### 3. 상태 전이 판정

**파일**: `src/core/relationship/transitions.py`

```python
"""관계 상태 전이 판정

relationship-system.md 섹션 3, 9.4 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `TRANSITION_TABLE` | 섹션 9.4 전체 (코드 그대로 사용 가능) |
| `evaluate_transition(relationship: Relationship) -> Optional[RelationshipStatus]` | 현재 상태에서 승격/하락/적대 전이 가능 여부 확인. 변경이 필요하면 새 상태 반환, 아니면 None |

**판정 우선순위**: demote → rival → promote 순으로 검사. 여러 조건 충족 시 하락이 우선.

### 4. 반전 이벤트 처리

**파일**: `src/core/relationship/reversals.py`

```python
"""반전 이벤트 처리

relationship-system.md 섹션 5 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `ReversalType(str, Enum)` | "betrayal", "redemption", "trust_collapse" |
| `apply_reversal(relationship: Relationship, reversal_type: ReversalType) -> Relationship` | 섹션 5.1 공식 적용. 새 Relationship 반환 (원본 불변). 반전 후 상태도 재계산 (evaluate_transition 호출) |

### 5. 패키지 구조

```
src/core/relationship/
    __init__.py          # 공개 API export
    models.py            # 도메인 모델
    calculations.py      # 3축 계산 (감쇠, 클램프)
    transitions.py       # 상태 전이 판정
    reversals.py         # 반전 이벤트
```

### 6. 테스트

**파일**: `tests/test_relationship_core.py`

- `test_relationship_status_enum`: 6종 값 확인
- `test_relationship_creation_defaults`: 기본값 (affinity=0, trust=0, stranger)
- `test_affinity_damping_at_zero`: 현재 0 → damping 1.0 → 변동 그대로
- `test_affinity_damping_at_high`: 현재 90 → damping 0.13 → +5 제안이 약 +0.7
- `test_affinity_damping_negative`: 현재 -50 → 감쇠 적용 확인
- `test_affinity_damping_minimum`: damping 최소 10% 보장
- `test_trust_damping_increase`: 상승 시 감쇠 적용
- `test_trust_damping_decrease`: 하락 시 감쇠 없음 (raw_change 그대로)
- `test_familiarity_decay`: 60일 경과 → -2
- `test_familiarity_decay_minimum`: 감쇠 후 최소 0
- `test_clamp_meta_delta`: 10 → 5, -10 → -5
- `test_transition_stranger_to_acquaintance`: familiarity 3 이상 → acquaintance
- `test_transition_acquaintance_to_friend`: affinity 30, trust 25 → friend
- `test_transition_friend_demote`: affinity 14 → acquaintance로 하락
- `test_transition_rival`: affinity -25, familiarity 5 → rival
- `test_transition_priority_demote_over_promote`: 동시 충족 시 하락 우선
- `test_reversal_betrayal`: affinity 45 → -45, trust 40 → 12
- `test_reversal_redemption`: affinity -40 → +28, trust 15 → 45
- `test_reversal_trust_collapse`: trust 60 → 12, affinity 변동 없음
- `test_reversal_auto_retransition`: betrayal 후 자동으로 rival 전이

### 7. 검증 및 커밋

```bash
ruff check src/core/relationship/ tests/test_relationship_core.py
pytest tests/test_relationship_core.py -v
pytest tests/ -v  # 기존 테스트 무파손
git add src/core/relationship/ tests/test_relationship_core.py
git commit -m "feat(relationship): add core models, 3-axis calculations, transitions, reversals

- RelationshipStatus 6-state enum
- Affinity/trust damping (asymmetric trust)
- Familiarity time decay
- State transition table with priority (demote > rival > promote)
- Reversal events (betrayal/redemption/trust_collapse)

Ref: relationship-system.md sections 2-5, 9"
```

---

# 지시서 #09-B: 태도 태그 생성 파이프라인

**예상 시간**: 15분
**선행**: #09-A 완료

## 참조 문서

- `docs/20_design/relationship-system.md` — 섹션 6 (태도 태그 생성)
- `src/core/npc/models.py` — HEXACO dataclass
- `src/core/npc/memory.py` — NPCMemory dataclass

## 작업 내용

### 1. 태도 태그 생성

**파일**: `src/core/relationship/attitude.py`

```python
"""NPC → PC 태도 태그 생성 파이프라인

relationship-system.md 섹션 6 대응.
3단계: 관계 수치 → HEXACO 보정 → 기억 보정
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `AFFINITY_ATTITUDE_MAP` | 섹션 6.2 — affinity 구간별 태그 매핑 (5구간) |
| `TRUST_ATTITUDE_MAP` | 섹션 6.2 — trust 구간별 태그 매핑 (3구간) |
| `HEXACO_ATTITUDE_RULES: List[Tuple]` | 섹션 6.3 — 8개 규칙 (factor, threshold, condition_field, condition_op, condition_value, tag) |
| `MEMORY_ATTITUDE_MAP: Dict[str, str]` | 섹션 6.4 — 6개 기억 태그 → 태도 태그 매핑 |
| `generate_base_attitude(relationship: Relationship) -> List[str]` | 1단계: 수치 → 태그 |
| `apply_hexaco_modifiers(tags: List[str], hexaco: HEXACO, relationship: Relationship) -> List[str]` | 2단계: HEXACO 보정 |
| `apply_memory_modifiers(tags: List[str], memory_tags: List[str]) -> List[str]` | 3단계: 기억 보정. 중복 태그 제거 |
| `generate_attitude_tags(relationship: Relationship, hexaco: HEXACO, memory_tags: List[str]) -> AttitudeContext` | 전체 파이프라인 실행. 태그 수 2~7 클램프 |

### 2. NPC간 의견 생성

**파일**: `src/core/relationship/npc_opinions.py`

```python
"""NPC간 관계를 대화용 태그로 변환

relationship-system.md 섹션 7.3 대응.
"""
```

구현할 항목:

| 항목 | 출처 |
|------|------|
| `generate_npc_opinion_tags(relationship: Relationship) -> List[str]` | affinity/trust 기반 간단 태그 생성. "speaks_fondly", "distrustful", "avoids" 등 |
| `build_npc_opinions(source_npc_id: str, relationships: List[Relationship]) -> Dict[str, List[str]]` | 특정 NPC의 타 NPC에 대한 의견 딕셔너리 |

### 3. 테스트

**파일**: `tests/test_relationship_attitude.py`

- `test_base_attitude_friendly`: affinity 35 → "friendly"
- `test_base_attitude_hostile`: affinity -60 → "hostile"
- `test_base_attitude_trust_layers`: trust 70 → "trusting"
- `test_hexaco_reserved`: X=0.2, familiarity=3 → "reserved" 추가
- `test_hexaco_chatty`: X=0.8, familiarity=10 → "chatty" 추가
- `test_hexaco_confrontational`: A=0.2, affinity=-10 → "confrontational" 추가
- `test_memory_modifier`: memory_tags=["broke_promise"] → "remembers_betrayal" 추가
- `test_memory_modifier_duplicate`: 동일 태그 중복 시 1개만
- `test_full_pipeline_tag_count`: 최종 태그 수 2~7 범위 확인
- `test_full_pipeline_example`: 섹션 6.5의 대장장이 한스 예시 재현
- `test_npc_opinion_fondly`: affinity 40 → "speaks_fondly" 포함
- `test_npc_opinion_distrustful`: trust 10 → "distrustful" 포함
- `test_build_npc_opinions`: 여러 관계 → 딕셔너리 구성 확인

### 4. 검증 및 커밋

```bash
ruff check src/core/relationship/ tests/test_relationship_attitude.py
pytest tests/test_relationship_attitude.py -v
pytest tests/ -v
git add src/core/relationship/attitude.py src/core/relationship/npc_opinions.py tests/test_relationship_attitude.py
git commit -m "feat(relationship): add attitude tag pipeline and NPC opinion generation

- 3-stage pipeline: base attitude → HEXACO modifiers → memory modifiers
- Tag count clamped to 2-7
- NPC-to-NPC opinion tags for dialogue context

Ref: relationship-system.md sections 6, 7"
```

---

# 지시서 #09-C: Relationship Service (DB 연동 + EventBus)

**예상 시간**: 25분
**선행**: #09-A, #09-B 완료

## 참조 문서

- `docs/20_design/relationship-system.md` — 섹션 8 (EventBus 인터페이스), 섹션 7 (NPC간 관계)
- `docs/30_technical/architecture.md` — Service 레이어 규칙
- `docs/30_technical/event-bus.md` — relationship 관련 이벤트
- `src/db/models_v2.py` — RelationshipModel 확인
- `src/services/npc_service.py` — Service 구현 패턴 참고

## 작업 내용

### 1. Relationship Service

**파일**: `src/services/relationship_service.py`

```python
"""Relationship Service — Core와 DB를 연결

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""
```

구현할 메서드:

| 메서드 | 역할 |
|--------|------|
| `__init__(self, db_session, event_bus)` | DI |
| `get_relationship(source_type, source_id, target_type, target_id) -> Optional[Relationship]` | DB 조회 → Core 모델 변환 |
| `get_relationships_for(source_type, source_id) -> List[Relationship]` | 특정 엔티티의 전체 관계 조회 |
| `create_relationship(source_type, source_id, target_type, target_id, **initial_values) -> Relationship` | 신규 관계 생성 + DB 저장 |
| `apply_dialogue_delta(source_id, target_id, affinity_delta, reason) -> Relationship` | 대화 종료 후: META에서 받은 delta → 감쇠 적용 → DB 갱신 → 상태 전이 체크 → 변경 시 이벤트 발행 |
| `apply_action_delta(source_id, target_id, affinity_delta, trust_delta, familiarity_delta, reason) -> Relationship` | 행동(부탁 수행, 선물 등) 후 수치 변동 → 감쇠 적용 → DB 갱신 → 전이 체크 |
| `apply_reversal(source_id, target_id, reversal_type) -> Relationship` | 반전 이벤트 적용 → DB 갱신 → relationship_reversed 이벤트 발행 |
| `process_familiarity_decay(current_turn) -> int` | 전체 관계의 familiarity 시간 감쇠 처리. 감쇠된 관계 수 반환 |
| `create_initial_npc_relationships(new_npc_id, node_id) -> List[Relationship]` | 승격 시: 같은 노드 NPC들과 초기 관계 생성 (섹션 7.1) |
| `generate_attitude(npc_id, target_id, hexaco, memory_tags, include_npc_opinions) -> AttitudeContext` | 태도 태그 생성 (Core 파이프라인 호출) |

**ORM ↔ Core 변환 헬퍼**: `_relationship_from_orm(model) -> Relationship`, `_relationship_to_orm(rel) -> dict` private 메서드.

### 2. EventTypes 추가

**파일**: `src/core/event_types.py` (기존 파일에 추가)

```python
# relationship
RELATIONSHIP_CHANGED = "relationship_changed"
RELATIONSHIP_REVERSED = "relationship_reversed"
ATTITUDE_REQUEST = "attitude_request"
ATTITUDE_RESPONSE = "attitude_response"
```

### 3. 테스트

**파일**: `tests/test_relationship_service.py`

인메모리 SQLite + EventBus mock으로 통합 테스트:

- `test_create_and_get_relationship`: 생성 → 조회 → 필드 일치
- `test_apply_dialogue_delta_with_damping`: affinity=50인 상태에서 +5 적용 → 감쇠된 값 확인
- `test_apply_dialogue_delta_meta_clamp`: +10 제안 → +5로 클램프됨
- `test_apply_dialogue_delta_triggers_transition`: familiarity 2 → 대화 후 familiarity 3 → stranger→acquaintance 전이 + 이벤트 발행 확인
- `test_apply_action_delta`: 부탁 수행 → affinity+10, trust+15 → 감쇠 적용 + DB 갱신
- `test_apply_reversal_betrayal`: 반전 후 수치 확인 + relationship_reversed 이벤트 확인
- `test_process_familiarity_decay`: 60일 경과 관계 3건 → 감쇠 후 familiarity 확인
- `test_create_initial_npc_relationships`: NPC 2명 존재하는 노드에 신규 NPC 승격 → 2건 관계 생성
- `test_generate_attitude_full_pipeline`: hexaco + memory_tags → AttitudeContext 반환, 태그 2~7개

### 4. 검증 및 커밋

```bash
ruff check src/services/relationship_service.py src/core/event_types.py tests/test_relationship_service.py
pytest tests/test_relationship_service.py -v
pytest tests/ -v
git add src/services/relationship_service.py src/core/event_types.py tests/test_relationship_service.py
git commit -m "feat(relationship): add RelationshipService with DB and EventBus integration

- CRUD, dialogue/action delta with damping
- Reversal events, familiarity decay
- Initial NPC relationship creation on promotion
- Attitude tag generation via Core pipeline
- EventTypes: relationship_changed, relationship_reversed, attitude_request/response

Ref: relationship-system.md sections 7, 8"
```

---

# 지시서 #09-D: RelationshipModule (GameModule 래핑 + EventBus 구독)

**예상 시간**: 15분
**선행**: #09-C 완료

## 참조 문서

- `docs/20_design/relationship-system.md` — 섹션 8 (EventBus 인터페이스)
- `src/modules/base.py` — GameModule ABC
- `src/modules/npc/module.py` — Module 구현 패턴 참고

## 작업 내용

### 1. RelationshipModule

**파일**: `src/modules/relationship/module.py`

```python
"""Relationship Module — GameModule 인터페이스 구현

relationship-system.md 섹션 8 대응.
"""
```

구현:

```python
class RelationshipModule(GameModule):
    name = "relationship"
    dependencies = ["npc_core"]

    def initialize(self, context: GameContext) -> None:
        self.service = RelationshipService(context.db_session, context.event_bus)
        # 구독 등록
        context.event_bus.subscribe(EventTypes.NPC_PROMOTED, self._handle_npc_promoted)
        context.event_bus.subscribe(EventTypes.DIALOGUE_ENDED, self._handle_dialogue_ended)
        context.event_bus.subscribe(EventTypes.ATTITUDE_REQUEST, self._handle_attitude_request)

    def process_turn(self, context: GameContext) -> None:
        """턴 처리: familiarity 시간 감쇠"""
        self.service.process_familiarity_decay(context.current_turn)

    def shutdown(self, context: GameContext) -> None:
        pass

    # --- EventBus 핸들러 ---

    def _handle_npc_promoted(self, event: GameEvent) -> None:
        """NPC 승격 시 같은 노드 NPC들과 초기 관계 생성"""
        npc_id = event.data["npc_id"]
        node_id = event.data["node_id"]
        self.service.create_initial_npc_relationships(npc_id, node_id)

    def _handle_dialogue_ended(self, event: GameEvent) -> None:
        """대화 종료 시 META에서 관계 변동 추출 + 상태 전이 판정"""
        source_id = event.data["player_id"]
        target_id = event.data["npc_id"]
        delta = event.data.get("relationship_delta", {})
        if delta:
            affinity_delta = delta.get("affinity", 0)
            reason = delta.get("reason", "dialogue")
            self.service.apply_dialogue_delta(source_id, target_id, affinity_delta, reason)

    def _handle_attitude_request(self, event: GameEvent) -> None:
        """태도 태그 요청 처리 → attitude_response 발행"""
        npc_id = event.data["npc_id"]
        target_id = event.data["target_id"]
        # NPC의 HEXACO와 기억은 event.data에 포함되어야 함
        hexaco = event.data.get("hexaco")
        memory_tags = event.data.get("memory_tags", [])
        include_opinions = event.data.get("include_npc_opinions", False)

        attitude = self.service.generate_attitude(
            npc_id, target_id, hexaco, memory_tags, include_opinions
        )

        event.source_bus.emit(GameEvent(
            event_type=EventTypes.ATTITUDE_RESPONSE,
            data={
                "request_id": event.data.get("request_id"),
                "npc_id": npc_id,
                "target_id": target_id,
                "attitude_tags": attitude.attitude_tags,
                "relationship_status": attitude.relationship_status,
                "npc_opinions": attitude.npc_opinions,
            },
            source="relationship",
        ))
```

**주의**: `DIALOGUE_ENDED`는 아직 event_types.py에 없을 수 있다. 있으면 사용, 없으면 추가:
```python
DIALOGUE_ENDED = "dialogue_ended"
```

### 2. 패키지 구조

```
src/modules/relationship/
    __init__.py          # RelationshipModule export
    module.py            # GameModule 구현
```

### 3. 테스트

**파일**: `tests/test_relationship_module.py`

- `test_module_register_and_initialize`: ModuleManager에 등록 → initialize 성공
- `test_npc_promoted_creates_relationships`: npc_promoted 이벤트 발행 → 초기 관계 생성 확인
- `test_dialogue_ended_applies_delta`: dialogue_ended 이벤트 + delta → 수치 변동 확인
- `test_attitude_request_response`: attitude_request 이벤트 → attitude_response 수신 확인
- `test_process_turn_decay`: process_turn 호출 → familiarity 감쇠 확인

### 4. SRC_INDEX.md 갱신

아래 항목 추가:

```markdown
## core/relationship/ - 관계 시스템 Core 로직

### core/relationship/models.py
- **목적:** 관계 도메인 모델 (DB 무관)
- **핵심:** RelationshipStatus, Relationship, AttitudeContext

### core/relationship/calculations.py
- **목적:** 3축 수치 계산
- **핵심:** affinity/trust 감쇠, familiarity 시간 감쇠, 클램프

### core/relationship/transitions.py
- **목적:** 관계 상태 전이 판정
- **핵심:** TRANSITION_TABLE, 우선순위 기반 전이 평가

### core/relationship/reversals.py
- **목적:** 반전 이벤트 처리
- **핵심:** betrayal/redemption/trust_collapse 공식

### core/relationship/attitude.py
- **목적:** 태도 태그 생성 파이프라인
- **핵심:** 3단계 (수치 → HEXACO → 기억), 태그 2~7개

### core/relationship/npc_opinions.py
- **목적:** NPC간 의견 태그
- **핵심:** 관계 수치 → 대화용 태그 변환

## services/relationship_service.py
- **목적:** Relationship Service — Core와 DB 연결
- **핵심:** 대화/행동 delta, 반전, 감쇠, 태도 생성

## modules/relationship/module.py
- **목적:** RelationshipModule — GameModule 인터페이스
- **핵심:** EventBus 구독 (npc_promoted, dialogue_ended, attitude_request)
```

### 5. 검증 및 커밋

```bash
ruff check src/modules/relationship/ tests/test_relationship_module.py
pytest tests/test_relationship_module.py -v
pytest tests/ -v
git add src/modules/relationship/ tests/test_relationship_module.py docs/SRC_INDEX.md
git commit -m "feat(relationship): add RelationshipModule with EventBus integration

- GameModule ABC implementation
- EventBus subscriptions: npc_promoted, dialogue_ended, attitude_request
- Familiarity decay on process_turn
- Update SRC_INDEX.md

Ref: relationship-system.md section 8"
```

---

# 실행 순서 요약

```
#09-0 (INDEX/SRC_INDEX 갱신)          ~10분
  ↓
#09-A (Core 모델 + 3축 + 전이 + 반전) ~20분
  ↓
#09-B (태도 태그 파이프라인)            ~15분
  ↓
#09-C (Service + DB + EventBus)       ~25분
  ↓
#09-D (Module 래핑 + 등록)             ~15분
```

총 예상: ~85분 (각 블록 사이 검증 포함)

#09-0은 독립 실행 가능. #09-A부터는 순서 엄수.
