# ITW 동행 시스템 설계서

**버전**: 1.1
**작성일**: 2026-02-12  
**상태**: 확정  
**관련**: quest-system.md (v1.1), quest-action-integration.md, dialogue-system.md, relationship-system.md, event-bus.md

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 동행(Companion) 시스템을 정의한다. PC가 NPC를 파티에 합류시켜 함께 이동·대화·행동하는 메커니즘을 다룬다. escort/rescue 퀘스트의 기반이자, 독립적인 탐험 동반 기능이다.

### 1.2 핵심 원칙

- **Python 제어, LLM 연기**: 동행 수락/거절 판정은 Python, NPC의 반응과 코멘트는 LLM
- **퀘스트 동행과 자발적 동행의 구분**: 발생 경로가 다르지만, 동행 중 행동은 동일한 시스템
- **1인 동행 제한 (Alpha)**: Alpha에서는 동시 동행 NPC 1명. Beta에서 확장 검토
- **기존 시스템 최소 침습**: 이동·대화·턴 처리에 훅을 걸되, 기존 흐름은 변경하지 않음
- **EventBus 통신**: 모듈간 직접 호출 금지

### 1.3 모듈 위치

- **Layer**: 3 (상호작용 모듈)
- **의존성**: npc_core, relationship, dialogue
- **위치**: `src/modules/companion/`

### 1.4 Alpha / Beta 범위

| 구분 | 기능 | 범위 |
|------|------|------|
| **Alpha 코어** | 동행 요청/수락/해산 라이프사이클 | Alpha |
| **Alpha 코어** | 동행 NPC 이동 동기화 | Alpha |
| **Alpha 코어** | 동행 중 대화 (talk → 턴 소비 정책) | Alpha |
| **Alpha 코어** | escort/rescue 퀘스트 연동 | Alpha |
| **Beta 확장** | 물자 공유 (파티 인벤토리 접근) | Beta |
| **Beta 확장** | 전투/판정 보조 (Dice Pool 보너스) | Beta |
| **Beta 확장** | 제3자 대화 끼어들기 | Beta |
| **Beta 확장** | 바이옴 진입 코멘트 | Beta |
| **Beta 확장** | NPC 자발적 이탈 조건 | Beta |
| **Beta 확장** | 복수 동행 (파티 2~3명) | Beta |

---

## 2. 동행 유형

### 2.1 두 가지 경로

| 유형 | 트리거 | 해산 조건 | 거절 난이도 |
|------|--------|----------|-----------|
| **퀘스트 동행** | escort 목표 활성화 시 자동 요청 | 퀘스트 완료/실패/포기 시 자동 해산 | 낮음 (퀘스트 상황이 강제력) |
| **자발적 동행** | PC가 `recruit <npc>` 또는 대화 중 제안 | PC가 `dismiss` 또는 NPC가 이탈 요청 | 관계·성격에 의존 |

### 2.2 퀘스트 동행

escort 목표가 활성화되면, 대상 NPC에게 동행 요청이 자동 발생한다.

```
escort 목표 활성화 (quest_activated 이벤트)
  → companion 모듈: 대상 NPC에게 동행 요청 판정
    ├─ 대상이 PC와 같은 노드 (호위) → 즉시 요청
    └─ 대상이 다른 위치 (구출) → PC가 대상을 발견한 시점에 요청
```

퀘스트 동행의 수락 확률은 **높게 설정**한다. 위험 지역에서 고립된 NPC가 구조자의 동행을 거부하기 어렵고, 호위를 의뢰한 NPC가 동행을 거부하는 것은 모순이다.

```python
QUEST_COMPANION_ACCEPT_BASE = 0.90  # 기본 90% 수락

def quest_companion_accept_chance(npc: NPC, quest: Quest) -> float:
    """퀘스트 동행 수락 확률"""
    base = QUEST_COMPANION_ACCEPT_BASE
    
    # 구출 상황: 위험 지역에 고립 → 거의 확정
    if quest.quest_type == "escort" and "rescue" in quest.tags:
        base = 0.98
    
    # NPC 성격 보정 (A: 원만성이 낮으면 약간 저항)
    if npc.hexaco_a <= 0.2:
        base -= 0.10
    
    return min(base, 0.99)
```

### 2.3 자발적 동행

