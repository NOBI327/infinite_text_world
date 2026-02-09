# ITW 대화 시스템 설계서

**버전**: 1.0  
**작성일**: 2026-02-10  
**상태**: 확정  
**관련**: npc-system.md, relationship-system.md, quest-system.md, simulation-scope.md

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 대화 시스템을 정의한다. 대화 시스템은 PC-NPC 간 다회 턴 대화를 관리하며, 퀘스트 시드 전달, 관계 변동, 행동 판정의 허브 역할을 한다. Python이 세션 생명주기와 검증을 제어하고, LLM이 서술과 NPC 연기를 담당한다.

### 1.2 핵심 원칙

- **Python 제어, LLM 연기**: 세션 관리·검증·판정은 Python, 서술·대사·해석은 LLM
- **서술 + META 이중 구조**: 매 대화 턴마다 LLM은 narrative(플레이어용)와 meta(Python용)를 반환
- **예산제 대화**: 관계·성격에 따라 대화 턴 예산을 할당, 그라데이션으로 자연 종료 유도
- **세션 종료 시 일괄 처리**: 관계 변동·기억 저장·상태 전이는 대화 끝에 한번에 적용
- **EventBus 통신**: 모듈간 직접 호출 금지

### 1.3 모듈 위치

- **Layer**: 3 (상호작용 모듈)
- **의존성**: npc_core, relationship
- **위치**: `src/modules/dialogue/`

### 1.4 범위

| 시스템 | 담당 | 비고 |
|--------|------|------|
| **dialogue 모듈** | NPC 대화 (다회 턴, 컨텍스트 관리, META 처리) | 이 문서 |
| **narrative_service** | 환경 서술 (look/move/investigate 등, 1회성 LLM 호출) | 기존 유지 |

narrative_service는 단발 호출로 성격이 다르므로 dialogue 모듈에 통합하지 않는다. 추후 모듈화 시 별도 검토.

---

## 2. 대화 턴 구조

### 2.1 게임 턴과의 관계

```
대화 세션 전체 = 게임 1턴

PC: "talk hans"
  → 대화 세션 시작 (게임 시간 정지)
  → 대화 턴 1, 2, 3, ... (게임 턴 변동 없음)
  → 대화 세션 종료
  → 게임 턴 +1 소비
  → turn_processed 이벤트 발행
```

대화 중에는 NPC 자율행동, 시드 TTL 감소, 오버레이 변동 등 **아무것도 진행되지 않는다**. 대화는 게임 시간에서 "순간"이다.

### 2.2 대화 턴 정의

**1회 LLM 호출 = 1 대화 턴**

PC가 자유 형식으로 입력하고, LLM이 서술+대사로 응답한다. PC 입력은 짧은 문장이든 긴 서술이든 상관없고, LLM 응답도 서술+대사가 자유롭게 섞인다.

### 2.3 대화 턴 예산 (Dialogue Turn Budget)

LLM의 대화 연장 경향을 제어하기 위해 Python이 대화 턴 예산을 할당한다.

#### 예산 계산

```python
BASE_BUDGET = {
    "stranger": 3,
    "acquaintance": 4,
    "friend": 6,
    "bonded": 8,
    "rival": 4,
    "nemesis": 6,
}

def calculate_budget(
    relationship_status: str,
    npc_hexaco_x: float,
    has_quest_seed: bool,
) -> int:
    """대화 턴 예산 계산"""
    base = BASE_BUDGET.get(relationship_status, 3)

    # HEXACO X(외향성) 보정
    if npc_hexaco_x >= 0.7:
        base += 1
    elif npc_hexaco_x <= 0.3:
        base -= 1

    # 퀘스트 시드 보정
    if has_quest_seed:
        base += 2

    return max(2, base)  # 최소 2턴
```

#### 예산 위상 (Budget Phase)

예산 소비에 따라 Python이 위상을 계산하고 LLM 프롬프트에 주입한다:

```python
def get_budget_phase(remaining: int, total: int) -> str:
    ratio = remaining / total
    if ratio > 0.6:
        return "open"
    elif ratio > 0.3:
        return "winding"
    elif remaining > 0:
        return "closing"
    else:
        return "final"
```

