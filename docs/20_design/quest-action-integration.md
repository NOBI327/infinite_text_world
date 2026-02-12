# ITW 퀘스트 연동 액션 설계서

**버전**: 1.1  
**작성일**: 2026-02-12  
**상태**: 확정  
**관련**: quest-system.md (v1.1), dialogue-system.md, game-loop.md, event-bus.md, companion-system.md, item-system.md

---

## 1. 개요

### 1.1 목적

이 문서는 게임 액션과 퀘스트 목표(Objective)를 연결하는 규칙을 정의한다. 어떤 액션이 어떤 목표를 달성/실패시키는가, 판정의 책임자는 누구인가, 대체 목표 생성 시 PC에게 어떤 선택지를 제시하는가를 확정한다.

### 1.2 핵심 원칙

- **Python 판정, LLM 서술**: 목표 달성/실패 판정은 Python, LLM은 결과 서술만
- **의뢰 추상화**: 모든 목표는 "대상을 납품처/목표 상태로" 환원 (quest-system.md v1.1)
- **수단 불문**: 입수 방법·이동 경로·해결 수단을 판정하지 않음. 최종 조건만 판정
- **분산 감지, 중앙 발행**: 사건은 각 모듈이 이벤트로 보고, engine(ObjectiveWatcher)이 목표 대조 후 발행
- **대체 목표 시 의뢰주 보고 필수**: 목표 실패 → 선택지에 반드시 "의뢰주에게 보고" 포함
- **EventBus 통신**: 모듈간 직접 호출 금지

### 1.3 Objective 유형 (quest-system.md v1.1 기준)

| 유형 | 의미 | 달성 조건 요약 |
|------|------|-------------|
| `reach_node` | 장소 도달 | PC가 목표 노드에 도착 (+ 선택적 액션 수행) |
| `deliver` | 아이템 전달 | 납품처 NPC에게 아이템을 건네면 완료 |
| `escort` | NPC 호위 | 대상 NPC와 함께(동행) 목표지 도착 |
| `talk_to_npc` | 대화 | 목표 NPC와 대화 (+ 선택적 주제 충족) |
| `resolve_check` | 판정 성공 | Protocol T.A.G. 판정에서 조건 충족 |

### 1.4 범위

| 포함 | 제외 |
|------|------|
| 목표 유형별 달성/실패 판정 규칙 | 퀘스트 발생/체이닝 (quest-system.md) |
| objective_completed / objective_failed 이벤트 설계 | 대화 세션 관리 (dialogue-system.md) |
| 대체 목표 생성 흐름과 PC 선택지 | Protocol T.A.G. 판정 상세 |
| 대화 중 행동 선언 → 목표 달성 흐름 | 동행 시스템 상세 (companion-system.md) |
| 기존 액션 확장 및 신규 액션 | 오버레이 연동 |

---

## 2. 판정 아키텍처

### 2.1 ObjectiveWatcher

engine(ModuleManager)에 속하는 컴포넌트. 각 모듈의 사건 이벤트를 구독하고, 활성 목표와 대조하여 달성/실패 여부를 판정한다.

```
[모듈] → 사건 이벤트 발행 (이동, 아이템 전달, 대화, 판정 결과 등)
  → [ObjectiveWatcher] 구독: 사건을 활성 목표와 대조
    ├─ 달성 → objective_completed 발행 → [quest 모듈] 수신
    └─ 실패 감지 → objective_failed 발행 → [quest 모듈] 수신
```

개별 모듈(dialogue, item 등)은 퀘스트 DB를 참조하지 않는다. ObjectiveWatcher만 활성 목표 목록을 관리한다.

### 2.2 ObjectiveWatcher 구조

```python
class ObjectiveWatcher:
    """활성 퀘스트 목표를 감시하고 달성/실패 시 이벤트를 발행한다."""
    
    def __init__(self, event_bus: EventBus, quest_db: QuestDatabase):
        self.event_bus = event_bus
        self.quest_db = quest_db
        self._register_watchers()
    
    def _register_watchers(self) -> None:
        """목표 유형별 감시 이벤트 구독"""
        bus = self.event_bus
        
        # reach_node
        bus.subscribe(EventTypes.PLAYER_MOVED, self._check_reach_objectives)
        bus.subscribe(EventTypes.ACTION_COMPLETED, self._check_action_reach_objectives)
        
        # deliver
        bus.subscribe(EventTypes.ITEM_GIVEN, self._check_deliver_objectives)
        
        # escort
        bus.subscribe(EventTypes.PLAYER_MOVED, self._check_escort_objectives)
        
        # talk_to_npc
        bus.subscribe(EventTypes.DIALOGUE_STARTED, self._check_talk_objectives_start)
        bus.subscribe(EventTypes.DIALOGUE_ENDED, self._check_talk_objectives_end)
        
        # resolve_check
        bus.subscribe(EventTypes.CHECK_RESULT, self._check_resolve_objectives)
        
        # escort 실패 감지 (대상 사망/부재)
        bus.subscribe(EventTypes.NPC_DIED, self._check_escort_target_dead)
    
    def _get_active_objectives(self, objective_type: str) -> list[Objective]:
        """특정 유형의 활성 목표 조회"""
        return self.quest_db.get_objectives(
            status="active",
            objective_type=objective_type,
        )
```

---