PC가 NPC에게 직접 동행을 요청한다. 관계와 성격이 수락 여부를 결정한다.

#### 요청 방법

```
방법 1: 정형 명령어
  PC: "recruit hans"
  → companion 모듈: 동행 요청 판정 → 결과에 따라 간단 서술

방법 2: 대화 중 제안
  PC: (대화 중) "같이 동쪽 산에 가지 않을래?"
  → LLM: META에 companion_request 반환
  → Python: 수락 판정 → 결과를 다음 LLM 호출에 전달
  → NPC 반응 서술
```

#### 수락 판정

```python
def voluntary_companion_accept(
    relationship_status: str,
    trust: int,
    npc_hexaco: dict,
    pc_destination_danger: float,  # 목적지 위험도 0.0~1.0
) -> tuple[bool, str | None]:
    """자발적 동행 수락 판정. 반환: (수락 여부, 거절 시 조건 태그)"""
    
    # 관계 기반 기본 수락률
    ACCEPT_BY_STATUS = {
        "stranger": 0.0,      # 낯선 사람과 동행 불가
        "acquaintance": 0.10,  # 거의 안 함
        "friend": 0.50,        # 반반
        "bonded": 0.85,        # 높음
        "rival": 0.0,          # 적과 동행 불가
        "nemesis": 0.0,        # 불가
    }
    
    base = ACCEPT_BY_STATUS.get(relationship_status, 0.0)
    if base == 0.0:
        return False, "insufficient_relationship"
    
    # trust 보정
    if trust >= 50:
        base += 0.15
    elif trust <= 20:
        base -= 0.15
    
    # 성격 보정
    # X(외향성) 높으면 동행 선호
    if npc_hexaco.get("X", 0.5) >= 0.7:
        base += 0.10
    # E(정서성) 높으면 위험 회피
    if npc_hexaco.get("E", 0.5) >= 0.7:
        base -= pc_destination_danger * 0.20
    # C(성실성) 높으면 자기 할 일 우선
    if npc_hexaco.get("C", 0.5) >= 0.7:
        base -= 0.10
    
    base = max(0.0, min(base, 0.95))
    
    if random.random() < base:
        return True, None
    else:
        return False, "personality_reluctance"
```

#### 조건 제시

수락하되 조건을 붙이는 경우가 있다. Python이 조건 발생 여부를 판정하고, LLM이 조건 내용을 서술한다.

```python
CONDITION_CHANCE = 0.40  # 수락 시 40% 확률로 조건 제시

CONDITION_TYPES = [
    "payment",          # 보수 요구
    "time_limit",       # 기한 제한 ("3일만 같이 간다")
    "destination_only", # 특정 목적지까지만
    "safety_guarantee", # 위험하면 빠진다
    "item_request",     # 특정 아이템 요구
]
```

```
PC: "recruit hans"
  → 수락 판정: True
  → 조건 판정: 40% → 성공
  → 조건 유형: "time_limit"
  → LLM에 전달: "NPC가 동행을 수락하되, 기한 조건을 제시한다."
  → 한스: "좋아, 같이 가지. 다만 3일 안에는 돌아와야 해. 대장간을 비울 수 없으니까."
  → PC: 수락 → 동행 시작 (조건 기록)
  → PC: 거절 → 동행 불성립
```

---

## 3. 동행 라이프사이클

### 3.1 상태 모델

```
[없음]
  │
  ├─ recruit / 퀘스트 자동 요청
  ↓
[요청 중] ── 거절 → [없음]
  │
  ├─ 수락 (무조건 / 조건부)
  ↓
[동행 중]
  │
  ├─ PC: dismiss → [해산]
  ├─ NPC: 이탈 요청 → [해산 협의] (Beta)
  ├─ 퀘스트 완료/실패 (퀘스트 동행) → [해산]
  ├─ NPC 사망 → [강제 해산]
  ├─ 조건 만료 (time_limit 등) → [해산]
  ↓
[해산]
  → NPC 원래 위치로 복귀 (또는 현재 위치에 잔류)
  → companion_disbanded 이벤트 발행
```

### 3.2 CompanionState 데이터 모델