| 위상 | 조건 | LLM 지시 | NPC 행동 예시 |
|------|------|---------|-------------|
| **open** | 잔여 > 60% | 지시 없음, 자유 대화 | 정상 대화 |
| **winding** | 잔여 30~60% | "NPC가 슬슬 다른 할 일을 의식하기 시작한다" | "아, 벌써 이렇게 됐네..." |
| **closing** | 잔여 1~29% | "NPC가 대화를 마무리하려 한다. 핵심만 전달하라." | "나도 이제 가봐야 해서..." |
| **final** | 잔여 0 | "이것이 마지막 발언이다. 인사하고 끝내라." | "그럼 다음에 또 보자고!" |

#### 퀘스트 시드 우선 전달

시드가 활성 상태인데 winding 진입 시까지 미전달이면, Python이 강제 삽입 지시:

```
budget 8턴, 시드 있음
  턴 1~4 (open): 일반 대화 중 시드 자연 전달 기대
  턴 5 (winding): seed_delivered == false
    → LLM 지시: "시간이 부족하다. 시드를 이번 턴에 반드시 전달하라."
  턴 6 (closing): PC 반응 대기
  턴 7~8: 마무리
```

### 2.4 종료 메커니즘

대화는 다음 조건 중 하나로 종료된다:

| 우선순위 | 종료 조건 | 상태 코드 |
|---------|----------|----------|
| 1 | PC가 종료 의사 표현 | `ended_by_pc` |
| 2 | LLM: `end_conversation: true` | `ended_by_npc` |
| 3 | LLM: `wants_to_continue: false` | `ended_by_npc` |
| 4 | budget 잔여 0 (하드 종료) | `ended_by_budget` |
| 5 | 시스템 오류 (LLM 실패 등) | `ended_by_system` |

PC는 예산과 무관하게 **언제든** 대화를 끝낼 수 있다. 예산은 **최대치**이지 최소치가 아니다.

`wants_to_continue: false`는 NPC 성격에 의한 조기 종료이다. 과묵한 NPC(X ≤ 0.3)가 budget 6턴 중 2턴만에 "..." 하고 끝내는 것이 자연스럽다.

하드 종료(budget 0) 시 Python이 템플릿 서술을 삽입한다: *"[NPC]가 바쁜 듯 자리를 뜬다."*

---

## 3. 대화 세션 생명주기

### 3.1 전체 흐름

```
[1] 세션 시작 (PC: "talk hans")
    │
    ├─ Python: NPC 존재 확인, Active Zone 내 확인
    ├─ Python: 대화 예산 계산 (관계 상태 + 시드 + HEXACO)
    ├─ EventBus: "dialogue_started" 발행
    │    └─ quest 모듈 구독: 퀘스트 시드 5% 판정
    │         └─ 성공 시 "quest_seed_generated" 발행 → dialogue 수신
    ├─ EventBus: "attitude_request" 발행
    │    └─ relationship 모듈: "attitude_response" 반환 (태도 태그)
    ├─ Python: LLM 컨텍스트 조립 (초기)
    │
    └─ DialogueSession 객체 생성
         │
[2] 대화 루프 (budget 소진 또는 종료까지)
    │
    ├─ PC 입력 수신
    ├─ Python: budget_phase 계산, 시드 전달 상태 확인
    ├─ Python: LLM 프롬프트 조립 (컨텍스트 + phase 지시 + 전체 대화 이력)
    ├─ LLM 호출 → narrative + meta JSON 반환
    ├─ Python: META 파싱 + 검증 (섹션 6 참조)
    │    ├─ relationship_delta 클램핑 (-5~+5)
    │    ├─ quest_seed_response 처리
    │    ├─ action_interpretation 검증 (constraints 대조)
    │    └─ memory_tags 수집
    ├─ narrative를 PC에게 출력
    ├─ 종료 판정 (섹션 2.4)
    │    ├─ 종료 조건 충족 → [3]으로
    │    └─ 계속 → 다음 대화 턴
    │
[3] 세션 종료
    │
    ├─ Python: 누적된 relationship_delta 합산 → 감쇠 곡선 적용 → DB 반영
    ├─ Python: memory_tags 일괄 저장
    ├─ Python: familiarity +1 (대화 1회 자동)
    ├─ EventBus: "dialogue_ended" 발행
    │    ├─ relationship 모듈: 감쇠 적용, 상태 전이 판정
    │    ├─ quest 모듈: 시드 수락/무시 처리
    │    └─ npc_memory 모듈: 기억 저장
    └─ 게임 턴 1턴 소비 (engine이 turn_processed 트리거)
```

