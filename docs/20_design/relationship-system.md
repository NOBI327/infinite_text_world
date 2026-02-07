# ITW 관계 시스템 설계서

**버전**: 1.0  
**작성일**: 2025-02-08  
**상태**: 확정

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 관계 시스템을 정의한다. PC-NPC 간, NPC-NPC 간 관계를 3축 수치로 추적하고, Python이 HEXACO 성격과 조합하여 LLM에 전달할 태도 태그를 생성한다.

### 1.2 핵심 원칙

- **단방향 수치 + Python 태그 생성**: DB에는 PC→NPC 수치만 저장, NPC→PC 태도는 Python이 HEXACO + 수치 + 기억으로 계산
- **LLM 최소화**: 계산 가능한 것은 Python, LLM은 서술/대화 생성만
- **EventBus 통신**: 모듈간 직접 호출 금지, 모든 데이터 공유는 EventBus 경유
- **대화 종료 시 판정**: 상태 전이는 대화가 끝날 때 일괄 계산

### 1.3 모듈 위치

- **Layer**: 3 (상호작용 모듈)
- **의존성**: npc_core
- **위치**: `src/modules/relationship/`

---

## 2. 관계 축 구조

### 2.1 3축 정의

| 축 | 범위 | 의미 | 변동 특성 |
|----|------|------|-----------|
| **affinity** | -100 ~ +100 | 감정적 호불호 | 대화/행동으로 양방향 변동. 감쇠 곡선 적용. |
| **trust** | 0 ~ 100 | 신뢰도 | 상승은 감쇠 적용, 하락은 감쇠 없음 (비대칭). |
| **familiarity** | 0 ~ ∞ | 상호작용 누적 횟수 | 대화 1회당 +1 자동 증가. 시간 경과 감쇠. |

### 2.2 방향성

- **PC→NPC**: 3축 수치 전체 DB 저장
- **NPC→PC**: 수치 저장 안 함. Python이 HEXACO + PC→NPC 수치 + 기억 태그를 조합하여 태도 태그 생성
- **NPC→NPC**: 같은 노드 NPC끼리 3축 수치 전체 DB 저장

---

## 3. 관계 상태 전이

### 3.1 상태 6단계

```
Stranger → Acquaintance → Friend → Bonded
               ↕               ↕       ↕
            Rival ←――――――――――――┘       ↓
               ↓         (반전 이벤트)   ↑
            Nemesis ―――――――――――――――――→┘
                        (반전 이벤트)
```

### 3.2 전이 조건

| 상태 | 승격 조건 | 하락 조건 |
|------|-----------|-----------|
| **Stranger** | 초기값 | affinity 절대값 < 10 AND familiarity < 3 |
| **Acquaintance** | familiarity ≥ 3 | affinity → (-10, 10) 범위로 떨어짐 |
| **Friend** | affinity ≥ 30 AND trust ≥ 25 | affinity < 15 OR trust < 10 |
| **Bonded** | affinity ≥ 65 AND trust ≥ 60 AND familiarity ≥ 20 AND 특수 이벤트 | affinity < 40 OR trust < 30 |
| **Rival** | affinity ≤ -25 AND familiarity ≥ 5 | affinity > -10 |
| **Nemesis** | affinity ≤ -55 AND trust ≤ 15 | affinity > -30 OR trust > 30 |

### 3.3 해금 효과

| 상태 | 효과 |
|------|------|
| Stranger | 기본 대화만 |
| Acquaintance | 이름 기억, 인사 변화 |
| Friend | 부탁 가능, 할인, 정보 공유 |
| Bonded | 동행, 자발적 도움, 충성 |
| Rival | 방해, 가격 인상, 비협조 |
| Nemesis | 적대 행동, 퀘스트 트리거, 매복 |

### 3.4 판정 시점

상태 전이는 **대화 종료 시** 판정한다. `dialogue_ended` 이벤트를 구독하여 수치 변동 적용 후 새 상태를 계산한다.

---

## 4. 수치 변동 메커니즘

### 4.1 변동 소스

| 소스 | affinity 변동 | trust 변동 | familiarity |
|------|-------------|-----------|------------|
| 대화 1회 | LLM이 META에 제안 (-5~+5) | 0 | +1 (자동) |
| 부탁 수행 | +5~+15 (난이도 비례) | +10~+20 | +1 |
| 부탁 거절 | -3~-5 | -5 | +1 |
| 약속 이행 | +3 | +10~+15 | 0 |
| 약속 파기 | -5 | -20~-30 | 0 |
| 선물 | +3~+10 (취향 일치 시 ×2) | +2 | +1 |
| 전투 협력 | +5~+10 | +10 | +2 |
| 배신 (반전) | -affinity | trust × 0.3 | 0 |
| 목숨 구조 (반전) | -affinity × 0.7 | +30 | +3 |