```python
@dataclass
class CompanionState:
    """동행 상태 관리"""
    companion_id: str               # UUID
    player_id: str
    npc_id: str
    
    # 유형
    companion_type: str             # "quest" | "voluntary"
    quest_id: Optional[str] = None  # 퀘스트 동행 시
    
    # 상태
    status: str = "active"          # "active" | "disbanded"
    started_turn: int = 0
    ended_turn: Optional[int] = None
    disband_reason: Optional[str] = None  # "pc_dismiss" | "quest_complete" | "quest_failed"
                                          # | "npc_dead" | "condition_expired" | "npc_request"
    
    # 조건 (자발적 동행, 조건부 수락 시)
    condition_type: Optional[str] = None      # "payment" | "time_limit" | "destination_only" | ...
    condition_data: Optional[dict] = None     # {"turn_limit": 30} | {"destination": "5_3"} | ...
    condition_met: bool = False               # 조건 충족 여부
    
    # 원래 위치 (해산 시 복귀용)
    origin_node_id: str = ""
    
    # 메타
    created_at: str = ""
```

### 3.3 DB 테이블

| 테이블 | 주요 필드 |
|--------|----------|
| `companions` | companion_id, player_id, npc_id, companion_type, quest_id, status, started_turn, ended_turn, disband_reason, condition_type, condition_data, condition_met, origin_node_id |

---

## 4. 동행 중 행동: 이동 동기화

### 4.1 원칙

동행 NPC는 PC의 이동에 **자동으로 따라온다**. 별도 명령 불필요.

### 4.2 이동 흐름

```
PC: "move e"
  → engine: PC 이동 처리 → player_moved 발행
  → companion 모듈: player_moved 구독
    → 활성 동행 NPC 조회
    → NPC 좌표를 PC 좌표로 갱신 (DB 업데이트)
    → companion_moved 발행 (서술용)
```

### 4.3 서브그리드 동행

동행 NPC는 PC의 서브그리드 진입·이동에도 **함께 이동**한다.

| PC 액션 | 동행 NPC 처리 |
|---------|-------------|
| `enter` (서브그리드 진입) | NPC도 함께 진입 |
| `exit` (서브그리드 탈출) | NPC도 함께 탈출 |
| `up` / `down` (수직 이동) | 해당 노드가 수직 이동 가능한 경우 NPC도 함께 이동 |

수직 이동 가능 여부는 서브그리드 노드의 `vertical_access` 속성(계단, 사다리, 절벽 등)에 의해 결정된다. PC가 이동 가능한 노드라면 동행 NPC도 동일하게 이동 가능.

※ 부상 NPC의 이동 페널티(이동 속도 저하 등)는 Beta 확장에서 검토.

### 4.4 이동 서술

동행 NPC의 이동은 PC 이동 서술에 **한 줄 추가**로 표현한다. 별도 LLM 호출 불필요.

```python
COMPANION_MOVE_TEMPLATE = "{npc_name}이(가) 뒤따라온다."

# 바이옴 변경 시 (Beta 확장)
COMPANION_BIOME_COMMENT_INSTRUCTION = (
    "동행 NPC가 새로운 바이옴에 대해 짧게 코멘트한다. "
    "성격과 경험에 맞는 반응을 1문장으로 표현하라."
)
```

Alpha에서는 템플릿 서술. Beta에서 바이옴 변경 시 LLM 코멘트 추가.

---

## 5. 동행 중 행동: 대화

### 5.1 동행 NPC와의 대화

#### 턴 소비 정책

동행 NPC와의 대화는 **통상 대화와 동일하게 1턴 소비**한다. 동행이라고 턴 무료로 하면 남용 가능성이 있고, 게임 시간이 흘러야 세계가 돌아간다.

```
PC: "talk hans" (동행 중인 한스)
  → dialogue 세션 시작 (통상과 동일)
  → 게임 1턴 소비
```

#### 예산 보정

동행 NPC와는 이미 친밀하므로, 대화 예산에 **동행 보정 +2**를 추가한다.

```python
def calculate_budget(
    relationship_status: str,
    npc_hexaco_x: float,
    has_quest_seed: bool,
    is_companion: bool,       # 추가
) -> int:
    base = BASE_BUDGET.get(relationship_status, 3)
    
    if npc_hexaco_x >= 0.7:
        base += 1
    elif npc_hexaco_x <= 0.3:
        base -= 1
    
    if has_quest_seed:
        base += 2
    
    if is_companion:           # 추가
        base += 2
    
    return max(2, base)
```