### 3.2 relationship_delta 적용 시점

**세션 종료 시 일괄 적용한다.**

- 대화 중간에 affinity가 바뀌면 태도 태그가 턴마다 변해서 NPC 성격이 불안정해짐
- 일괄 적용하면 대화 중 NPC가 일관된 태도를 유지
- 대화 끝나고 "아, 이 사람 생각보다 괜찮네" 하고 바뀌는 게 자연스러움

다만, 대화 중 누적 delta를 추적하여 LLM에게 `accumulated_delta` 힌트를 줄 수 있다. 실제 수치 반영만 뒤로 미룬다.

### 3.3 time_core 연동

dialogue 모듈은 time_core를 직접 호출하지 않는다 (모듈 간 직접 호출 금지).

```
대화 세션 종료
  → dialogue: "dialogue_ended" 이벤트 발행
  → engine/ModuleManager: turn_processed 트리거
  → 각 모듈이 turn_processed 구독하여 처리
```

talk 명령은 look/move와 동일하게 1턴을 소비한다. 차이점은 내부에서 다회 LLM 호출이 일어난다는 것뿐이다.

| 대화 중 멈추는 것 |
|------------------|
| NPC 자율행동 (Phase A/B/C) |
| 시드 TTL 감소 |
| urgent 퀘스트 타이머 |
| familiarity 시간 감쇠 |
| 오버레이 severity 변동 |
| Zone 전환 |

---

## 4. META JSON 통합 형식

### 4.1 설계 원칙

- 매 대화 턴마다 LLM은 항상 동일한 최상위 구조를 반환한다
- 상황에 따라 선택적 필드가 채워지거나 null이다
- Python은 META만 파싱하면 모든 게임 로직을 처리할 수 있다
- narrative(서술)는 플레이어에게 그대로 보여주고, meta는 Python만 소비한다

### 4.2 전체 구조

```json
{
  "narrative": "한스가 걱정스러운 표정으로 망치를 내려놓았다. '요즘 걱정이 많아...'",

  "meta": {
    "dialogue_state": {
      "wants_to_continue": true,
      "end_conversation": false,
      "topic_tags": ["family", "concern"]
    },

    "relationship_delta": {
      "affinity": 2,
      "reason": "shared_worry"
    },

    "memory_tags": ["mentioned_cousin_fritz", "worried_about_family"],

    "quest_seed_response": null,

    "quest_details": null,

    "action_interpretation": null,

    "resolution_comment": null,

    "trade_request": null,

    "gift_offered": null,

    "npc_internal": {
      "emotional_state": "anxious",
      "hidden_intent": null
    }
  }
}
```

### 4.3 필드 상세

#### dialogue_state (필수, 매 턴)

| 필드 | 타입 | 설명 |
|------|------|------|
| `wants_to_continue` | bool | NPC가 대화를 이어가고 싶은지. false면 조기 종료. |
| `end_conversation` | bool | NPC가 명시적으로 대화를 끝내는지. |
| `topic_tags` | list[str] | 이번 턴의 대화 주제 태그 (로그/분석용). |

#### relationship_delta (필수, 매 턴)

| 필드 | 타입 | 범위 | 설명 |
|------|------|------|------|
| `affinity` | int | -5 ~ +5 | 이번 턴 감정 변동 제안. 변동 없으면 0. |
| `reason` | str | — | 변동 사유 태그. |

Python이 클램핑한다. 세션 종료 시 합산 후 감쇠 곡선 적용.

#### memory_tags (필수, 매 턴)

- 문자열 배열, 빈 배열 허용
- 각 태그 50자 이내
- 세션 종료 시 NPC 기억에 일괄 저장

#### quest_seed_response (선택, 시드 활성 대화에서)

| 값 | 의미 |
|----|------|
| `"accepted"` | PC가 시드에 반응, 퀘스트 활성화 |
| `"ignored"` | PC가 시드를 무시 |
| `null` | 시드 미전달 또는 시드 없음 |

#### quest_details (선택, PC가 시드 수락 시)