## 3. 목표 유형별 달성 판정 규칙

### 3.1 reach_node — 도달 목표

#### 트리거와 판정

| 트리거 이벤트 | 판정 규칙 |
|-------------|----------|
| `player_moved` | PC 현재 좌표 == target.node_id |
| `action_completed` | require_action이 설정된 경우, 해당 노드에서 해당 액션 수행 시 |

#### 판정 흐름

```
PC: "move e"
  → engine: 이동 처리 → player_moved 발행 {to_node: "5_3"}
  → ObjectiveWatcher: 활성 reach_node 목표 순회
    → target.node_id == "5_3"?
      ├─ Yes, require_action == None → objective_completed 발행
      ├─ Yes, require_action == "investigate" → 대기 (도착만으로 불충분)
      └─ No → 무동작

PC: "investigate" (노드 5_3에서)
  → engine: 조사 처리 → action_completed 발행 {action_type: "investigate", node_id: "5_3"}
  → ObjectiveWatcher: require_action == "investigate" && node_id 매칭
    → objective_completed 발행
```

#### 판정 코드

```python
def _check_reach_objectives(self, event: GameEvent) -> None:
    to_node = event.data["to_node"]
    
    for obj in self._get_active_objectives("reach_node"):
        target = obj.target
        if target["node_id"] != to_node:
            continue
        
        # require_action이 없으면 도착만으로 달성
        if not target.get("require_action"):
            self._emit_completed(obj, trigger_action="move", trigger_data=event.data)

def _check_action_reach_objectives(self, event: GameEvent) -> None:
    action_type = event.data["action_type"]
    node_id = event.data["node_id"]
    
    for obj in self._get_active_objectives("reach_node"):
        target = obj.target
        if target["node_id"] != node_id:
            continue
        if target.get("require_action") != action_type:
            continue
        
        self._emit_completed(obj, trigger_action=action_type, trigger_data=event.data)
```

### 3.2 deliver — 전달 목표

#### 핵심 원칙: 수단 불문

입수 방법(harvest, 거래, 제작, 절도 등)을 판정하지 않는다. **납품처 NPC에게 아이템을 건네는 행위**만 판정한다.

#### 트리거와 판정

| 트리거 이벤트 | 상황 | 판정 규칙 |
|-------------|------|----------|
| `item_given` | give 액션 또는 대화 중 gift_offered | recipient == target.recipient_npc_id && 아이템 매칭 |

#### 판정 흐름

```
PC: "give hans healing_herb" (또는 대화 중 선물/전달)
  → engine/dialogue: item_given 발행
    {recipient_npc_id: "npc_hans_042", item_prototype_id: "healing_herb", quantity: 1}
  → ObjectiveWatcher: deliver 목표 순회
    → recipient 매칭 && 아이템 매칭 && 수량 충족?
      ├─ Yes → objective_completed 발행
      └─ No → 무동작
```

#### 아이템 매칭 규칙

```python
def _check_deliver_objectives(self, event: GameEvent) -> None:
    recipient = event.data["recipient_npc_id"]
    given_proto = event.data["item_prototype_id"]
    given_qty = event.data.get("quantity", 1)
    given_tags = event.data.get("item_tags", [])
    
    for obj in self._get_active_objectives("deliver"):
        target = obj.target
        if target["recipient_npc_id"] != recipient:
            continue
        
        # 프로토타입 ID 매칭 (특정 아이템)
        if "item_prototype_id" in target:
            if target["item_prototype_id"] != given_proto:
                continue
        
        # 태그 매칭 (범용 — "약초 아무거나")
        elif "item_tag" in target:
            if target["item_tag"] not in given_tags:
                continue
        
        # 수량 체크 (누적)
        required_qty = target.get("quantity", 1)
        delivered = self._get_cumulative_delivery(obj.objective_id) + given_qty
        if delivered < required_qty:
            continue  # 아직 부족, 진행 중
        
        self._emit_completed(obj, trigger_action="give", trigger_data=event.data)
```

#### deliver 퀘스트 예시

```
"약초를 구해와" (납품처 = 의뢰인)
  의뢰인 한스가 약초 3개 요청
  → Objective: deliver {item_prototype_id: "healing_herb", quantity: 3, recipient_npc_id: "npc_hans_042"}
  → PC가 어떻게 구하든 상관없음 (harvest, 거래, 다른 퀘스트 보상 등)
  → PC: "give hans healing_herb" (3번 또는 3개 한번에)
  → objective_completed

"편지를 B에게 전해줘" (납품처 = 제3자)
  의뢰인 한스가 편지를 PC에게 give → PC 인벤토리에 편지
  → Objective: deliver {item_prototype_id: "letter_hans_01", recipient_npc_id: "npc_doctor_015"}
  → PC가 의사에게 이동 후 give
  → objective_completed
```

### 3.3 escort — 호위 목표

#### 핵심: companion-system.md 연동

escort 목표의 달성에는 동행 시스템이 필요하다. 대상 NPC가 **동행 상태(companion)**로 PC와 함께 목표지에 도착해야 한다.

#### 대상 초기 상태별 흐름

| 초기 상태 | 의미 | 선행 조건 |
|----------|------|----------|
| `present` | 대상이 PC 위치에 있음 | 없음 — 즉시 동행 요청 가능 |
| `missing` | 대상 위치를 모름 | reach_node(추정 위치) → 발견 → 분기 |
| `unknown` | 생존 여부 불명 | reach_node(추정 위치) → 생존 분기 → 후속 처리 |