#### LLM 컨텍스트 차이

동행 NPC와의 대화 시, LLM 프롬프트에 동행 상태 정보를 추가한다:

```json
{
  "companion_context": {
    "is_companion": true,
    "companion_type": "voluntary",
    "turns_together": 12,
    "shared_experiences": ["crossed_mountain_pass", "survived_storm"],
    "condition": {"type": "time_limit", "remaining_turns": 18},
    "instruction": "이 NPC는 PC와 동행 중이다. 여행 동반자로서의 친밀감이 대화에 반영되어야 한다."
  }
}
```

### 5.2 제3자 NPC 대화 시 동행 NPC 반응 (Beta)

PC가 다른 NPC와 대화할 때, 동행 NPC가 끼어드는 기능. Beta에서 구현.

#### 설계 방향

```
PC: "talk merchant" (동행 한스와 함께)
  → dialogue 세션 시작 (대상: merchant)
  → LLM 컨텍스트에 동행 NPC 정보 추가:
    "companion_present": {
      "npc_id": "npc_hans_042",
      "name": "한스",
      "personality_summary": "걱정이 많고 정직한 대장장이",
      "relationship_with_merchant": "acquaintance",
      "instruction": "동행 NPC가 대화에 가끔 끼어들 수 있다. 매 턴이 아니라, 자연스러운 시점(자기 전문 분야, 감정적 반응)에서만. META의 companion_interjection에 기록하라."
    }

LLM 반환:
  narrative: "상인이 가격을 부르자, 한스가 옆에서 중얼거린다. '그건 좀 비싸지 않나...'"
  meta: {
    companion_interjection: {
      npc_id: "npc_hans_042",
      content: "가격에 대한 불만",
      topic_tag: "price_negotiation"
    }
  }
```

- 끼어들기는 LLM 재량으로 매 턴이 아닌 자연스러운 시점에만
- 끼어들기가 거래/관계에 영향을 줄 수 있음 (상인이 기분 나빠서 가격 올림 등)
- Alpha에서는 미구현, LLM 컨텍스트에 동행 NPC 존재만 알림

---

## 6. 동행 해산

### 6.1 해산 트리거

| 트리거 | 해산 유형 | 처리 |
|--------|----------|------|
| PC: `dismiss <npc>` | PC 요청 | 확인 서술 후 해산 |
| 퀘스트 완료 (escort) | 퀘스트 완료 | 자동 해산, NPC 목표지 잔류 |
| 퀘스트 실패/포기 | 퀘스트 종료 | 자동 해산, NPC 현재 위치 잔류 |
| 조건 만료 (time_limit 등) | 조건 충족 | NPC가 이탈 선언 |
| NPC 사망 | 강제 | 즉시 해산 |
| NPC 이탈 요청 (Beta) | NPC 자발 | 대화 통해 협의 |

### 6.2 해산 흐름

```
해산 트리거 발생
  → companion 모듈: CompanionState.status = "disbanded"
  → ended_turn, disband_reason 기록
  → companion_disbanded 이벤트 발행
  → NPC 귀환 행동 결정 (6.2.1)
  → 해산 서술 생성
```

#### 6.2.1 해산 후 NPC 귀환 행동

해산 후 NPC는 자신의 유형과 상황에 따라 **목적지를 향해 이동을 시작**한다. 이동은 simulation-scope.md의 Background Task로 처리되며, PC가 없어도 NPC가 세계 내에서 이동하는 기존 설계와 일치한다.

##### NPC 유형별 귀환 목적지

| NPC 유형 | 귀환 목적지 | 예시 |
|----------|-----------|------|
| **정주형** (직업·거주지 보유) | `origin_node_id` (원래 거주/근무 노드) | 한스 → 대장간 |
| **구출 대상** | 의뢰인 위치 또는 안전 지역 | 프리츠 → 한스가 있는 마을 |
| **방랑형** (고정 거주지 없음) | 현재 위치 잔류 | 떠돌이 상인 → 해산 지점에 남음 |

##### 귀환 목적지 결정