```json
{
  "title": "실종된 사촌",
  "description": "한스의 사촌 프리츠가 이틀 전 동쪽 산에 갔다가 돌아오지 않았다.",
  "quest_type": "investigate",
  "urgency": "urgent",
  "time_limit": 20,
  "target_hints": ["eastern_mountain", "logging_trail"],
  "tags": ["missing_person", "family", "mountain", "search"],
  "objectives_hint": [
    {"description": "동쪽 산에서 프리츠를 찾아라", "hint_type": "find_npc", "hint_target": "fritz"},
    {"description": "프리츠를 마을로 데려와라", "hint_type": "escort_to", "hint_target": "village"}
  ]
}
```

quest-system.md의 hint_type → objective_type 매핑 및 fallback 목표 생성 규칙 적용.

#### action_interpretation (선택, PC가 행동 선언 시)

```json
{
  "approach": "axiom_exploit",
  "stat": "EXEC",
  "modifiers": [
    {"source": "axiom_counter", "value": 1.1, "axiom_id": "Water_03", "reason": "Water vs Fire (same Domain amplify)"},
    {"source": "prior_investigation", "value": 1, "reason": "약점 파악 보너스 다이스"}
  ],
  "description": "PC가 화염 공리의 약점을 파악하고 물 공리로 상쇄를 시도한다"
}
```

**퀘스트 중이든 아니든** PC가 행동을 선언하면 발생한다. Constraints 검증은 섹션 5 참조.

#### resolution_comment (선택, 퀘스트 완료/실패 대화 시)

```json
{
  "npc_dialogue": "사촌을 찾아줘서 고맙네. 그런데 그 이상한 하늘나는 상자는 뭔가?",
  "method_tag": "unconventional_transport",
  "impression_tag": "grateful_but_bewildered"
}
```

quest-system.md의 NPC 한줄평 규칙 참조. NPC 기억(Tier 2) + 퀘스트 DB 이중 저장.

#### trade_request (선택, 거래 발생 시)

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | str | "buy" \| "sell" \| "negotiate" \| "confirm" \| "reject" |
| `item_instance_id` | str | 거래 대상 아이템 instance ID |
| `proposed_price` | int \| null | PC/NPC 제안가 (negotiate 시) |
| `final_price` | int \| null | 최종 합의가 (confirm 시) |

Python 검증: action이 허용 값인지, 아이템이 실제 존재하는지, 통화 잔고 충분한지 확인. 상세는 item-system.md 섹션 6 참조.

#### gift_offered (선택, 선물 제공 시)

| 필드 | 타입 | 설명 |
|------|------|------|
| `item_instance_id` | str | 선물 아이템 instance ID |
| `npc_reaction` | str | NPC 반응 태그 ("grateful", "indifferent", "offended" 등) |

Python이 item-system.md의 `calculate_gift_affinity()`로 relationship_delta를 계산하고, 세션 종료 시 일괄 적용.

#### npc_internal (선택, 매 턴)

| 필드 | 타입 | 설명 |
|------|------|------|
| `emotional_state` | str | NPC의 현재 감정 상태 (디버그/로그용) |
| `hidden_intent` | str \| null | NPC가 숨기고 있는 의도 (거짓말 등) |

디버그 및 향후 분석용. 게임 로직에는 사용하지 않는다.

---

## 5. Constraints와 수단의 자유 검증

### 5.1 원칙

"PC가 가진 것만 쓸 수 있다"는 원칙은 **퀘스트와 무관한 게임 전체의 기본 규칙**이다. 평상시 가능한 행동은 퀘스트 중에도 가능하고, 평상시 불가능한 행동은 퀘스트 중에도 불가능하다.

### 5.2 Constraints 프롬프트 주입 (1차 방어)

모든 대화 세션의 LLM 프롬프트에 PC 보유 자원을 Constraints로 주입한다:

```json
{
  "constraints": {
    "pc_axioms": ["Fire_01", "Water_03"],
    "pc_stats": {"WRITE": 3, "READ": 4, "EXEC": 2, "SUDO": 1},
    "pc_items": ["rope", "torch", "healing_herb"],
    "instruction": "PC가 보유하지 않은 공리나 아이템을 사용하는 해석을 하지 마라. 보유 목록 외의 수단을 action_interpretation에 포함시키지 마라."
  }
}
```

### 5.3 Python 사후 검증 (2차 방어)

LLM 반환의 `action_interpretation`에 대해 Python이 PC 보유 자원과 대조한다:

```python
def validate_action_interpretation(
    interpretation: dict,
    pc_axioms: list[str],
    pc_items: list[str],
    pc_stats: dict[str, int],
) -> dict:
    """LLM의 행동 해석이 PC 보유 자원 범위 내인지 검증"""

    validated_modifiers = []
    for mod in interpretation.get("modifiers", []):
        source = mod["source"]

        # 공리 참조 검증
        if source.startswith("axiom_") and mod.get("axiom_id"):
            if mod["axiom_id"] not in pc_axioms:
                continue  # PC 미보유 공리 → 제거

        # 아이템 참조 검증
        if source.startswith("item_") and mod.get("item_id"):
            if mod["item_id"] not in pc_items:
                continue  # PC 미보유 아이템 → 제거

        # modifier 값 클램핑
        mod["value"] = clamp(mod["value"], -2.0, 2.0)

        validated_modifiers.append(mod)

    interpretation["modifiers"] = validated_modifiers

    # stat 검증
    stat = interpretation.get("stat", "EXEC")
    if stat not in ("WRITE", "READ", "EXEC", "SUDO"):
        interpretation["stat"] = "EXEC"

    return interpretation
```

### 5.4 추가 LLM 호출 없음

action_interpretation은 **이미 진행되는 대화 LLM 호출의 META 안에** 선택적으로 포함된다. 정형 명령어(look/move/investigate 등)는 기존 engine.py가 직접 처리하며, action_interpretation이 불필요하다.

| 상황 | LLM 호출 | action_interpretation |
|------|---------|---------------------|
| 정형 명령어 (look/move/...) | narrative_service (기존) | 불필요 |
| NPC 대화 중 일반 발언 | 대화 LLM 호출 (이미 발생) | 불필요 |
| NPC 대화 중 행동 선언 | 대화 LLM 호출 (이미 발생) | META에 포함 |

---

## 6. Python 사후 검증 파이프라인

### 6.1 원칙

**검증 실패 시 재생성 요청하지 않고, Python이 보정한다.** 유일한 예외는 체인 완결 퀘스트에서 복선 미회수 시.

### 6.2 검증 규칙

#### 항상 검증 (매 턴)

| 필드 | 검증 규칙 | 실패 시 처리 |
|------|----------|------------|
| `relationship_delta.affinity` | -5 ≤ value ≤ +5 | 클램핑 |
| `memory_tags` | 문자열 배열, 각 태그 50자 이내 | 초과분 잘라냄 |
| `dialogue_state` | 필수 필드 존재 확인 | 기본값 (wants_to_continue: true, end_conversation: false) |

#### 조건부 검증 (해당 시)

| 필드 | 검증 규칙 | 실패 시 처리 |
|------|----------|------------|
| `quest_seed_response` | "accepted" \| "ignored" \| null | null 처리 |
| `quest_details.quest_type` | 8개 유형 중 하나 | fallback 유형 적용 |
| `quest_details.objectives_hint` | hint_type 매핑 가능 여부 | fallback 목표 생성 |
| `action_interpretation.stat` | WRITE \| READ \| EXEC \| SUDO | 기본 EXEC |
| `action_interpretation.modifiers` | PC 보유 자원에 존재 | 미보유 modifier 제거 |
| `resolution_comment.method_tag` | 허용 태그 목록 | "unconventional" 기본값 |
| `resolution_comment.impression_tag` | 허용 태그 목록 | "neutral" 기본값 |
| `trade_request.action` | "buy" \| "sell" \| "negotiate" \| "confirm" \| "reject" | null 처리 |
| `trade_request.item_instance_id` | 아이템 존재 확인 | null 처리 (거래 무효) |
| `gift_offered.item_instance_id` | 아이템 존재 + PC 소유 확인 | null 처리 (선물 무효) |

### 6.3 검증 흐름

```
LLM 반환 → JSON 파싱
  ├─ 파싱 실패 → 서술만 사용, meta 전체 기본값
  ├─ 필수 필드 누락 → 기본값 적용
  ├─ 값 범위 초과 → 클램핑
  ├─ constraints 위반 → 해당 항목 제거
  └─ 체인 완결 복선 미회수 → 재생성 (유일한 예외)
```

---

## 7. LLM 프롬프트 구조

### 7.1 프롬프트 계층