#### 판정 흐름 (present)

```
퀘스트 시작: escort {target_npc_id: "npc_hans_042", destination: "7_3", initial_status: "present"}
  → 한스가 동행 요청 수락 (퀘스트 동행이므로 수락 확률 높음)
  → 동행 상태 진입

PC: "move e" ... (이동 반복)
  → player_moved 발행
  → ObjectiveWatcher:
    → PC 위치 == destination "7_3"?
    → companion 모듈에 target_npc_id가 동행 중인지 확인?
      ├─ 둘 다 Yes → objective_completed 발행
      └─ 아니면 → 무동작
```

#### 판정 흐름 (missing/unknown — 구출)

```
퀘스트 시작: escort {target_npc_id: "npc_fritz_043", destination: "2_2",
                     initial_status: "unknown", location_hint: "5_8"}
  → 암묵적 선행: reach_node(5_8) — 목표 목록에는 포함하지 않음, 힌트로만 제공

PC가 5_8 도착 → 현장 상황 판정 (Python)
  ├─ 생존 → NPC 발견 이벤트 → 동행 요청 → escort 진행
  ├─ 사망 → npc_died 이벤트 → ObjectiveWatcher: objective_failed 발행
  └─ 부재 → 대상 미발견 → 추가 탐색 필요 (목표 유지, 힌트 갱신)
```

#### 판정 코드

```python
def _check_escort_objectives(self, event: GameEvent) -> None:
    """player_moved 시 escort 달성 체크"""
    to_node = event.data["to_node"]
    player_id = event.data["player_id"]
    
    for obj in self._get_active_objectives("escort"):
        target = obj.target
        if target["destination_node_id"] != to_node:
            continue
        
        # 동행 상태 확인 (companion 모듈 데이터 — DB 조회)
        if not self._is_companion(player_id, target["target_npc_id"]):
            continue
        
        self._emit_completed(obj, trigger_action="move", trigger_data=event.data)

def _check_escort_target_dead(self, event: GameEvent) -> None:
    """npc_died 시 escort 대상 사망 체크"""
    dead_npc_id = event.data["npc_id"]
    
    for obj in self._get_active_objectives("escort"):
        if obj.target["target_npc_id"] != dead_npc_id:
            continue
        
        self._emit_failed(
            obj,
            fail_reason="target_dead",
            trigger_data=event.data,
        )
```

### 3.4 talk_to_npc — 대화 목표

#### 트리거와 판정

| 조건 | 트리거 이벤트 | 판정 규칙 |
|------|-------------|----------|
| 단순 접촉 (require_topic == None) | `dialogue_started` | npc_id 매칭 |
| 주제 요구 (require_topic 설정) | `dialogue_ended` | npc_id 매칭 && topic_tags에 주제 포함 |

#### 판정 흐름

```
단순 접촉:
  PC: "talk fritz"
  → dialogue_started {npc_id: "npc_fritz_043"}
  → ObjectiveWatcher: talk_to_npc(npc_fritz_043, require_topic=None) 매칭
  → objective_completed 발행

주제 요구:
  PC: "talk merchant" → 대화 세션 → 분쟁 중재 주제 진행 → 세션 종료
  → dialogue_ended {npc_id: "npc_merchant_012", topic_tags: ["trade", "dispute_resolution"]}
  → ObjectiveWatcher: require_topic "dispute_resolution" ∈ topic_tags?
  → Yes → objective_completed 발행
```

#### 판정 코드

```python
def _check_talk_objectives_start(self, event: GameEvent) -> None:
    npc_id = event.data["npc_id"]
    
    for obj in self._get_active_objectives("talk_to_npc"):
        target = obj.target
        if target["npc_id"] != npc_id:
            continue
        if target.get("require_topic"):
            continue  # 주제 요구는 dialogue_ended에서 판정
        
        self._emit_completed(obj, trigger_action="talk", trigger_data=event.data)

def _check_talk_objectives_end(self, event: GameEvent) -> None:
    npc_id = event.data["npc_id"]
    topic_tags = event.data.get("topic_tags", [])
    memory_tags = event.data.get("memory_tags", [])
    all_tags = set(topic_tags + memory_tags)
    
    for obj in self._get_active_objectives("talk_to_npc"):
        target = obj.target
        if target["npc_id"] != npc_id:
            continue
        if not target.get("require_topic"):
            continue  # 단순 접촉은 dialogue_started에서 이미 처리
        if target["require_topic"] not in all_tags:
            continue
        
        self._emit_completed(obj, trigger_action="talk", trigger_data=event.data)
```

### 3.5 resolve_check — 판정 성공 목표

#### 트리거와 판정

| 트리거 이벤트 | 판정 규칙 |
|-------------|----------|
| `check_result` | result_tier >= min_result_tier && 스탯 매칭 && 컨텍스트 태그 매칭 |

#### 판정 흐름

```
PC: (대화 중) "다리를 보강한다"
  → dialogue_action_declared → engine: d6 Dice Pool 판정
  → check_result {result_tier: "success", stat: "EXEC", context_tags: ["bridge_repair"]}
  → ObjectiveWatcher: resolve_check(min: success, context: bridge_repair) 매칭
  → objective_completed 발행
```