```python
def determine_return_destination(
    npc: NPC,
    companion: CompanionState,
    disband_reason: str,
    quest: Quest | None,
) -> str | None:
    """해산 후 NPC의 귀환 목적지 결정. None이면 현재 위치 잔류."""

    # 퀘스트 완료 (escort) → 목표지에 잔류 (이미 도착했으므로)
    if disband_reason == "quest_complete" and quest and quest.quest_type == "escort":
        return None  # 현재 위치(목표지) 잔류

    # 구출 대상 → 의뢰인 위치로 이동
    if disband_reason in ("quest_complete", "quest_failed") and quest:
        client_npc_id = quest.origin_npc_id
        if client_npc_id:
            client_node = get_npc_node(client_npc_id)
            return client_node  # 의뢰인이 있는 장소로

    # 정주형 → 원래 위치로 복귀
    if npc.home_node_id:
        return npc.home_node_id

    # 방랑형 → 잔류
    return None
```

##### 귀환 이동 처리

```python
def schedule_return_travel(npc_id: str, destination_node_id: str) -> None:
    """Background Task로 NPC 귀환 이동 예약"""
    # simulation-scope.md의 NPC 자율 이동과 동일한 메커니즘
    # 매 턴 turn_processed에서 1노드씩 이동
    create_background_task(
        task_type="npc_return_travel",
        npc_id=npc_id,
        destination=destination_node_id,
        speed=1,  # 턴당 1노드
    )
```

NPC가 귀환 중에도 PC가 해당 NPC를 만나면 통상 대화 가능. 귀환 이동은 PC 상호작용과 독립적으로 진행된다.

##### 해산 사유별 귀환 정리

| 해산 사유 | NPC 처리 |
|----------|---------|
| PC dismiss (우호적) | 유형별 귀환 목적지로 이동 시작 |
| PC dismiss (위험 지역) | 유형별 귀환 목적지로 이동 시작 + NPC 귀환 중 위험 노출 (Beta 확장) |
| 퀘스트 완료 (escort) | 목표지에 잔류 (새 위치 확정) |
| 퀘스트 완료 (기타) | 유형별 귀환 목적지로 이동 시작 |
| 퀘스트 실패/포기 | 구출 대상: 의뢰인 위치로 / 기타: 유형별 귀환 |
| 조건 만료 | 유형별 귀환 목적지로 이동 시작 |
| NPC 사망 | 처리 없음 |

### 6.3 해산 서술

```python
DISBAND_TEMPLATES = {
    "pc_dismiss": "{npc_name}에게 작별을 고한다.",
    "quest_complete": "{npc_name}이(가) 감사를 표하며 자리를 잡는다.",
    "quest_failed": "{npc_name}이(가) 침울한 표정으로 돌아선다.",
    "condition_expired": "{npc_name}: '약속한 기한이 됐어. 나는 여기서 돌아가야 해.'",
    "npc_dead": "",  # 별도 사망 서술이 처리
}
```

Alpha에서는 템플릿 서술. Beta에서 LLM 해산 대화 세션(짧은 특수 세션) 추가 검토.

### 6.4 해산 후 관계 영향

| 해산 사유 | affinity | trust | 비고 |
|----------|----------|-------|------|
| PC dismiss (우호적) | 0 | 0 | 변동 없음 |
| PC dismiss (위험 지역에서) | -5 | -10 | NPC 입장에서 버림 |
| 퀘스트 완료 (success) | +10 | +15 | quest 보상에 추가 |
| 퀘스트 완료 (partial) | +3 | +5 | |
| 퀘스트 실패 | 0 | -5 | |
| 조건 만료 | 0 | 0 | 약속 이행 |
| NPC 사망 | — | — | 관계 소멸 |

위험 지역 판단은 현재 노드의 위험도(overlay severity, 적대 NPC 존재 등)를 참조한다.

---

## 7. escort/rescue 퀘스트 연동

### 7.1 escort 퀘스트 → 동행 자동 연결

```
quest_activated 이벤트 (quest_type: escort)
  → companion 모듈 구독
  → escort 대상 NPC의 initial_status 확인
    ├─ "present" → 즉시 동행 요청 (퀘스트 동행)
    └─ "missing" / "unknown" → 대기 (PC가 대상 발견 시 동행 요청)
```

### 7.2 구출 → 동행 흐름