```
[System Prompt] ── 세션 내내 고정
  ├─ 역할 정의
  ├─ META JSON 스키마 정의
  ├─ 출력 형식 규칙
  └─ 일반 행동 규칙

[NPC Context] ── 세션 내내 고정
  ├─ NPC 프로필 (이름, 직업, 위치)
  ├─ HEXACO 성격 (자연어 변환)
  ├─ 태도 태그 (relationship 모듈에서 수신)
  ├─ 관계 상태, familiarity
  ├─ NPC 기억 (Tier 1 + Tier 2 관련 항목)
  ├─ 같은 노드 NPC에 대한 의견 (npc_opinions)
  └─ 현재 노드 환경 정보

[Session Context] ── 세션 내내 고정, 조건부
  ├─ constraints (항상): PC 보유 공리/스탯/아이템
  ├─ quest_seed (시드 활성 시): 유형, 컨텍스트 태그, 전달 지시
  ├─ active_quests (퀘스트 진행 시): 퀘스트 요약, 목표
  ├─ expired_seeds (만료 시드 있을 시): 만료 결과, 서술 지시
  └─ chain_context (체이닝 시): 이전 퀘스트 요약, 미해결 복선

[Turn Context] ── 매 턴 갱신
  ├─ budget_phase
  ├─ budget_remaining
  ├─ seed_delivered (시드 전달 상태)
  ├─ phase_instruction (위상별 LLM 지시)
  └─ accumulated_delta (누적 호감 변동 힌트)

[Conversation History] ── 매 턴 추가, 전체 포함
  ├─ PC: "안녕 한스, 요즘 어때?"
  ├─ NPC: "아, 자네였나. 요즘 좀..."       ← narrative만, meta 제외
  ├─ PC: "무슨 일 있어?"
  └─ NPC: "사실은..."                      ← narrative만, meta 제외

[Current Input] ── 이번 턴
  └─ PC: "내가 도와줄까?"
```

### 7.2 대화 이력 관리

- **전체 이력 항상 포함** (슬라이딩 윈도우 미적용)
- budget 최대 ~10턴이므로 컨텍스트 윈도우 압박 없음
- **이전 턴의 meta는 제외**, narrative만 포함
  - meta는 Python 소비용이므로 LLM에 다시 보여줄 필요 없음
  - 토큰 절약 + LLM이 이전 meta 패턴을 복제하는 것 방지

### 7.3 HEXACO 자연어 변환

LLM에게 숫자 대신 자연어 성격 묘사를 전달한다:

```python
HEXACO_DESCRIPTORS = {
    "H": {
        (0.0, 0.3): "이익에 민감하고 실리적이다",
        (0.3, 0.7): "보통 수준의 정직성",
        (0.7, 1.0): "정직하고 겸손하다",
    },
    "E": {
        (0.0, 0.3): "담대하고 감정에 흔들리지 않는다",
        (0.3, 0.7): "보통 수준의 감수성",
        (0.7, 1.0): "걱정이 많고 감정적이다",
    },
    "X": {
        (0.0, 0.3): "과묵하고 혼자 있는 것을 선호한다",
        (0.3, 0.7): "보통 수준의 사교성",
        (0.7, 1.0): "외향적이고 수다스럽다",
    },
    "A": {
        (0.0, 0.3): "비판적이고 대립을 피하지 않는다",
        (0.3, 0.7): "보통 수준의 관용",
        (0.7, 1.0): "관대하고 협력적이다",
    },
    "C": {
        (0.0, 0.3): "충동적이고 즉흥적이다",
        (0.3, 0.7): "보통 수준의 성실성",
        (0.7, 1.0): "체계적이고 신중하다",
    },
    "O": {
        (0.0, 0.3): "전통적이고 익숙한 것을 선호한다",
        (0.3, 0.7): "보통 수준의 개방성",
        (0.7, 1.0): "호기심이 많고 새로운 것을 좋아한다",
    },
}
```

예시 출력: *"이 NPC는 걱정이 많고 감정적이며(E), 꽤 외향적이고(X), 관대한 편이다(A)."*

---

## 8. EventBus 인터페이스

### 8.1 dialogue 모듈이 발행하는 이벤트

| 이벤트 | 데이터 | 구독 예상 |
|--------|--------|----------|
| `dialogue_started` | `{session_id, player_id, npc_id, node_id}` | quest (시드 5% 판정) |
| `dialogue_ended` | `{session_id, npc_id, accumulated_deltas, memory_tags, seed_result, dialogue_turns}` | relationship, quest, npc_memory |
| `dialogue_action_declared` | `{session_id, npc_id, action_interpretation, validated}` | engine (판정 실행) |