#### Alpha 전투 추상화

Alpha에서 전투는 resolve_check로 처리한다. Beta에서 전투 시스템 도입 시 check_type: "COMBAT"을 추가하고 engine이 combat으로 라우팅한다.

```
Alpha: "도적 처리" → resolve_check {check_type: "EXEC", context_tag: "combat_bandit"}
Beta:  "도적 처리" → resolve_check {check_type: "COMBAT", context_tag: "combat_bandit"}
```

Objective 구조 변경 없이 engine 라우팅만 추가.

#### 판정 코드

```python
def _check_resolve_objectives(self, event: GameEvent) -> None:
    result_tier = event.data["result_tier"]
    stat = event.data.get("stat")
    context_tags = event.data.get("context_tags", [])
    
    TIER_ORDER = {"failure": 0, "partial": 1, "success": 2, "critical": 3}
    
    for obj in self._get_active_objectives("resolve_check"):
        target = obj.target
        
        # 최소 성공 등급 체크
        min_tier = target.get("min_result_tier", "success")
        if TIER_ORDER.get(result_tier, 0) < TIER_ORDER.get(min_tier, 2):
            continue
        
        # 스탯 체크 (지정된 경우)
        if target.get("check_type") and target["check_type"] != stat:
            continue
        
        # 컨텍스트 태그 체크 (지정된 경우)
        if target.get("context_tag") and target["context_tag"] not in context_tags:
            continue
        
        self._emit_completed(obj, trigger_action="check", trigger_data=event.data)
```

### 3.6 달성 판정 요약

| 목표 유형 | 주 트리거 | 판정 조건 | 비고 |
|----------|----------|----------|------|
| `reach_node` | player_moved | 좌표 일치 | require_action 시 action_completed 추가 대기 |
| `deliver` | item_given | 납품처 + 아이템 + 수량 | 입수 방법 불문 |
| `escort` | player_moved | 좌표 일치 + 동행 상태 확인 | companion 모듈 연동 |
| `talk_to_npc` | dialogue_started/ended | NPC 매칭 + 주제 매칭 | require_topic 유무로 시점 분기 |
| `resolve_check` | check_result | 등급 + 스탯 + 컨텍스트 | Alpha에서 전투 대체 |

---

## 4. objective_completed / objective_failed 이벤트

### 4.1 objective_completed 페이로드

```python
{
    "quest_id": str,           # 해당 퀘스트 ID
    "objective_id": str,       # 달성된 목표 ID
    "objective_type": str,     # "reach_node" | "deliver" | "escort" | "talk_to_npc" | "resolve_check"
    "trigger_action": str,     # 트리거한 액션 ("move", "give", "talk", "check" 등)
    "trigger_data": dict,      # 트리거 상세
    "turn_number": int,        # 달성 턴
}
```

### 4.2 objective_failed 페이로드

```python
{
    "quest_id": str,           # 해당 퀘스트 ID
    "objective_id": str,       # 실패한 목표 ID
    "objective_type": str,
    "fail_reason": str,        # "target_dead" | "target_missing" | "item_unobtainable" | "time_expired"
    "trigger_data": dict,      # 실패 상황 상세
    "turn_number": int,
}
```

### 4.3 quest 모듈의 처리

```
objective_completed 수신
  → Objective.status = "completed", completed_turn 기록
  → 퀘스트 전체 완료 판정 (섹션 4.4)
  → PC 알림: "[시스템] 퀘스트 'X' — 목표 달성: Y (1/2)"

objective_failed 수신
  → Objective.status = "failed", failed_turn, fail_reason 기록
  → 대체 목표 생성 (섹션 5)
```

### 4.4 퀘스트 완료 판정

```python
def evaluate_quest_result(quest: Quest, objectives: list[Objective]) -> str | None:
    """퀘스트 결과 판정 — 대체 목표 포함"""
    
    original = [o for o in objectives if not o.is_replacement]
    replacements = [o for o in objectives if o.is_replacement]
    
    original_completed = [o for o in original if o.status == "completed"]
    original_failed = [o for o in original if o.status == "failed"]
    replacement_completed = [o for o in replacements if o.status == "completed"]
    
    # 원본 목표 전부 달성 → success
    if len(original_completed) == len(original):
        return "success"
    
    # 원본 일부 실패 + 대체 목표 달성 → partial
    if original_failed and replacement_completed:
        return "partial"
    
    # urgent 시간 초과
    if quest.urgency == "urgent" and quest.time_limit:
        elapsed = current_turn - quest.activated_turn
        if elapsed >= quest.time_limit:
            if len(original_completed) > 0 or replacement_completed:
                return "partial"
            return "failure"
    
    # 활성 목표 남아있음 → 진행 중
    active = [o for o in objectives if o.status == "active"]
    if active:
        return None
    
    return "failure"
```

---

## 5. 대체 목표 생성

### 5.1 원칙

Objective 실패 시, Python이 **대체 목표 후보를 생성**하고 PC에게 선택지를 제시한다. 선택지에는 반드시 **"의뢰주에게 보고"**가 포함된다.

### 5.2 생성 흐름