```
PC가 구출 대상 위치 도착 → 대상 생존 확인
  → companion 모듈: 퀘스트 동행 요청
    → 수락 확률: 98% (구출 상황)
    → 수락 → CompanionState 생성 (companion_type: "quest", quest_id: ...)
    → companion_joined 발행
  → 이후 PC 이동 시 자동 동기화
  → 목표지 도착 → escort 목표 달성 → 퀘스트 완료 → 자동 해산
```

### 7.3 동행 상태와 escort 달성 판정

quest-action-integration.md의 ObjectiveWatcher가 escort 달성을 판정할 때, companion 모듈의 DB를 참조한다:

```python
def _is_companion(self, player_id: str, npc_id: str) -> bool:
    """해당 NPC가 현재 PC의 동행 상태인지 확인"""
    companion = self.companion_db.get_active_companion(player_id)
    return companion is not None and companion.npc_id == npc_id
```

### 7.4 구출 대상 사망 시

```
PC가 대상 위치 도착 → 대상 사망 확인
  → npc_died 이벤트
  → ObjectiveWatcher: escort 목표 실패 (target_dead)
  → quest 모듈: 대체 목표 생성 (quest-action-integration.md 섹션 5)
  → 동행은 시작되지 않음 (사망 NPC는 동행 불가)
```

---

## 8. 조건부 동행 처리

### 8.1 조건 유형별 처리

| 조건 유형 | condition_data | 만료 판정 | 만료 시 |
|----------|---------------|----------|--------|
| `payment` | `{amount: 50}` | PC가 금액 지불 여부 | 미지불 시 NPC 불만 → 동행 유지 but trust 감소 |
| `time_limit` | `{turn_limit: 30}` | 동행 시작 이후 경과 턴 | NPC가 이탈 선언 |
| `destination_only` | `{destination: "5_3"}` | 해당 노드 도착 시 | NPC가 이탈 선언 |
| `safety_guarantee` | `{danger_threshold: 0.7}` | 노드 위험도 초과 시 | NPC가 이탈 경고 → 1턴 유예 → 이탈 |
| `item_request` | `{item_id: "warm_cloak"}` | PC가 아이템 제공 여부 | 미제공 시 동행 거부 (사전 조건) |

### 8.2 조건 만료 판정 시점

`turn_processed` 이벤트를 구독하여 매 턴 조건을 체크한다:

```python
def _handle_turn_processed(self, event: GameEvent) -> None:
    """매 턴 동행 조건 체크"""
    active = self.companion_db.get_active_companion(event.data["player_id"])
    if not active or not active.condition_type:
        return
    
    if active.condition_type == "time_limit":
        elapsed = event.data["turn_number"] - active.started_turn
        if elapsed >= active.condition_data["turn_limit"]:
            self._trigger_disband(active, reason="condition_expired")
    
    elif active.condition_type == "destination_only":
        pc_node = self._get_pc_node(event.data["player_id"])
        if pc_node == active.condition_data["destination"]:
            self._trigger_disband(active, reason="condition_expired")
    
    elif active.condition_type == "safety_guarantee":
        node_danger = self._get_node_danger(self._get_pc_node(event.data["player_id"]))
        if node_danger >= active.condition_data["danger_threshold"]:
            # 1턴 경고 → 다음 턴에도 위험하면 이탈
            if active.condition_data.get("warned"):
                self._trigger_disband(active, reason="condition_expired")
            else:
                active.condition_data["warned"] = True
                # NPC 경고 서술 삽입
```

---

## 9. NPC 자발적 이탈 (Beta)

### 9.1 이탈 조건

Beta에서 동행 NPC가 스스로 이탈을 요청하는 조건:

| 조건 | 판정 기준 |
|------|----------|
| 원래 거주지에서 너무 멀어짐 | 거리 > NPC 성격(O: 개방성) 기반 임계값 |
| 동행 기간 과다 | 경과 턴 > NPC 성격(C: 성실성) 기반 임계값 |
| 관계 악화 | 동행 중 affinity 누적 감소가 임계값 초과 |
| 목표 달성 | 퀘스트 동행의 목표지 도착 (퀘스트 완료와 동시) |
| NPC의 개인 사정 | NPC 기억의 이벤트 트리거 (가족 위급 등) — 추후 확장 |

### 9.2 이탈 요청 흐름 (Beta)