### 8.2 dialogue 모듈이 구독하는 이벤트

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `attitude_response` | relationship | 태도 태그 수신, NPC 컨텍스트에 반영 |
| `quest_seed_generated` | quest | 시드 정보 수신, 세션 컨텍스트에 주입 |
| `check_result` | engine | 판정 결과 수신, 다음 LLM 호출에 전달 |

### 8.3 이벤트 순서 (세션 시작 시)

```
dialogue_started 발행
  → quest 모듈: 5% 판정
    ├─ 실패 → 없음
    └─ 성공 → quest_seed_generated 발행 → dialogue 수신
  → attitude_request 발행
    → relationship: attitude_response 반환
  → 시드 + 태도 준비 완료 → 첫 LLM 호출
```

---

## 9. 데이터 모델

### 9.1 DialogueSession

```python
@dataclass
class DialogueSession:
    """대화 세션 단위"""
    session_id: str                     # UUID
    player_id: str
    npc_id: str
    node_id: str                        # 대화 발생 노드

    # 예산
    budget_total: int                   # 초기 예산
    budget_remaining: int               # 잔여 예산
    budget_phase: str                   # "open" | "winding" | "closing" | "final"

    # 상태
    status: str                         # "active" | "ended_by_pc" | "ended_by_npc"
                                        # | "ended_by_budget" | "ended_by_system"
    started_turn: int                   # 게임 턴
    dialogue_turn_count: int = 0        # 대화 턴 수

    # 시드
    quest_seed: Optional[QuestSeed] = None
    seed_delivered: bool = False
    seed_result: Optional[str] = None   # "accepted" | "ignored" | None

    # 누적 데이터 (세션 종료 시 일괄 처리)
    accumulated_affinity_delta: float = 0.0
    accumulated_memory_tags: list[str] = field(default_factory=list)

    # 대화 이력 (LLM 컨텍스트용)
    history: list[DialogueTurn] = field(default_factory=list)

    # 컨텍스트 (세션 시작 시 조립, 고정)
    npc_context: dict = field(default_factory=dict)
    session_context: dict = field(default_factory=dict)
```

### 9.2 DialogueTurn

```python
@dataclass
class DialogueTurn:
    """대화 턴 1회"""
    turn_index: int
    pc_input: str                       # PC 발언
    npc_narrative: str                  # LLM 서술 (플레이어에게 보여줌)
    meta: dict                          # LLM META 원본 (Python 소비)
    validated_meta: dict                # Python 검증 후 META
```

### 9.3 DB 테이블

| 테이블 | 주요 필드 | 용도 |
|--------|----------|------|
| `dialogue_sessions` | session_id, player_id, npc_id, node_id, started_turn, ended_turn, status, budget_total, dialogue_turn_count, seed_id, seed_result, total_affinity_delta | 세션 이력 |
| `dialogue_turns` | turn_id, session_id, turn_index, pc_input, npc_narrative, raw_meta, validated_meta | 대화 턴 이력 (디버그/분석용) |

- NPC 기억(Tier 2)의 원본 소스
- 디버그/밸런스 분석용
- 보존 정책은 추후 결정 (운영 단계)

---

## 10. 전체 흐름 예시

### 10.1 일반 대화 (시드 없음)

```
턴 42: PC가 대장장이 한스와 대화 시작 ("talk hans")
  → dialogue_started 발행
  → quest: 5% 판정 → 실패 (시드 없음)
  → relationship: attitude_response → ["friendly", "cautious_trust", "reliable_customer"]
  → budget 계산: friend(6) + X:0.6(보정 없음) = 6턴
  → DialogueSession 생성

  [대화 턴 1] budget 6/6, phase: open
    PC: "안녕 한스, 요즘 무기 주문 많아?"
    LLM → narrative: "한스가 망치를 내려놓고 웃는다. '덕분에 바쁘지.'"
          meta: {relationship_delta: {affinity: 1, reason: "friendly_greeting"},
                 memory_tags: ["asked_about_business"],
                 dialogue_state: {wants_to_continue: true, end_conversation: false}}

  [대화 턴 2] budget 5/6, phase: open
    PC: "검 하나 맞추고 싶은데"
    LLM → narrative + meta (거래 관련 대화)

  [대화 턴 3] budget 4/6, phase: winding
    LLM 지시에 "NPC가 슬슬 다른 할 일을 의식한다" 추가
    LLM → "한스가 화로를 힐끗 본다. '아, 곧 쇳물을 부어야 해서...'"

  [대화 턴 4] budget 3/6, phase: winding
    PC: "그럼 다음에 올게"
    LLM → meta: {end_conversation: true}

  → 세션 종료 (ended_by_pc)
  → 누적 delta: affinity +4 → 감쇠 적용 → 실제 반영
  → memory_tags: ["asked_about_business", "ordered_sword"] 저장
  → familiarity +1
  → dialogue_ended 발행 → 게임 턴 +1
```