```
objective_failed 수신 (quest 모듈)
  │
  ├─ 1. fail_reason 기반 대체 후보 생성
  │    ├─ [필수] talk_to_npc(의뢰인) — "의뢰주에게 보고"
  │    │    replacement_origin: "client_consult"
  │    └─ [자동] fail_reason별 대체 후보 (0~2개)
  │         replacement_origin: "auto_fallback"
  │
  ├─ 2. PC에게 선택지 제시 (시스템 메시지)
  │
  └─ 3. PC 선택 → 해당 대체 목표를 active로 추가
       (또는 PC가 자유 행동 → 자유 행동 결과에 따라 판정)
```

### 5.3 fail_reason별 대체 후보

| fail_reason | 필수 대체 | 자동 대체 후보 |
|-------------|----------|--------------|
| `target_dead` | talk_to_npc(의뢰인) "보고" | deliver(유품, 의뢰인), resolve_check(사인 조사) |
| `target_missing` | talk_to_npc(의뢰인) "보고" | reach_node(추가 탐색), talk_to_npc(목격자) |
| `item_unobtainable` | talk_to_npc(의뢰인) "보고" | deliver(대체품, 의뢰인) |
| `time_expired` | talk_to_npc(의뢰인) "보고" | — (자동 대체 없음) |

### 5.4 PC 선택지 제시

```
[시스템] 프리츠가 사망한 것을 확인했다.
  1. 유품을 수습하여 한스에게 가져간다    → deliver(유품, 한스)
  2. 한스에게 돌아가서 보고한다            → talk_to_npc(한스)
  3. 주변을 더 조사한다                   → resolve_check(사인 조사)
  (또는 다른 행동을 자유롭게 선언할 수 있다)
```

선택지는 가이드일 뿐, PC는 제시되지 않은 행동도 할 수 있다. 이 경우 ObjectiveWatcher가 기존 메커니즘으로 판정한다.

### 5.5 대체 목표 생성 코드

```python
REPLACEMENT_TEMPLATES: dict[str, list[dict]] = {
    "target_dead": [
        {
            "type": "deliver",
            "description_template": "{target_name}의 유품을 {client_name}에게 전달하라",
            "target_template": {
                "item_tag": "belongings_{target_npc_id}",
                "recipient_npc_id": "{client_npc_id}",
            },
            "origin": "auto_fallback",
        },
        {
            "type": "resolve_check",
            "description_template": "{target_name}의 사인을 조사하라",
            "target_template": {
                "min_result_tier": "success",
                "context_tag": "investigate_death_{target_npc_id}",
            },
            "origin": "auto_fallback",
        },
    ],
    "target_missing": [
        {
            "type": "reach_node",
            "description_template": "주변을 추가로 탐색하라",
            "target_template": {
                "node_id": "{nearby_node}",
                "require_action": "investigate",
            },
            "origin": "auto_fallback",
        },
        {
            "type": "talk_to_npc",
            "description_template": "목격자를 찾아 대화하라",
            "target_template": {
                "npc_id": "{nearest_npc}",
                "require_topic": "missing_{target_npc_id}",
            },
            "origin": "auto_fallback",
        },
    ],
    "item_unobtainable": [
        {
            "type": "deliver",
            "description_template": "대체품을 {client_name}에게 전달하라",
            "target_template": {
                "item_tag": "substitute_{item_tag}",
                "recipient_npc_id": "{client_npc_id}",
            },
            "origin": "auto_fallback",
        },
    ],
}

# 모든 fail_reason에 공통 필수 대체
CLIENT_CONSULT_TEMPLATE = {
    "type": "talk_to_npc",
    "description_template": "{client_name}에게 상황을 보고하라",
    "target_template": {
        "npc_id": "{client_npc_id}",
        "require_topic": None,
    },
    "origin": "client_consult",
}


def generate_replacement_objectives(
    failed_obj: Objective,
    quest: Quest,
    context: dict,
) -> list[Objective]:
    """실패한 목표에 대한 대체 목표 후보 생성"""
    
    replacements = []
    
    # 필수: 의뢰주 보고
    consult = _instantiate_template(CLIENT_CONSULT_TEMPLATE, quest, context)
    consult.is_replacement = True
    consult.replaced_objective_id = failed_obj.objective_id
    consult.replacement_origin = "client_consult"
    replacements.append(consult)
    
    # 자동: fail_reason별 대체
    templates = REPLACEMENT_TEMPLATES.get(failed_obj.fail_reason, [])
    for tmpl in templates:
        obj = _instantiate_template(tmpl, quest, context)
        obj.is_replacement = True
        obj.replaced_objective_id = failed_obj.objective_id
        obj.replacement_origin = "auto_fallback"
        replacements.append(obj)
    
    return replacements
```

### 5.6 의뢰주 보고 → 퀘스트 분기

의뢰주 보고(client_consult)를 선택하여 의뢰인과 대화하면, **대화 내에서 새 퀘스트 시드가 발생할 수 있다.** 이는 5% 확률 판정이 아니라, **실패 보고 컨텍스트에 의한 높은 확률 시드**로 처리한다.