```
turn_processed → companion 모듈: 이탈 조건 체크
  → 조건 충족 → NPC 이탈 의사 플래그 설정
  → 다음 대화 시 (PC가 동행 NPC와 talk)
    → LLM 컨텍스트에 이탈 의사 주입
    → NPC: "나 이제 돌아가야 할 것 같아..."
    → PC 반응:
      ├─ 수락 → 해산
      ├─ 설득 → WRITE 판정 → 성공 시 이탈 연기 (N턴)
      └─ 무시 → NPC가 다음 턴에 자동 이탈
```

---

## 10. 데이터 모델 요약

### 10.1 DB 테이블

| 테이블 | 주요 필드 |
|--------|----------|
| `companions` | companion_id, player_id, npc_id, companion_type, quest_id, status, started_turn, ended_turn, disband_reason, condition_type, condition_data, condition_met, origin_node_id |
| `companion_log` | log_id, companion_id, turn_number, event_type, data | 동행 이력 (디버그/분석) |

### 10.2 companion_log 이벤트 유형

| event_type | 기록 내용 |
|-----------|----------|
| `joined` | 동행 시작 |
| `moved` | 이동 동기화 |
| `talked` | 동행 NPC와 대화 |
| `condition_warned` | 조건 만료 경고 |
| `disbanded` | 해산 |

---

## 11. EventBus 인터페이스

### 11.1 companion 모듈이 발행하는 이벤트

| 이벤트 | 페이로드 | 구독자 |
|--------|----------|--------|
| `companion_joined` | `{companion_id, player_id, npc_id, companion_type, quest_id}` | dialogue, quest, npc_memory |
| `companion_moved` | `{companion_id, npc_id, from_node, to_node}` | narrative (서술 추가) |
| `companion_disbanded` | `{companion_id, npc_id, disband_reason, quest_id}` | quest, relationship, npc_memory |

### 11.2 companion 모듈이 구독하는 이벤트

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `player_moved` | engine | 동행 NPC 이동 동기화 |
| `quest_activated` | quest | escort 퀘스트 → 동행 자동 요청 판정 |
| `quest_completed` | quest | 퀘스트 동행 자동 해산 |
| `quest_failed` | quest | 퀘스트 동행 자동 해산 |
| `quest_abandoned` | quest | 퀘스트 동행 자동 해산 |
| `npc_died` | npc_core | 동행 NPC 사망 → 강제 해산 |
| `turn_processed` | engine | 조건 만료 체크, 이탈 조건 체크 (Beta) |

### 11.3 기존 이벤트 영향

| 기존 이벤트 | 변경 | 내용 |
|-----------|------|------|
| `dialogue_started` | 페이로드 확장 | `companion_npc_id` 선택 키 추가 (동행 NPC 존재 시) |
| `dialogue_ended` | 페이로드 확장 | `companion_interjection_count` 선택 키 추가 (Beta) |

### 11.4 순환 분석

**경로: companion → quest → companion**
```
quest_activated → companion(동행 요청) → companion_joined → quest(구독)
```
- 위험 수준: 낮음. quest는 `companion_joined`를 수신하여 escort 연결 정보만 기록하고 새 이벤트를 발행하지 않음.

**경로: companion → npc_core**
```
companion_moved → (npc_core는 비구독)
```
- 위험 수준: 없음. companion이 NPC 좌표를 직접 DB 갱신하므로 npc_core 이벤트 불필요.

---

## 12. 전체 흐름 예시

### 12.1 자발적 동행 (Alpha)

```
턴 40: PC와 한스의 관계: Friend, trust: 45

PC: "recruit hans"
  → companion: 수락 판정
    base: 0.50 (friend) + 0.15 (trust 45) + 0.10 (X: 0.7) = 0.75
    → 75% 판정 → 성공
  → 조건 판정: 40% → 성공, 유형: "time_limit"
  → LLM 서술: "한스가 잠시 생각하더니 고개를 끄덕인다. '좋아, 같이 가지. 다만 30턴 안에는 돌아와야 해.'"
  → PC 수락
  → CompanionState 생성 (voluntary, condition: time_limit 30턴)
  → companion_joined 발행

턴 41: PC: "move e"
  → player_moved → companion: 한스 좌표 동기화
  → 서술: "동쪽으로 이동한다. 한스가 뒤따라온다."

턴 45: PC: "talk hans"
  → dialogue 세션 시작 (통상 + 동행 보정 +2)
  → LLM 컨텍스트에 companion_context 주입
  → 대화 진행 → 1턴 소비

턴 68: 조건 만료 (30턴 경과)
  → turn_processed → companion: time_limit 체크 → 만료
  → 서술: "한스: '약속한 기한이 됐어. 나는 여기서 돌아가야 해.'"
  → 자동 해산 → companion_disbanded 발행
  → 한스: 현재 위치에서 원래 위치로 복귀 시작 (Background Task)
```