### 4.2 LLM META JSON 형식

대화 종료 시 LLM이 반환하는 META에 관계 변동 제안이 포함된다:

```json
{
  "narrative": "한스가 고개를 끄덕이며...",
  "meta": {
    "relationship_delta": {
      "affinity": 3,
      "reason": "friendly_conversation"
    },
    "memory_tags": ["discussed_weapon_order"],
    "quest_hook": null
  }
}
```

Python이 `relationship_delta.affinity`를 받아 감쇠 곡선 적용 후 실제 변동값을 계산한다. LLM이 제안하는 범위는 -5~+5이며, Python이 클램핑한다.

### 4.3 감쇠 곡선

#### affinity 감쇠 (양방향 대칭, 지수 1.2)

```python
damping = 1.0 - (abs(current_affinity) / 100) ** 1.2
actual_change = raw_change * max(damping, 0.1)  # 최소 10% 적용
```

| 현재 affinity | damping | +5 제안 → 실제 |
|--------------|---------|---------------|
| 0 | 1.00 | +5.0 |
| 20 | 0.87 | +4.4 |
| 50 | 0.58 | +2.9 |
| 70 | 0.36 | +1.8 |
| 90 | 0.13 | +0.7 |

#### trust 감쇠 (비대칭)

```python
if raw_change >= 0:
    # 상승: 감쇠 적용 (지수 1.2)
    damping = 1.0 - (current_trust / 100) ** 1.2
    actual_change = raw_change * max(damping, 0.1)
else:
    # 하락: 감쇠 없음 (신뢰는 쉽게 무너짐)
    actual_change = raw_change
```

#### familiarity 시간 감쇠

```python
# 마지막 만남 이후 경과 일수 기준
# 30일(게임 내 시간)마다 familiarity -1, 최소 0
decay = days_since_last_interaction // 30
new_familiarity = max(0, current_familiarity - decay)
```

affinity와 trust는 시간 경과로 감쇠하지 않는다. 한번 형성된 감정과 신뢰는 유지되고, 친밀도(familiarity)만 잊혀간다.

---

## 5. 반전 이벤트

### 5.1 반전 유형

| 반전 유형 | 트리거 예시 | affinity 공식 | trust 공식 |
|-----------|------------|---------------|------------|
| **우정→적대 (betrayal)** | 배신, 도둑질, NPC 소중한 것 파괴 | affinity = -affinity | trust = trust × 0.3 |
| **적대→우정 (redemption)** | 목숨 구해줌, 공통 적 앞에서 협력 | affinity = -affinity × 0.7 | trust = trust + 30 |
| **신뢰 붕괴 (trust_collapse)** | 거짓말 발각, 약속 파기 | 변동 없음 | trust = trust × 0.2 |

### 5.2 반전 후 상태 재계산

반전 공식 적용 후 새 수치로 상태를 재계산한다.

예시: Friend (affinity 45, trust 40) → betrayal 반전
- affinity = -45, trust = 40 × 0.3 = 12
- 새 수치: affinity -45, trust 12 → Rival 조건 충족 (affinity ≤ -25, familiarity ≥ 5)
- 상태: Friend → Rival

예시: Rival (affinity -40, trust 15) → redemption 반전
- affinity = -(-40) × 0.7 = 28, trust = 15 + 30 = 45
- 새 수치: affinity 28, trust 45 → Acquaintance 또는 Friend 조건 충족
- 상태: Rival → Acquaintance (affinity < 30이면) 또는 Friend (affinity ≥ 30이면)

---

## 6. Python 태도 태그 생성

### 6.1 3단계 파이프라인

```
입력: PC→NPC 관계 + NPC HEXACO + NPC 기억 태그
  ↓
[1단계] 관계 수치 → 기본 태도 태그
  ↓
[2단계] HEXACO 보정 태그 추가
  ↓
[3단계] 기억 태그 보정 추가
  ↓
출력: attitude_tags (2~7개), tone_modifier
```

### 6.2 1단계: 관계 수치 → 기본 태도

| 조건 | 태그 |
|------|------|
| affinity ≥ 50 | `warm` |
| 20 ≤ affinity < 50 | `friendly` |
| -20 < affinity < 20 | `neutral` |
| -50 < affinity ≤ -20 | `cold` |
| affinity ≤ -50 | `hostile` |
| trust ≥ 60 | `trusting` |
| 30 ≤ trust < 60 | `cautious_trust` |
| trust < 30 | `distrustful` |

### 6.3 2단계: HEXACO 보정