```
PC: "talk hans" (구출 실패 후 보고)
  → dialogue_started 발행
  → quest 모듈: 실패 보고 대화 감지
    → 시드 발생 확률: 50% (통상 5%의 10배)
    → 성공 시 quest_seed_generated 발행
      context_tags에 원본 퀘스트 태그 + fail_reason 포함

LLM 컨텍스트:
  "quest_failure_report": {
    "failed_quest": "실종된 사촌",
    "fail_reason": "target_dead",
    "instruction": "의뢰인이 실패 보고를 받는다. 감정적 반응 후, 후속 행동을 제안할 수 있다."
  }

한스: "프리츠가... 그런... 누가 그런 짓을... 범인을 찾아줄 수 있겠나?"
  → PC 수락 → 새 퀘스트 (rivalry, "범인 추적")
    chain_id 계승 가능
  → PC 거부 → 시드 NPC 기억 저장, TTL 시작
```

원본 퀘스트: 보고 대체 목표 달성 → result = "partial".

---

## 6. 대화 중 행동 선언과 목표 달성

### 6.1 기존 흐름 (dialogue-system.md 섹션 5)

```
PC 행동 선언 → LLM: action_interpretation → Python: constraints 검증
  → dialogue_action_declared → engine: d6 판정 → check_result → dialogue: 서술 반영
```

### 6.2 목표 달성 연동

check_result 수신 시 ObjectiveWatcher가 resolve_check 목표를 점검한다. 기존 흐름에 변경 없이 ObjectiveWatcher의 구독으로 처리.

```
check_result 발행
  → dialogue: 서술 반영 (기존)
  → ObjectiveWatcher: resolve_check 매칭 → objective_completed 발행 (추가)
```

### 6.3 대화 중 목표 달성 시 대화 유지

목표 달성이 대화를 끊지 않는다. 다음 LLM 호출에 달성 사실을 주입한다.

```
[대화 턴 N] check_result: success → objective_completed 발행

[대화 턴 N+1] LLM 컨텍스트 추가:
  "quest_update": {
    "quest_id": "quest_bridge_001",
    "objective_completed": "다리를 보강하라",
    "remaining_objectives": 0,
    "quest_completed": true,
    "instruction": "PC가 목표를 달성했다. NPC가 인지하고 반응하라. resolution_comment를 META에 포함하라."
  }
```

### 6.4 대화 중 목표 실패 처리

대화 중 escort 대상 사망 등으로 목표가 실패하는 경우도 동일하게 처리:

```
[대화 턴 N] npc_died → objective_failed 발행

[대화 턴 N+1] LLM 컨텍스트 추가:
  "quest_update": {
    "quest_id": "quest_fritz_001",
    "objective_failed": "프리츠를 마을로 호위하라",
    "fail_reason": "target_dead",
    "replacement_options": ["유품 수습", "사인 조사", "의뢰주 보고"],
    "instruction": "목표가 실패했다. 상황을 서술하고, NPC가 반응하라."
  }
```

대체 목표 선택지는 대화 종료 후 시스템 메시지로 제시한다. 대화 중에는 서술만.

---

## 7. 기존 액션 확장 및 신규 액션

### 7.1 신규 액션

| 액션 | 형식 | 용도 | 소비 턴 |
|------|------|------|---------|
| `talk <npc>` | `talk hans` | NPC 대화 세션 시작 | 1턴 (세션 전체) |
| `give <npc> <item>` | `give hans herb` | NPC에게 아이템 전달 | 1턴 |
| `use <item>` | `use rope` | 아이템 사용 (환경 적용) | 1턴 |

#### talk

dialogue-system.md에 정의. 이 문서에서는 talk_to_npc 목표의 트리거 역할만.

#### give

deliver 목표의 핵심 트리거. 대화 밖에서 아이템을 NPC에게 전달한다.

```
PC: "give hans healing_herb"
  → engine: PC 인벤토리에 healing_herb 존재? → Yes
  → engine: hans가 같은 노드? → Yes
  → item 모듈: 소유권 이전 처리
  → item_given 발행
    {recipient_npc_id: "npc_hans_042", item_prototype_id: "healing_herb", quantity: 1}
  → ObjectiveWatcher: deliver 목표 체크
  → narrative_service: 전달 서술 생성
```

대화 중 전달은 gift_offered META로 처리되며, 동일하게 item_given 이벤트를 발행한다.

#### use

아이템을 환경에 사용. resolve_check의 트리거가 될 수 있다.

```
PC: "use rope" (절벽에서)
  → engine: rope 보유 확인 → 상황 판정 (T.A.G.)
  → check_result 발행 → ObjectiveWatcher: resolve_check 체크
```

상세 설계는 item-system.md 확장 시. 이 문서에서는 퀘스트 훅만 확보.

### 7.2 기존 액션의 퀘스트 훅

기존 액션 코드는 변경하지 않는다. 처리 완료 후 이벤트를 발행하고, ObjectiveWatcher가 구독한다.

| 기존 액션 | 훅 이벤트 | 감시 대상 목표 |
|----------|----------|-------------|
| `move` | `player_moved` | reach_node, escort |
| `look` | `action_completed` | reach_node (require_action: look) |
| `investigate` | `action_completed` | reach_node (require_action: investigate) |
| `harvest` | `item_created` → `item_given`(자동 입수) | (deliver와 간접 연동) |
| `rest` | — | 퀘스트 연동 없음 |
| `enter` / `exit` / `up` / `down` | `player_moved` | reach_node |

**harvest와 deliver의 관계**: harvest로 아이템을 획득하는 것은 deliver 목표를 달성하지 않는다. deliver는 **납품처 NPC에게 건네는 행위**만 판정한다. harvest는 입수 수단일 뿐이다.