### 10.2 시드 발생 + 수락

```
턴 55: PC가 한스와 대화 시작
  → quest: 5% 판정 → 성공! 시드 생성 (tier: 2, type: personal, ttl: 15)
  → quest_seed_generated 발행 → dialogue 수신
  → budget: friend(6) + 시드(+2) = 8턴

  [대화 턴 1] budget 8/8, phase: open, seed_delivered: false
    PC: "한스, 잘 지내?"
    LLM 지시: 시드 있음, 자연스럽게 전달하라
    LLM → "한스가 한숨을 쉰다. '사실 걱정이 있어... 사촌 프리츠가 이틀 전
            산에 갔는데 소식이 없어.'"
    meta: {quest_seed_response: null, memory_tags: ["worried_about_fritz"]}
    → Python: seed_delivered = true

  [대화 턴 2] budget 7/8, phase: open, seed_delivered: true
    PC: "내가 찾아볼까?"
    LLM → meta: {quest_seed_response: "accepted",
                  quest_details: {title: "실종된 사촌", quest_type: "investigate", ...}}
    → Python: seed_result = "accepted"
    → quest 모듈: 퀘스트 활성화, L4 오버레이 생성

  [대화 턴 3~4] 퀘스트 상세 대화 (위치 힌트 등)

  → 세션 종료
  → dialogue_ended 발행 (seed_result: "accepted" 포함)
```

### 10.3 시드 무시

```
턴 55: 동일하게 시드 발생

  [대화 턴 1] 한스가 사촌 걱정 언급 (seed_delivered = true)

  [대화 턴 2]
    PC: "그렇구나. 그건 그렇고 검 얘기 하려고 왔는데"
    LLM → meta: {quest_seed_response: "ignored"}
    → Python: seed_result = "ignored"

  → 세션 종료
  → 시드를 NPC 기억(Tier 2)에 저장, TTL 시작
  → 15턴 뒤 만료 시 expiry_result 기록
```

### 10.4 대화 중 행동 선언 (Constraints 검증)

```
턴 60: 퀘스트 진행 중, PC가 NPC와 대화하며 행동 선언

  PC: "화염 공리로 모닥불을 피워서 신호를 보내겠다"

  LLM → meta: {
    action_interpretation: {
      approach: "axiom_signal",
      stat: "EXEC",
      modifiers: [
        {source: "axiom_use", axiom_id: "Fire_01", value: 0.5, reason: "화염 공리 사용"}
      ],
      description: "PC가 화염 공리로 모닥불을 피워 신호를 보낸다"
    }
  }

  → Python 검증:
    Fire_01 ∈ pc_axioms? → Yes → 통과
    modifier value 0.5 ∈ [-2.0, 2.0]? → Yes → 통과
  → dialogue_action_declared 발행
  → engine: EXEC d6 Dice Pool 판정 실행
  → check_result 이벤트 → dialogue 수신
  → 다음 LLM 호출에 판정 결과 전달 → 서술 생성
```

### 10.5 NPC 성격에 의한 조기 종료

```
턴 70: PC가 과묵한 경비병(X: 0.2)에게 말을 건다
  → relationship: stranger
  → budget: stranger(3) + X:0.2(-1) = 2턴 (최소)

  [대화 턴 1] budget 2/2, phase: closing
    PC: "이 근처에 뭔 일 있었어?"
    LLM → "경비병이 짧게 대답한다. '없었다.'"
    meta: {wants_to_continue: false}

  → 세션 종료 (ended_by_npc, 1턴 만에)
```

---

## 11. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-10 | 최초 작성 |
| 1.1 | 2026-02-10 | trade_request, gift_offered META 필드 추가 (item-system.md 연동) |