| HEXACO | 조건 | 추가 태그 |
|--------|------|----------|
| H ≤ 0.3 | affinity > 0 | `calculating` |
| E ≥ 0.7 | affinity < 0 | `anxious_around_pc` |
| X ≥ 0.7 | familiarity ≥ 5 | `chatty` |
| X ≤ 0.3 | familiarity < 10 | `reserved` |
| A ≥ 0.7 | trust < 30 | `forgiving_but_wary` |
| A ≤ 0.3 | affinity < 0 | `confrontational` |
| C ≥ 0.7 | 기억에 "paid_on_time" 류 | `respects_reliability` |
| O ≥ 0.7 | familiarity ≥ 3 | `curious_about_pc` |

### 6.4 3단계: 기억 태그 보정

| 기억 태그 | 추가 태도 태그 |
|-----------|---------------|
| `broke_promise` | `remembers_betrayal` |
| `saved_life` | `deeply_grateful` |
| `paid_on_time` (반복) | `reliable_customer` |
| `stole_from_me` | `watches_belongings` |
| `fought_together` | `battle_bond` |
| `shared_secret` | `confidant` |

### 6.5 출력 예시

```
대장장이 한스 (H:0.4, E:0.3, X:0.6, A:0.7, C:0.8, O:0.3)
PC→한스: affinity 35, trust 45, familiarity 8, status: friend
기억: ["paid_on_time", "paid_on_time", "discussed_weapon"]

1단계: ["friendly", "cautious_trust"]
2단계: + ["calculating"]  (H 0.4 ≤ 0.3 → 아니므로 해당 없음... H 0.4 > 0.3이므로 calculating 안 붙음)
       + ["respects_reliability"]  (C 0.8 ≥ 0.7, 기억에 paid_on_time)
3단계: + ["reliable_customer"]  (paid_on_time 반복)

최종: ["friendly", "cautious_trust", "respects_reliability", "reliable_customer"]
→ 4개 태그, 범위 내 (2~7)
```

---

## 7. NPC간 관계

### 7.1 초기 관계 생성

NPC가 승격(`npc_promoted` 이벤트)될 때, 같은 노드의 기존 NPC들과 초기 관계를 생성한다.

```python
# 같은 시설 NPC끼리
initial_relationship = Relationship(
    source_id=new_npc_id,
    target_id=existing_npc_id,
    affinity=random.uniform(-10, 20),  # 약간의 편차
    trust=random.uniform(10, 30),
    familiarity=5,  # 같은 곳에서 일하니 어느 정도 아는 사이
    status=RelationshipStatus.ACQUAINTANCE,
)
```

### 7.2 변동 시점

| 시점 | 트리거 | 예시 |
|------|--------|------|
| PC 행동 | PC가 한 NPC 편을 듦 | 한스 편 들기 → 마리→한스 affinity 변동 없음, 마리→PC affinity 하락 |
| 퀘스트 결과 | PC 선택이 NPC간 관계에 영향 | 분쟁 퀘스트에서 한스 편 → 한스↔마리 관계 악화 |
| Phase B 자율행동 | NPC 욕구 시스템에서 충돌 | 한스(Profit 욕구)가 마리 단골을 가로챔 → 마리→한스 affinity 하락 |

### 7.3 대화에서의 활용

PC가 NPC A와 대화 중 NPC B를 언급하면, A→B 관계를 태그로 변환하여 LLM에 전달:

```python
npc_opinions = {
    "npc_mari": ["speaks_fondly", "old_friend"],      # affinity > 30
    "npc_gorek": ["distrustful", "avoids"],            # trust < 20
}
```

---

## 8. EventBus 인터페이스

### 8.1 관계 모듈이 발행하는 이벤트

| 이벤트 | 데이터 | 구독 예상 |
|--------|--------|----------|
| `relationship_changed` | `{source_id, target_id, field, old_value, new_value, old_status, new_status}` | dialogue, quest_engine, npc_behavior |
| `relationship_reversed` | `{source_id, target_id, reversal_type, old_status, new_status}` | memory, dialogue, quest_engine |
| `attitude_response` | `{request_id, npc_id, target_id, attitude_tags, relationship_status, npc_opinions}` | dialogue |

### 8.2 관계 모듈이 구독하는 이벤트

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `npc_promoted` | npc_core | 같은 노드 NPC들과 초기 관계 생성 |
| `dialogue_ended` | dialogue | META에서 affinity 변동 추출, 감쇠 적용, 상태 전이 판정 |
| `quest_completed` | quest_engine | 관련 NPC와의 trust/affinity 변동 |
| `attitude_request` | dialogue | 태도 태그 계산 후 `attitude_response` 발행 |
| `turn_processed` | ModuleManager | familiarity 시간 감쇠 체크 |

### 8.3 attitude_request/response 패턴