### 12.2 구출 퀘스트 → 퀘스트 동행 (Alpha)

```
턴 50: 구출 퀘스트 활성화
  escort {target: fritz, destination: "2_2", initial_status: "unknown", hint: "5_8"}
  → companion: initial_status "unknown" → 대기 (발견 시 동행 요청)

턴 55: PC가 5_8 도착 → 프리츠 생존 확인
  → companion: 퀘스트 동행 요청 (98% 수락)
  → 프리츠: "도와주러 온 거야? 고마워, 같이 가자!"
  → CompanionState 생성 (quest, quest_id: "quest_fritz_001")
  → companion_joined 발행

턴 56~60: 이동 → 프리츠 자동 동행

턴 60: 노드 2_2 도착
  → player_moved → ObjectiveWatcher: escort 체크
    → PC 위치 == 2_2 && fritz 동행 중 → objective_completed
  → quest: quest_completed (success)
  → companion: quest_completed 구독 → 자동 해산
  → 서술: "프리츠가 안도의 한숨을 내쉬며 주위를 둘러본다."
  → 프리츠: 2_2에 잔류 (새 위치)
```

### 12.3 구출 실패 → 대체 목표 (Alpha)

```
턴 55: PC가 5_8 도착 → 프리츠 사망 확인
  → npc_died → companion: 동행 시작되지 않음 (사망 NPC)
  → ObjectiveWatcher: escort 실패 (target_dead)
  → quest: 대체 목표 생성

  [시스템] 프리츠가 사망한 것을 확인했다.
    1. 유품을 수습하여 한스에게 가져간다
    2. 한스에게 돌아가서 보고한다
    3. 사인을 조사한다

  → PC 선택: "2. 한스에게 보고"
  → talk_to_npc(hans) 대체 목표 활성화
  → (동행은 발생하지 않음 — 실패 경로)
```

---

## 13. 구현 우선순위

### Phase 1: Alpha 코어

| 순서 | 항목 | 의존 |
|------|------|------|
| 1 | CompanionState 데이터 모델 + DB 테이블 | DB 인프라 |
| 2 | companion 모듈 기본 구조 (GameModule) | ModuleManager |
| 3 | 퀘스트 동행: quest_activated 구독 → 자동 요청 → 수락 판정 | quest 모듈 |
| 4 | 이동 동기화: player_moved 구독 → NPC 좌표 갱신 | 3 |
| 5 | escort 달성 연동: ObjectiveWatcher._is_companion() | 4, quest-action-integration |
| 6 | 해산: quest_completed/failed 구독 → 자동 해산 | 3 |
| 7 | 자발적 동행: recruit 명령 → 수락 판정 → 조건 제시 | 2 |
| 8 | 조건 만료: turn_processed 구독 → 조건 체크 | 7 |
| 9 | dismiss 명령 → 해산 | 2 |
| 10 | 동행 NPC 대화: talk → 예산 보정 + companion_context | dialogue 모듈 |

### Phase 2: Beta 확장

| 순서 | 항목 | 의존 |
|------|------|------|
| 11 | 바이옴 진입 코멘트 (LLM 1문장) | 4 |
| 12 | 제3자 대화 끼어들기 (companion_interjection) | dialogue 모듈 |
| 13 | 물자 공유 (파티 인벤토리 접근) | item 모듈 |
| 14 | 전투/판정 보조 (Dice Pool 보너스) | 전투 시스템 |
| 15 | NPC 자발적 이탈 조건 + 설득 판정 | 관계 시스템 |
| 16 | 복수 동행 (파티 2~3명) | 1~10 전체 |

---

## 14. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-12 | 최초 작성 |
| 1.1 | 2026-02-12 | 섹션 4.3 "이동 제한" → "서브그리드 동행"으로 수정, 섹션 6.2 해산 후 NPC 귀환 행동 구체화 |