### 7.3 신규 이벤트

| 이벤트 | 페이로드 | 발행자 | 구독자 |
|--------|----------|--------|--------|
| `player_moved` | `{player_id, from_node, to_node, move_type}` | engine | ObjectiveWatcher |
| `action_completed` | `{player_id, action_type, node_id, result_data}` | engine | ObjectiveWatcher |
| `item_given` | `{player_id, recipient_npc_id, item_prototype_id, item_instance_id, quantity, item_tags}` | engine / dialogue | ObjectiveWatcher |
| `objective_failed` | `{quest_id, objective_id, objective_type, fail_reason, trigger_data, turn_number}` | ObjectiveWatcher | quest |

`move_type`: "walk" | "enter" | "exit" | "up" | "down"

`action_type`: "look" | "investigate" | "harvest" | "give" | "use"

---

## 8. 대화 외 자유 행동

### 8.1 Alpha 미지원

대화 밖에서 자유 형식 행동 선언("밧줄을 묶어서 내려간다")은 Alpha에서 미지원. 정형 명령어와 대화 중 행동 선언만 지원한다.

### 8.2 Beta 확장 방향

```
PC: "절벽에 밧줄을 묶어서 내려간다"
  → engine: 정형 명령어 매칭 실패
  → engine: 행동 해석 LLM 호출 (narrative_service 확장)
    → action_interpretation → constraints 검증 → d6 판정
    → check_result → ObjectiveWatcher: resolve_check 체크
```

---

## 9. 전체 흐름 예시

### 9.1 deliver 퀘스트 — "약초를 가져다줘"

```
퀘스트 활성화: deliver 유형
  Objective: deliver {item_prototype_id: "healing_herb", quantity: 3, recipient: "npc_hans_042"}

턴 60: PC: "harvest" (약초 지대에서)
  → item_created → PC 인벤토리에 healing_herb 추가
  → (deliver 목표는 무반응 — give를 기다림)

턴 61: PC: "harvest" → 2개째
턴 62: PC: "harvest" → 3개째

턴 65: PC: "move w" ... → 한스 위치 도착
턴 66: PC: "give hans healing_herb" (3개)
  → item_given {recipient: hans, item: healing_herb, qty: 3}
  → ObjectiveWatcher: deliver 매칭! → objective_completed
  → quest: 유일한 목표 → quest_completed (success)
  → [시스템] "퀘스트 '약초 전달' 완료!"
```

### 9.2 escort 퀘스트 — 구출 → 사망 분기 → 의뢰주 보고

```
퀘스트 활성화: escort 유형
  Objective: escort {target: fritz, destination: "2_2", initial_status: "unknown", hint: "5_8"}

턴 50: PC가 5_8 도착 → 프리츠 사망 확인
  → npc_died {npc_id: "npc_fritz_043", cause: "bandit_attack"}
  → ObjectiveWatcher: escort 대상 사망 → objective_failed {fail_reason: "target_dead"}
  → quest 모듈: 대체 목표 생성

  [시스템] 프리츠가 사망한 것을 확인했다.
    1. 유품을 수습하여 한스에게 가져간다
    2. 한스에게 돌아가서 보고한다
    3. 사인을 조사한다

턴 51: PC 선택: "2. 한스에게 보고"
  → talk_to_npc(hans) 대체 목표 활성화

턴 55: PC: "talk hans"
  → dialogue_started → ObjectiveWatcher: talk_to_npc(hans) 매칭 → objective_completed
  → quest: 원본 실패 + 대체 달성 → result = "partial"
  → 대화 내에서:
    한스: "프리츠가... 그런... 범인을 찾아줄 수 있겠나?"
    → quest 모듈: 실패 보고 시드 50% 판정 → 성공
    → 새 퀘스트 시드: rivalry "범인 추적" (chain_id 계승)
```

### 9.3 대화 중 resolve_check 달성

```
퀘스트: "무너진 다리 수리" (resolve)
  Objective: resolve_check {min_result_tier: "success", context_tag: "bridge_repair"}

턴 55: PC가 목수 NPC와 대화 중
  PC: "남은 목재와 밧줄로 임시 지지대를 만들어보겠다"
  → LLM: action_interpretation {stat: "EXEC", modifiers: [{source: "item_use", item_id: "rope"}]}
  → Python: rope ∈ pc_items → 통과
  → dialogue_action_declared → engine: d6 판정 → success
  → check_result {result_tier: "success", context_tags: ["bridge_repair"]}
  → dialogue: 서술 반영
  → ObjectiveWatcher: resolve_check 매칭 → objective_completed
  → quest: quest_completed (success)
  
  [대화 턴 N+1]
  목수: "오, 이게 되네! 손재주가 있군."
  → meta: {resolution_comment: {method_tag: "improvised_repair", impression_tag: "impressed"}}
```

---

## 10. EventBus 인터페이스

### 10.1 신규 이벤트 (이 문서에서 추가)