```python
# dialogue 모듈이 대화 시작 시:
event_bus.emit(GameEvent(
    event_type="attitude_request",
    data={
        "request_id": "req_001",
        "npc_id": "npc_hans",
        "target_id": "player_001",
        "include_npc_opinions": True,  # 같은 노드 NPC에 대한 태도 포함 여부
    },
    source="dialogue",
))

# relationship 모듈이 구독 → 계산 → 응답:
event_bus.emit(GameEvent(
    event_type="attitude_response",
    data={
        "request_id": "req_001",
        "npc_id": "npc_hans",
        "target_id": "player_001",
        "attitude_tags": ["friendly", "cautious_trust", "respects_reliability"],
        "relationship_status": "friend",
        "npc_opinions": {
            "npc_mari": ["speaks_fondly"],
            "npc_gorek": ["distrustful"],
        },
    },
    source="relationship",
))
```

---

## 9. 데이터 모델

### 9.1 Relationship

```python
@dataclass
class Relationship:
    relationship_id: str              # UUID
    source_type: str                  # "player" | "npc"
    source_id: str                    # player_id 또는 npc_id
    target_type: str                  # "player" | "npc"
    target_id: str                    # npc_id

    # 3축 수치
    affinity: float = 0.0             # -100 ~ +100
    trust: float = 0.0                # 0 ~ 100
    familiarity: int = 0              # 0 ~ ∞

    # 상태
    status: RelationshipStatus = RelationshipStatus.STRANGER
    tags: List[str] = field(default_factory=list)  # ["debt_owed", "saved_life", ...]

    # 메타
    last_interaction_turn: int = 0    # familiarity 감쇠 기준
    created_at: str = ""
    updated_at: str = ""
```

### 9.2 RelationshipStatus

```python
class RelationshipStatus(str, Enum):
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    BONDED = "bonded"
    RIVAL = "rival"
    NEMESIS = "nemesis"
```

### 9.3 AttitudeContext

```python
@dataclass
class AttitudeContext:
    """태도 태그 생성 결과. EventBus attitude_response에 사용."""
    target_npc_id: str
    attitude_tags: List[str]              # 2~7개
    relationship_status: str
    npc_opinions: Dict[str, List[str]]    # 같은 노드 NPC에 대한 태도
```

### 9.4 상태 전이 조건 테이블 (코드용)

```python
TRANSITION_TABLE = {
    RelationshipStatus.STRANGER: {
        "promote": lambda r: r.familiarity >= 3,
        "promote_to": RelationshipStatus.ACQUAINTANCE,
    },
    RelationshipStatus.ACQUAINTANCE: {
        "promote": lambda r: r.affinity >= 30 and r.trust >= 25,
        "promote_to": RelationshipStatus.FRIEND,
        "demote": lambda r: abs(r.affinity) < 10 and r.familiarity < 3,
        "demote_to": RelationshipStatus.STRANGER,
        "rival": lambda r: r.affinity <= -25 and r.familiarity >= 5,
        "rival_to": RelationshipStatus.RIVAL,
    },
    RelationshipStatus.FRIEND: {
        "promote": lambda r: r.affinity >= 65 and r.trust >= 60 and r.familiarity >= 20,
        "promote_to": RelationshipStatus.BONDED,  # + 특수 이벤트 필요
        "demote": lambda r: r.affinity < 15 or r.trust < 10,
        "demote_to": RelationshipStatus.ACQUAINTANCE,
    },
    RelationshipStatus.BONDED: {
        "demote": lambda r: r.affinity < 40 or r.trust < 30,
        "demote_to": RelationshipStatus.FRIEND,
    },
    RelationshipStatus.RIVAL: {
        "demote": lambda r: r.affinity > -10,
        "demote_to": RelationshipStatus.ACQUAINTANCE,
        "promote": lambda r: r.affinity <= -55 and r.trust <= 15,
        "promote_to": RelationshipStatus.NEMESIS,
    },
    RelationshipStatus.NEMESIS: {
        "demote": lambda r: r.affinity > -30 or r.trust > 30,
        "demote_to": RelationshipStatus.RIVAL,
    },
}
```

---

## 10. 기억 시스템 연동

관계도(familiarity)가 NPC 기억 Tier 2 용량을 결정한다 (npc-system.md 참조):

| familiarity | Tier 2 기억 슬롯 |
|-------------|------------------|
| 0~4 | 3개 |
| 5~9 | 5개 |
| 10~14 | 8개 |
| 15~19 | 12개 |
| 20+ | 20개 |

이 매핑은 relationship 모듈이 `attitude_response`에 포함하여 memory 모듈이 참조할 수 있도록 한다.

---

## 11. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2025-02-08 | 최초 작성 |
