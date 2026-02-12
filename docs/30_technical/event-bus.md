# EventBus 통합 설계

**버전**: 1.1
**작성일**: 2026-02-10  
**상태**: 확정  
**관련**: architecture.md, npc-system.md (14.2), relationship-system.md (8), quest-system.md (9), dialogue-system.md (8), item-system.md (10)

---

## 1. 개요

### 1.1 목적

각 설계 문서에 흩어진 EventBus 인터페이스를 하나로 통합한다. 이벤트의 발행자/구독자를 정리하고, 순환 참조·중복·누락을 검증한다.

### 1.2 현재 인프라

`src/core/event_bus.py`에 구현 완료 (지시서 #02):
- `GameEvent(event_type, data, source)` — 이벤트 데이터 컨테이너
- `EventBus` — 동기식. `subscribe()`, `emit()`, `reset_chain()`, `clear()`
- 안전장치: 전파 깊이 MAX_DEPTH=5, 동일 source:event_type 중복 발행 차단
- `reset_chain()`은 턴 종료 시 호출하여 중복 추적 초기화

### 1.3 설계 원칙

- 서비스/모듈은 다른 서비스/모듈을 직접 import하지 않는다
- 이벤트 data에는 ID만 전달한다 (무거운 객체 금지)
- 한 턴 내 전파 깊이 최대 5단계
- 동일 원인에서 동일 이벤트 중복 발행 금지

---

## 2. 이벤트 카탈로그

전체 이벤트를 발행 모듈 기준으로 분류한다.

### 2.1 npc_core 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `npc_promoted` | `{npc_id, origin_type, node_id}` | relationship, quest, npc_memory |
| `npc_created` | `{npc_id, role, node_id}` | quest, item |
| `npc_died` | `{npc_id, cause, node_id}` | relationship, quest |
| `npc_moved` | `{npc_id, from_node, to_node}` | — (Phase B+) |

### 2.2 relationship 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `relationship_changed` | `{source_id, target_id, field, old_value, new_value, old_status, new_status}` | dialogue, quest, npc_behavior |
| `relationship_reversed` | `{source_id, target_id, reversal_type, old_status, new_status}` | npc_memory, dialogue, quest |
| `attitude_response` | `{request_id, npc_id, target_id, attitude_tags, relationship_status, npc_opinions}` | dialogue |

### 2.3 quest 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `quest_activated` | `{quest_id, quest_type, related_npc_ids, target_node_ids}` | overlay, npc_behavior, dialogue |
| `quest_completed` | `{quest_id, result, rewards, chain_id}` | relationship, overlay, npc_memory, item |
| `quest_failed` | `{quest_id, reason, chain_id}` | relationship, overlay, npc_memory |
| `quest_abandoned` | `{quest_id, chain_id}` | relationship, overlay, npc_memory |
| `quest_seed_created` | `{seed_id, npc_id, seed_type, ttl_turns}` | npc_memory |
| `quest_seed_expired` | `{seed_id, npc_id, expiry_result}` | npc_memory |
| `quest_seed_generated` | `{seed_id, npc_id, seed_type, context_tags}` | dialogue |
| `quest_chain_formed` | `{chain_id, quest_ids}` | dialogue |
| `quest_chain_finalized` | `{chain_id, total_quests, overall_result}` | relationship, world |
| `npc_needed` | `{quest_id, npc_role, node_id}` | npc_core |
| `chain_eligible_matched` | `{quest_id, chain_id, npc_ref, matched_npc_id}` | dialogue, npc_memory |

### 2.4 dialogue 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `dialogue_started` | `{session_id, player_id, npc_id, node_id}` | quest |
| `dialogue_ended` | `{session_id, npc_id, accumulated_deltas, memory_tags, seed_result, dialogue_turns}` | relationship, quest, npc_memory, item |
| `dialogue_action_declared` | `{session_id, npc_id, action_interpretation, validated}` | engine |
| `attitude_request` | `{request_id, npc_id, target_id, include_npc_opinions}` | relationship |

### 2.5 item 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `item_transferred` | `{instance_id, from_type, from_id, to_type, to_id, reason}` | relationship, quest |
| `item_broken` | `{instance_id, prototype_id, owner_type, owner_id, broken_result}` | narrative |
| `item_created` | `{instance_id, prototype_id, owner_type, owner_id, source}` | quest, npc_core |

### 2.6 engine / ModuleManager 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `turn_processed` | `{turn_number, player_id}` | relationship, quest, item, **companion** |
| `check_result` | `{session_id, action, result_tier, dice_result, stat, context_tags}` | dialogue, **ObjectiveWatcher** |
| `objective_completed` | `{quest_id, objective_id, objective_type, trigger_action, trigger_data, turn_number}` | quest |
| **`player_moved`** *(신규)* | `{player_id, from_node, to_node, move_type}` | **ObjectiveWatcher**, **companion** |
| **`action_completed`** *(신규)* | `{player_id, action_type, node_id, result_data}` | **ObjectiveWatcher** |
| **`item_given`** *(신규)* | `{player_id, recipient_npc_id, item_prototype_id, instance_id, quantity, item_tags}` | **ObjectiveWatcher**, relationship |
| **`objective_failed`** *(신규)* | `{quest_id, objective_id, objective_type, fail_reason, trigger_data, turn_number}` | quest |

`move_type`: "walk" | "enter" | "exit" | "up" | "down"
`action_type`: "look" | "investigate" | "harvest" | "give" | "use"

#### check_result 페이로드 확장

기존 필수 키 `session_id, action, result_tier, dice_result`에 선택 키 추가:

| 추가 키 | 타입 | 용도 |
|---------|------|------|
| `stat` | STRING | 판정 스탯 ("READ", "WRITE", "EXEC", "SUDO") — ObjectiveWatcher resolve_check 매칭용 |
| `context_tags` | LIST[STRING] | 판정 맥락 태그 — ObjectiveWatcher resolve_check 매칭용 |

#### objective_completed 페이로드 확장

기존 필수 키 `quest_id, objective_id, objective_type`에 선택 키 추가:

| 추가 키 | 타입 | 용도 |
|---------|------|------|
| `trigger_action` | STRING | 달성을 트리거한 액션 ("move", "give", "talk", "check") |
| `trigger_data` | DICT | 트리거 상세 데이터 |
| `turn_number` | INTEGER | 달성 턴 |

### 2.7 overlay 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `environment_quest_trigger` | `{overlay_id, node_id, trigger_type}` | quest |

### 2.8 combat 발행 (Phase 3+)

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `combat_entity_survived` | `{entity_id, node_id}` | npc_core |

### 2.9 companion 발행

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| **`companion_joined`** | `{companion_id, player_id, npc_id, companion_type, quest_id}` | dialogue, quest, npc_memory |
| **`companion_moved`** | `{companion_id, npc_id, from_node, to_node}` | narrative |
| **`companion_disbanded`** | `{companion_id, npc_id, disband_reason, quest_id}` | quest, relationship, npc_memory |

---

## 3. 구독 매트릭스

행 = 이벤트, 열 = 구독 모듈. ● = 구독. **OW** = ObjectiveWatcher (engine 내부 컴포넌트).

| 이벤트 \ 구독자 | npc_core | relationship | quest | dialogue | item | npc_memory | overlay | engine | narrative | **OW** | **companion** |
|---------------|:--------:|:------------:|:-----:|:--------:|:----:|:----------:|:-------:|:------:|:---------:|:------:|:-------------:|
| `npc_promoted` | | ● | ● | | | ● | | | | | |
| `npc_created` | | | ● | | ● | | | | | | |
| `npc_died` | | ● | ● | | | | | | | **●** | **●** |
| `npc_moved` | | | | | | | | | | | |
| `relationship_changed` | | | ● | ● | | | | | | | |
| `relationship_reversed` | | | ● | ● | | ● | | | | | |
| `attitude_response` | | | | ● | | | | | | | |
| `quest_activated` | | | | ● | | | ● | | | | **●** |
| `quest_completed` | | ● | | | ● | ● | ● | | | | **●** |
| `quest_failed` | | ● | | | | ● | ● | | | | **●** |
| `quest_abandoned` | | ● | | | | ● | ● | | | | **●** |
| `quest_seed_created` | | | | | | ● | | | | | |
| `quest_seed_expired` | | | | | | ● | | | | | |
| `quest_seed_generated` | | | | ● | | | | | | | |
| `quest_chain_formed` | | | | ● | | | | | | | |
| `quest_chain_finalized` | | ● | | | | | | | | | |
| `npc_needed` | ● | | | | | | | | | | |
| `chain_eligible_matched` | | | | ● | | ● | | | | | |
| `dialogue_started` | | | ● | | | | | | | **●** | |
| `dialogue_ended` | | ● | ● | | ● | ● | | | | **●** | |
| `dialogue_action_declared` | | | | | | | | ● | | | |
| `attitude_request` | | ● | | | | | | | | | |
| `item_transferred` | | ● | ● | | | | | | | | |
| `item_broken` | | | | | | | | | ● | | |
| `item_created` | ● | | ● | | | | | | | | |
| `turn_processed` | | ● | ● | | ● | | | | | | **●** |
| `check_result` | | | | ● | | | | | | **●** | |
| `objective_completed` | | | ● | | | | | | | | |
| `environment_quest_trigger` | | | ● | | | | | | | | |
| `combat_entity_survived` | ● | | | | | | | | | | |
| **`player_moved`** | | | | | | | | | | **●** | **●** |
| **`action_completed`** | | | | | | | | | | **●** | |
| **`item_given`** | | **●** | | | | | | | | **●** | |
| **`objective_failed`** | | | **●** | | | | | | | | |
| **`companion_joined`** | | | **●** | **●** | | **●** | | | | | |
| **`companion_moved`** | | | | | | | | | **●** | | |
| **`companion_disbanded`** | | | **●** | | | **●** | | | | | |

---

## 4. 순환 분석

이벤트 체인에서 A→B→A 순환이 발생할 수 있는 경로를 분석한다.

### 4.1 잠재적 순환 경로

**경로 1: quest ↔ npc_core**
```
quest --npc_needed--> npc_core --npc_created--> quest
```
- quest가 `npc_needed` 발행 → npc_core가 NPC 생성 후 `npc_created` 발행 → quest가 구독
- **위험 수준: 낮음**. quest는 `npc_created` 수신 시 해당 NPC를 퀘스트에 연결만 하고, 새 `npc_needed`를 발행하지 않는다
- **방어**: EventBus 중복 차단 (`quest:npc_needed` 1회 발행 후 동일 체인 내 재발행 불가)

**경로 2: dialogue ↔ relationship**
```
dialogue --attitude_request--> relationship --attitude_response--> dialogue
```
- 요청/응답 패턴. dialogue가 `attitude_request` 발행 → relationship이 계산 후 `attitude_response` 발행 → dialogue 수신
- **위험 수준: 없음**. 의도된 request/response 패턴이며, dialogue가 `attitude_response` 수신 후 다시 `attitude_request`를 발행하지 않는다

**경로 3: dialogue → quest → dialogue**
```
dialogue --dialogue_started--> quest --quest_seed_generated--> dialogue
```
- **위험 수준: 없음**. dialogue_started에서 quest가 시드 판정 후 응답하는 의도된 패턴

**경로 4: dialogue → relationship → dialogue (간접)**
```
dialogue --dialogue_ended--> relationship --relationship_changed--> dialogue
```
- **위험 수준: 중간**. dialogue_ended 후 relationship이 상태 변경 → relationship_changed 발행 → dialogue가 구독
- **방어**: dialogue는 `relationship_changed`를 **다음 세션** 컨텍스트 참조용으로만 사용한다. 종료된 세션에서 다시 `dialogue_ended`를 발행하지 않는다
- **구현 규칙**: dialogue의 `relationship_changed` 핸들러는 캐시 갱신만 하고, 이벤트를 발행하지 않는다

**경로 5: quest → relationship → quest (간접)**
```
quest --quest_completed--> relationship --relationship_changed--> quest
```
- **위험 수준: 중간**. 퀘스트 완료 → 관계 변동 → 관계 변경 이벤트 → quest 구독
- **방어**: quest는 `relationship_changed` 수신 시 정보 기록만 하고, 새 퀘스트/시드를 즉시 생성하지 않는다. 시드 생성은 `dialogue_started` 이벤트에서만 발생한다

### 4.2 추가 순환 경로 분석

**경로 6: ObjectiveWatcher → quest (신규)**
```
engine(OW) --objective_completed--> quest --quest_completed--> relationship, overlay, ...
```
- 위험 수준: 없음. quest_completed 구독자는 engine에 이벤트를 발행하지 않음.
- ObjectiveWatcher는 quest 이벤트를 구독하지 않음.

**경로 7: ObjectiveWatcher → quest → 대체 목표 (신규)**
```
engine(OW) --objective_failed--> quest --대체 목표 생성--> (DB 쓰기)
```
- 위험 수준: 없음. 대체 목표 생성은 DB 쓰기일 뿐 이벤트를 발행하지 않음.
- 대체 목표의 달성은 PC의 다음 액션에서 별도 체인으로 처리됨.

**경로 8: companion ↔ quest (신규)**
```
quest_activated → companion(동행 요청) → companion_joined → quest(구독)
```
- 위험 수준: 낮음. quest는 `companion_joined` 수신 시 escort 목표와 동행을 연결하여 정보만 기록. 새 이벤트 발행 없음.
- **방어**: companion의 `companion_joined` 발행은 `quest_activated` 체인 내에서 depth 1에서 발생. quest의 핸들러는 depth 2에서 실행되며 이벤트를 발행하지 않음. MAX_DEPTH=5 이내.

**경로 9: player_moved → companion + ObjectiveWatcher 동시 (신규)**
```
engine --player_moved--> [companion: NPC 좌표 갱신 → companion_moved 발행]
                     --> [ObjectiveWatcher: reach_node/escort 체크 → objective_completed 발행]
```
- 위험 수준: 낮음. 두 구독자가 독립적으로 처리.
- companion_moved → narrative (서술 추가, 이벤트 발행 없음)
- objective_completed → quest (퀘스트 판정, quest_completed 발행 가능)
- quest_completed → companion (자동 해산)
- **방어**: 체인 깊이: player_moved(0) → companion_moved(1) / objective_completed(1) → quest_completed(2) → companion_disbanded(3). MAX_DEPTH=5 이내.
- **실행 순서 중요**: companion이 OW보다 먼저 실행되어야 NPC 좌표가 갱신된 상태에서 escort 판정이 가능. 모듈 초기화 순서로 보장 (섹션 8.2).

### 4.3 순환 방어 정책

| 규칙 | 내용 |
|------|------|
| EventBus 중복 차단 | 동일 source:event_type은 체인 내 1회 발행 (기 구현) |
| 전파 깊이 제한 | MAX_DEPTH=5 (기 구현) |
| 핸들러 부작용 금지 | request/response 외의 핸들러는 **이벤트 발행을 최소화**한다 |
| 지연 발행 원칙 | 복잡한 후속 처리는 다음 턴의 `turn_processed`에서 수행한다 |

---

## 5. 이벤트 생명주기

### 5.1 턴 주기

```
[게임 턴 시작]
  │
  ├─ PC 입력 처리 (move/look/investigate/give/...)
  │    ├─ player_moved 발행 (이동 시)
  │    │    ├─ companion: NPC 좌표 동기화 → companion_moved 발행 (depth 1)
  │    │    │    └─ narrative: 이동 서술 추가 (depth 2)
  │    │    └─ ObjectiveWatcher: reach_node/escort 체크 (depth 1)
  │    │         └─ objective_completed 발행 시 → quest (depth 2)
  │    │              └─ quest_completed 발행 시 → companion: 자동 해산 (depth 3)
  │    │
  │    ├─ action_completed 발행 (조사/채취 등)
  │    │    └─ ObjectiveWatcher: reach_node(require_action) 체크 (depth 1)
  │    │
  │    └─ item_given 발행 (give 액션 시)
  │         └─ ObjectiveWatcher: deliver 체크 (depth 1)
  │
  ├─ 대화 세션 (해당 시)
  │    ├─ dialogue_started 발행 (depth 0)
  │    │    ├─ quest: 시드 5% 판정 (depth 1)
  │    │    ├─ dialogue: attitude_request (depth 1)
  │    │    └─ ObjectiveWatcher: talk_to_npc(단순 접촉) 체크 (depth 1)
  │    │
  │    ├─ [LLM 대화 루프 — N턴]
  │    │    ├─ dialogue_action_declared 발행 (해당 시)
  │    │    │    └─ engine: check_result 발행
  │    │    │         ├─ dialogue: 서술 반영
  │    │    │         └─ ObjectiveWatcher: resolve_check 체크
  │    │    └─ (루프 반복)
  │    │
  │    └─ dialogue_ended 발행 (depth 0, 체인 리셋 후)
  │         ├─ relationship: 수치 갱신 (depth 1)
  │         ├─ quest: seed_result 확인 (depth 1)
  │         ├─ npc_memory: 기억 저장 (depth 1)
  │         ├─ item: 거래/선물 처리 (depth 1)
  │         └─ ObjectiveWatcher: talk_to_npc(주제 요구) 체크 (depth 1)
  │
  ├─ turn_processed 발행 (체인 리셋 후)
  │    ├─ relationship: 시간 감쇠
  │    ├─ quest: TTL 체크
  │    ├─ item: 내구도 감쇠
  │    └─ companion: 조건 만료 체크 → 해산 시 companion_disbanded 발행 (depth 1)
  │
  └─ event_bus.reset_chain()

[게임 턴 종료]
```

### 5.2 체인 리셋 시점

한 턴 내에서 `reset_chain()`을 **여러 번** 호출하여 체인을 분리한다:

| 시점 | 이유 |
|------|------|
| 대화 세션 종료 후, `dialogue_ended` 발행 전 | 세션 내부 이벤트와 종료 이벤트를 분리 |
| `turn_processed` 발행 전 | 대화 종료 체인과 턴 처리 체인을 분리 |
| 턴 종료 시 | 다음 턴 준비 |

이렇게 하면 대화 세션 내 depth 2까지 사용된 후, `dialogue_ended` 체인에서 다시 depth 0부터 시작할 수 있다.

---

## 6. 이벤트 타입 상수

구현 시 문자열 오타를 방지하기 위해 상수 모듈을 정의한다.

**파일**: `src/core/event_types.py`

```python
"""EventBus 이벤트 타입 상수

event-bus.md 섹션 2의 이벤트 카탈로그와 1:1 대응.
새 이벤트 추가 시 반드시 여기에 상수를 정의하고, event-bus.md도 갱신할 것.
"""


class EventTypes:
    """이벤트 타입 상수 네임스페이스"""

    # --- npc_core 발행 ---
    NPC_PROMOTED = "npc_promoted"
    NPC_CREATED = "npc_created"
    NPC_DIED = "npc_died"
    NPC_MOVED = "npc_moved"

    # --- relationship 발행 ---
    RELATIONSHIP_CHANGED = "relationship_changed"
    RELATIONSHIP_REVERSED = "relationship_reversed"
    ATTITUDE_RESPONSE = "attitude_response"

    # --- quest 발행 ---
    QUEST_ACTIVATED = "quest_activated"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    QUEST_ABANDONED = "quest_abandoned"
    QUEST_SEED_CREATED = "quest_seed_created"
    QUEST_SEED_EXPIRED = "quest_seed_expired"
    QUEST_SEED_GENERATED = "quest_seed_generated"
    QUEST_CHAIN_FORMED = "quest_chain_formed"
    QUEST_CHAIN_FINALIZED = "quest_chain_finalized"
    NPC_NEEDED = "npc_needed"
    CHAIN_ELIGIBLE_MATCHED = "chain_eligible_matched"

    # --- dialogue 발행 ---
    DIALOGUE_STARTED = "dialogue_started"
    DIALOGUE_ENDED = "dialogue_ended"
    DIALOGUE_ACTION_DECLARED = "dialogue_action_declared"
    ATTITUDE_REQUEST = "attitude_request"

    # --- item 발행 ---
    ITEM_TRANSFERRED = "item_transferred"
    ITEM_BROKEN = "item_broken"
    ITEM_CREATED = "item_created"

    # --- engine / ModuleManager 발행 ---
    TURN_PROCESSED = "turn_processed"
    CHECK_RESULT = "check_result"
    OBJECTIVE_COMPLETED = "objective_completed"

    # --- engine / ModuleManager 발행 (추가) ---
    PLAYER_MOVED = "player_moved"
    ACTION_COMPLETED = "action_completed"
    ITEM_GIVEN = "item_given"
    OBJECTIVE_FAILED = "objective_failed"

    # --- companion 발행 (신규) ---
    COMPANION_JOINED = "companion_joined"
    COMPANION_MOVED = "companion_moved"
    COMPANION_DISBANDED = "companion_disbanded"

    # --- overlay 발행 ---
    ENVIRONMENT_QUEST_TRIGGER = "environment_quest_trigger"

    # --- combat 발행 (Phase 3+) ---
    COMBAT_ENTITY_SURVIVED = "combat_entity_survived"
```

---

## 7. 페이로드 검증

### 7.1 필수 필드 정의

구현 시 각 이벤트의 data dict에 **필수 키**가 존재하는지 런타임 검증한다. 검증은 `emit()` 시점이 아닌 **핸들러 진입 시점**에서 수행한다 (발행자 부담 최소화).

```python
# 예시: 핸들러 내부
def handle_npc_promoted(event: GameEvent) -> None:
    npc_id = event.data["npc_id"]      # KeyError → 로그 경고 후 무시
    node_id = event.data["node_id"]
    # ...
```

### 7.2 페이로드 스키마 요약

| 이벤트 | 필수 키 | 선택 키 |
|--------|---------|---------|
| `npc_promoted` | npc_id, origin_type, node_id | |
| `npc_created` | npc_id, role, node_id | |
| `npc_died` | npc_id, cause, node_id | |
| `npc_moved` | npc_id, from_node, to_node | |
| `relationship_changed` | source_id, target_id, field, old_value, new_value | old_status, new_status |
| `relationship_reversed` | source_id, target_id, reversal_type, old_status, new_status | |
| `attitude_response` | request_id, npc_id, target_id, attitude_tags, relationship_status | npc_opinions |
| `quest_activated` | quest_id, quest_type, related_npc_ids, target_node_ids | |
| `quest_completed` | quest_id, result, rewards, chain_id | |
| `quest_failed` | quest_id, reason, chain_id | |
| `quest_abandoned` | quest_id, chain_id | |
| `quest_seed_created` | seed_id, npc_id, seed_type, ttl_turns | |
| `quest_seed_expired` | seed_id, npc_id | expiry_result |
| `quest_seed_generated` | seed_id, npc_id, seed_type, context_tags | |
| `quest_chain_formed` | chain_id, quest_ids | |
| `quest_chain_finalized` | chain_id, total_quests, overall_result | |
| `npc_needed` | quest_id, npc_role, node_id | |
| `chain_eligible_matched` | quest_id, chain_id, npc_ref, matched_npc_id | |
| `dialogue_started` | session_id, player_id, npc_id, node_id | |
| `dialogue_ended` | session_id, npc_id, accumulated_deltas, memory_tags, seed_result, dialogue_turns | |
| `dialogue_action_declared` | session_id, npc_id, action_interpretation, validated | |
| `attitude_request` | request_id, npc_id, target_id | include_npc_opinions |
| `item_transferred` | instance_id, from_type, from_id, to_type, to_id, reason | |
| `item_broken` | instance_id, prototype_id, owner_type, owner_id | broken_result |
| `item_created` | instance_id, prototype_id, owner_type, owner_id, source | |
| `turn_processed` | turn_number, player_id | |
| `check_result` | session_id, action, result_tier, dice_result | |
| `objective_completed` | quest_id, objective_id, objective_type | |
| `environment_quest_trigger` | overlay_id, node_id, trigger_type | |
| `combat_entity_survived` | entity_id, node_id | |
| `player_moved` | player_id, from_node, to_node | move_type |
| `action_completed` | player_id, action_type, node_id | result_data |
| `item_given` | player_id, recipient_npc_id, item_prototype_id | instance_id, quantity, item_tags |
| `objective_failed` | quest_id, objective_id, objective_type, fail_reason | trigger_data, turn_number |
| `companion_joined` | companion_id, player_id, npc_id, companion_type | quest_id |
| `companion_moved` | companion_id, npc_id, from_node, to_node | |
| `companion_disbanded` | companion_id, npc_id, disband_reason | quest_id |

기존 이벤트 페이로드 변경분:

| 이벤트 | 변경 | 내용 |
|--------|------|------|
| `check_result` | 선택 키 추가 | `stat`, `context_tags` |
| `objective_completed` | 선택 키 추가 | `trigger_action`, `trigger_data`, `turn_number` |
| `dialogue_started` | 선택 키 추가 | `companion_npc_id` (동행 NPC가 같이 있을 때) |

---

## 8. 구독 등록 패턴

### 8.1 모듈 등록

각 모듈은 `GameModule.initialize(context)` 시점에 EventBus 구독을 등록한다:

```python
class NPCModule(GameModule):
    def initialize(self, context: GameContext) -> None:
        bus = context.event_bus
        bus.subscribe(EventTypes.NPC_NEEDED, self._handle_npc_needed)
        bus.subscribe(EventTypes.COMBAT_ENTITY_SURVIVED, self._handle_combat_survived)
        bus.subscribe(EventTypes.ITEM_CREATED, self._handle_item_created)
```

### 8.2 등록 순서

모듈 초기화 순서에 따라 구독이 등록된다. 핸들러 실행 순서는 등록 순서(FIFO)이므로, 의존 관계가 있는 경우 모듈 초기화 순서를 제어해야 한다.

**권장 초기화 순서** (module-architecture.md Layer 순서 기준):

```
1. npc_core      (Layer 1)
2. item           (Layer 1)
3. relationship   (Layer 2)
4. overlay        (Layer 2)
5. companion      (Layer 3) ← 신규. quest보다 먼저 등록해야 player_moved에서
6. quest          (Layer 3)    companion이 OW보다 먼저 NPC 좌표를 갱신한다.
7. dialogue       (Layer 3)
```

**순서 근거**: `player_moved` 수신 시 companion이 NPC 좌표를 갱신한 뒤, ObjectiveWatcher(engine 내부, 모듈 등록과 별도)가 escort 달성을 판정한다. ObjectiveWatcher는 모듈이 아니라 engine 내부 컴포넌트이므로, 모듈 등록 이후에 구독을 등록하여 항상 마지막에 실행되도록 한다.

```python
class ModuleManager:
    def initialize_all(self, context: GameContext) -> None:
        # 1. 모듈 등록 (Layer 순서)
        for module in self.modules:  # npc_core → item → ... → dialogue
            module.initialize(context)

        # 2. ObjectiveWatcher 등록 (모듈 이후)
        self.objective_watcher = ObjectiveWatcher(context.event_bus, context.quest_db)
        # OW의 subscribe가 항상 마지막 → 핸들러 실행도 마지막
```

---

## 9. npc_promoted vs npc_created 구분

설계 문서 간 `npc_created`와 `npc_promoted`가 혼용되는 경우가 있어 명확히 구분한다.

| 이벤트 | 발생 시점 | 발행자 | 의미 |
|--------|----------|--------|------|
| `npc_promoted` | 배경인물이 NPC로 승격될 때 | npc_core | 승격 결과. 기존 entity_id와 새 npc_id 모두 참조 가능 |
| `npc_created` | quest의 `npc_needed` 요청으로 NPC가 새로 생성될 때 | npc_core | 퀘스트 전용 NPC 생성 결과 |

- `npc_promoted`는 organic한 승격 (PC 상호작용 누적)
- `npc_created`는 scripted한 생성 (퀘스트 필요에 의한 즉시 생성)
- 두 경우 모두 `npcs` 테이블에 레코드가 생성된다
- 구독자는 용도에 맞는 이벤트만 구독한다

---

## 10. Request/Response 패턴

동기식 EventBus에서 요청/응답이 필요한 경우의 패턴.

### 10.1 attitude_request → attitude_response

```
dialogue --attitude_request--> [EventBus]
  [EventBus] --deliver--> relationship
  relationship --attitude_response--> [EventBus]
  [EventBus] --deliver--> dialogue
```

**핵심**: 동기식이므로 `attitude_request` emit 호출이 반환되기 전에 `attitude_response` 핸들러까지 실행 완료된다. dialogue는 emit 직후 바로 결과를 사용할 수 있다.

**구현 패턴**:
```python
class DialogueModule(GameModule):
    def _request_attitude(self, npc_id: str, target_id: str) -> None:
        self._pending_attitude = None  # 응답 슬롯 초기화

        self.event_bus.emit(GameEvent(
            event_type=EventTypes.ATTITUDE_REQUEST,
            data={"request_id": "req_001", "npc_id": npc_id, "target_id": target_id},
            source="dialogue",
        ))

        # 동기식이므로 여기서 이미 _pending_attitude가 채워져 있다
        if self._pending_attitude is None:
            logger.warning("attitude_response 미수신")

    def _handle_attitude_response(self, event: GameEvent) -> None:
        self._pending_attitude = event.data
```

### 10.2 dialogue_started → quest_seed_generated

같은 패턴. dialogue가 `dialogue_started` 발행 → quest 모듈이 5% 판정 → 성공 시 `quest_seed_generated` 발행 → dialogue 수신.

---

## 11. 미구현 이벤트 (Phase별)

### Alpha 필수 (Phase 2)

구현 대상: `npc_promoted`, `npc_created`, `dialogue_started`, `dialogue_ended`, `attitude_request`, `attitude_response`, `quest_seed_generated`, `turn_processed`, `relationship_changed`, `player_moved`, `action_completed`, `item_given`, `objective_failed`, `companion_joined`, `companion_moved`, `companion_disbanded`

### Alpha 후 (Phase 2+)

`quest_activated`, `quest_completed`, `quest_failed`, `quest_abandoned`, `quest_seed_created`, `quest_seed_expired`, `npc_needed`, `objective_completed`, `item_transferred`, `item_created`, `item_broken`, `npc_died`

### Phase 3+

`npc_moved`, `environment_quest_trigger`, `combat_entity_survived`, `quest_chain_formed`, `quest_chain_finalized`, `chain_eligible_matched`, `relationship_reversed`, `dialogue_action_declared`, `check_result`

---

## 12. EventBus 인프라 변경 사항

현재 `src/core/event_bus.py`는 **변경 불필요**. 기존 인프라로 모든 요구사항을 충족한다.

추가 구현 대상:

| 파일 | 내용 | 우선순위 |
|------|------|---------|
| `src/core/event_types.py` | 이벤트 타입 상수 (섹션 6) | 다음 모듈 구현 시 |

---

## 13. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-10 | 최초 작성: 5개 설계 문서 이벤트 통합, 순환 분석, 페이로드 스키마 |
| 1.1 | 2026-02-12 | quest-action-integration.md, companion-system.md 반영: 이벤트 7종 추가, 구독 매트릭스 갱신, 순환 분석 3건 추가, ObjectiveWatcher 구독 반영, 모듈 초기화 순서 갱신 |