| 이벤트 | 페이로드 | 발행자 | 구독자 |
|--------|----------|--------|--------|
| `player_moved` | `{player_id, from_node, to_node, move_type}` | engine | ObjectiveWatcher |
| `action_completed` | `{player_id, action_type, node_id, result_data}` | engine | ObjectiveWatcher |
| `item_given` | `{player_id, recipient_npc_id, item_prototype_id, instance_id, quantity, item_tags}` | engine/dialogue | ObjectiveWatcher, relationship |
| `objective_failed` | `{quest_id, objective_id, objective_type, fail_reason, trigger_data, turn_number}` | ObjectiveWatcher | quest |

### 10.2 기존 이벤트의 ObjectiveWatcher 구독

| 이벤트 | 발행자 | 감시 목표 유형 |
|--------|--------|-------------|
| `dialogue_started` | dialogue | talk_to_npc (단순 접촉) |
| `dialogue_ended` | dialogue | talk_to_npc (주제 요구) |
| `check_result` | engine | resolve_check |
| `npc_died` | npc_core | escort (대상 사망 감지) |
| `objective_completed` | ObjectiveWatcher | quest (퀘스트 완료 판정) |

### 10.3 구독 매트릭스 갱신 (event-bus.md 반영분)

기존 매트릭스에 추가할 행/열:

| 이벤트 \ 구독자 | ObjectiveWatcher | quest | relationship |
|---------------|:----------------:|:-----:|:------------:|
| `player_moved` | ● | | |
| `action_completed` | ● | | |
| `item_given` | ● | | ● |
| `objective_completed` | | ● | |
| `objective_failed` | | ● | |

기존 이벤트에 ObjectiveWatcher 구독 추가:

| 이벤트 | 기존 구독자 | 추가 |
|--------|-----------|------|
| `dialogue_started` | quest | + ObjectiveWatcher |
| `dialogue_ended` | relationship, quest, npc_memory, item | + ObjectiveWatcher |
| `check_result` | dialogue | + ObjectiveWatcher |
| `npc_died` | relationship, quest | + ObjectiveWatcher |

### 10.4 페이로드 스키마

| 이벤트 | 필수 키 | 선택 키 |
|--------|---------|---------|
| `player_moved` | player_id, from_node, to_node | move_type |
| `action_completed` | player_id, action_type, node_id | result_data |
| `item_given` | player_id, recipient_npc_id, item_prototype_id | instance_id, quantity, item_tags |
| `objective_completed` | quest_id, objective_id, objective_type | trigger_action, trigger_data, turn_number |
| `objective_failed` | quest_id, objective_id, objective_type, fail_reason | trigger_data, turn_number |

### 10.5 순환 분석

**경로: ObjectiveWatcher → quest → 후속 모듈**
```
engine(OW) --objective_completed--> quest --quest_completed--> relationship, overlay, ...
```
- 위험 수준: 없음. quest_completed 구독자는 engine에 이벤트를 발행하지 않음.
- ObjectiveWatcher는 quest 이벤트를 구독하지 않음.

**경로: ObjectiveWatcher → quest → 대체 목표 → ObjectiveWatcher**
```
engine(OW) --objective_failed--> quest --대체 목표 생성--> (DB에 추가)
```
- 위험 수준: 없음. 대체 목표 생성은 DB 쓰기일 뿐 이벤트를 발행하지 않음.
- 대체 목표의 달성은 PC의 다음 액션에서 별도 체인으로 처리됨.

---

## 11. 구현 우선순위

### Phase 1: 최소 연동 (Alpha 핵심)

| 순서 | 항목 | 의존 |
|------|------|------|
| 1 | `player_moved`, `action_completed`, `item_given` 이벤트 추가 (event_types.py) | EventBus 인프라 (완료) |
| 2 | ObjectiveWatcher 기본 구조 (engine 내부) | 1 |
| 3 | reach_node 달성 판정 | 2 |
| 4 | talk_to_npc 달성 판정 (단순 접촉) | 2, dialogue 모듈 |
| 5 | deliver 달성 판정 + give 액션 | 2, item 모듈 |
| 6 | objective_completed → quest 완료 판정 | 3, 4, 5 |
| 7 | PC 알림 (시스템 메시지) | 6 |

### Phase 2: 판정·호위 연동

| 순서 | 항목 | 의존 |
|------|------|------|
| 8 | resolve_check 달성 판정 (check_result 구독) | dialogue 행동 선언 |
| 9 | 대화 중 목표 달성 → LLM 컨텍스트 반영 | 8 |
| 10 | escort 달성 판정 | companion 모듈 (C) |
| 11 | escort 실패 감지 (npc_died 구독) | 10 |
| 12 | 대체 목표 생성 + PC 선택지 | 11 |
| 13 | 의뢰주 보고 → 퀘스트 분기 (실패 보고 시드) | 12 |

### Phase 3: 확장

| 순서 | 항목 | 의존 |
|------|------|------|
| 14 | require_action 지원 (reach_node + investigate 등) | 3 |
| 15 | talk_to_npc 주제 요구 (dialogue_ended 구독) | 4 |
| 16 | deliver 누적 수량 판정 | 5 |
| 17 | use 액션 구현 | item 모듈 확장 |
| 18 | 전투 시스템 연동 (check_type: COMBAT) | Beta 전투 시스템 |

---

## 12. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-12 | 최초 작성 |
| 1.1 | 2026-02-12 | quest-system.md v1.1 반영: Objective 5종, deliver/escort 통합, 대체 목표 생성, 의뢰주 보고 필수, 전투 추상화 |
