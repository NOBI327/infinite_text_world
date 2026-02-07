# ITW 시뮬레이션 범위 규칙

**버전**: 1.0  
**작성일**: 2025-02-08  
**상태**: 확정  
**관련**: npc-system.md, relationship-system.md

---

## 1. 개요

### 1.1 목적

이 문서는 NPC 시뮬레이션의 공간적 범위와, 범위 밖으로 벗어난 NPC의 처리 규칙을 정의한다. 무한한 월드에서 모든 NPC를 시뮬레이션할 수 없으므로, PC 주변만 풀 시뮬레이션하고 나머지는 간소화한다.

### 1.2 핵심 원칙

- PC 주변 5×5 노드만 풀 시뮬레이션 (Active Zone)
- 범위 밖 NPC는 상태만 추적, 서술/자율행동 없음 (Background Zone)
- 퀘스트/이벤트 관련 NPC는 범위와 무관하게 백그라운드 처리
- 욕구로 벗어난 NPC는 유예 턴 후 통상 스케줄 위치로 귀환

---

## 2. 시뮬레이션 존

### 2.1 존 정의

```
┌─────────────────────────────────────┐
│          Background Zone            │
│  ┌───────────────────────────────┐  │
│  │       Active Zone (5×5)       │  │
│  │                               │  │
│  │    PC 중심 ±2 노드 범위       │  │
│  │    풀 시뮬레이션              │  │
│  │                               │  │
│  └───────────────────────────────┘  │
│  상태만 추적, 서술 없음             │
└─────────────────────────────────────┘
```

### 2.2 Active Zone (5×5, 25노드)

PC 위치 `(px, py)` 기준:

```python
active_nodes = {
    (x, y)
    for x in range(px - 2, px + 3)
    for y in range(py - 2, py + 3)
}
```

#### Active Zone에서 처리하는 것

| 시스템 | 처리 내용 |
|--------|----------|
| NPC 자율행동 | Phase A 스케줄, Phase B 욕구 판정 |
| 대화 | LLM 호출, META 생성, 관계 변동 |
| 관계 변동 | affinity/trust 변경, 상태 전이 판정 |
| NPC간 관계 | 같은 노드 NPC끼리 상호작용 |
| 이동 | NPC 노드간 이동 처리 |
| 태도 태그 생성 | 3단계 파이프라인 (관계수치→HEXACO→기억) |
| 오버레이 영향 | Weather, Territory 등 오버레이 효과 적용 |

### 2.3 Background Zone (Active 밖 전체)

#### Background Zone에서 처리하는 것

| 처리 | 내용 |
|------|------|
| 위치 기록 | DB에 마지막 위치 저장 |
| 상태 유지 | HP, 관계 수치, 기억 등 그대로 보존 |
| 시간 감쇠 | familiarity 시간 감쇠는 적용 (DB 기준 계산) |

#### Background Zone에서 처리하지 않는 것

| 미처리 | 이유 |
|--------|------|
| 자율행동 | 연산 비용 |
| LLM 호출 | 토큰 비용 |
| NPC간 관계 변동 | PC가 관여하지 않는 관계 변동은 게임성 기여 낮음 |
| 오버레이 반응 | PC가 관찰하지 않으므로 불필요 |

---

## 3. Zone 전환 처리

### 3.1 Background → Active (NPC가 Active Zone에 진입)

PC가 이동하여 Active Zone이 이동하면, 새로 포함된 노드의 NPC를 활성화한다.

```python
# PC 이동 후
new_active = calculate_active_zone(new_px, new_py)
old_active = calculate_active_zone(old_px, old_py)

entering_nodes = new_active - old_active    # 새로 Active에 들어온 노드
leaving_nodes = old_active - new_active     # Active에서 나간 노드
```

**진입 시 처리:**

```
1. 해당 노드의 NPC를 DB에서 로드
2. 경과 시간에 따른 familiarity 감쇠 일괄 적용
3. 스케줄에 따라 NPC 위치 보정 (현재 시간대에 맞는 위치로)
4. 다음 턴부터 풀 시뮬레이션
```

### 3.2 Active → Background (NPC가 Active Zone에서 이탈)

**이탈 시 처리:**

```
1. NPC 현재 상태를 DB에 저장
2. 이탈 사유 분류 (아래 섹션 4 참조)
3. 사유에 따른 백그라운드 처리 등록
```

---

## 4. Active Zone 밖 NPC 처리

### 4.1 분류

NPC가 Active Zone 밖에 있는 사유를 2가지로 분류한다:

| 사유 | 예시 | 처리 |
|------|------|------|
| **이벤트 관련 (event_bound)** | 퀘스트 수행 중, 이벤트 NPC | 백그라운드 처리 유지 |
| **욕구 이탈 (desire_wandered)** | Phase B 욕구로 이동, 방랑형 NPC 스케줄 | 유예 턴 후 귀환 |

### 4.2 이벤트 관련 NPC (event_bound)

퀘스트나 이벤트에 묶인 NPC는 Active Zone과 무관하게 상태를 추적한다.

```python
@dataclass
class BackgroundTask:
    npc_id: str
    task_type: str          # "quest_travel", "event_role", ...
    destination_node: str   # 목적지 "x_y"
    estimated_turns: int    # 예상 소요 턴
    elapsed_turns: int = 0  # 경과 턴
    on_complete: str        # 완료 시 발행할 이벤트
```

**처리 규칙:**
- 매 턴 `elapsed_turns += 1`
- `elapsed_turns >= estimated_turns`이면 목적지 도착으로 처리
- 도착 시 `on_complete` 이벤트 발행 (예: `quest_npc_arrived`)
- PC가 해당 노드에 접근하면 풀 시뮬레이션 재개

**백그라운드에서 기록되는 것:**
- 이동 경로 (노드 목록)
- 도착 시간
- 타 노드에서 맺은 관계 → DB에 기록 (간소화: 관계 태그만, 수치는 고정값)

### 4.3 욕구 이탈 NPC (desire_wandered)

Phase B 욕구로 통상 스케줄 밖으로 벗어나 Active Zone을 이탈한 NPC.

**유예 턴 계산:**

```python
home_node = npc.schedule.get_home_node()
current_node = npc.current_node
distance = manhattan_distance(current_node, home_node)

return_turns = distance * 2  # 1노드당 2턴
```

**처리 흐름:**

```
턴 T: NPC가 Active Zone 이탈 (desire_wandered)
  → return_timer 시작 (return_turns = distance × 2)

턴 T+1 ~ T+N:
  → 매 턴 return_timer -= 1
  → 매 턴 NPC 위치를 홈 방향으로 1노드 이동 (2턴마다)
  → PC가 해당 노드에 접근하면 → 귀환 중단, 현재 위치에서 풀 시뮬레이션 재개

턴 T+N (return_timer == 0):
  → NPC를 홈 노드에 배치
  → 통상 스케줄 재개
```

**PC 접근 시 처리:**

```
PC가 이동 → 새 Active Zone 계산
  → 귀환 중인 NPC가 새 Active Zone 안에 있으면:
    → 귀환 중단
    → 현재 위치에서 풀 시뮬레이션 재개
    → 자연스러운 묘사: "길에서 마주침" 등
```

### 4.4 NPC 이동 경로 기록 (타 노드 관계)

이벤트 관련 NPC가 타 노드에서 다른 NPC와 상호작용한 경우:

```python
@dataclass
class OffscreenInteraction:
    """Active Zone 밖에서 발생한 NPC 상호작용 기록"""
    npc_id: str
    other_npc_id: str
    node_id: str               # 상호작용 발생 노드
    turn: int
    interaction_type: str      # "trade", "conflict", "conversation"
    result_tags: List[str]     # ["traded_goods", "minor_dispute"]
    affinity_delta: float      # 고정값 (간소화)
    trust_delta: float         # 고정값 (간소화)
```

**간소화 규칙:**
- 백그라운드에서는 LLM 호출 안 함
- 상호작용 유형별 고정 수치 적용 (trade: affinity +3, trust +5 등)
- PC가 해당 NPC와 대화 시 기억으로 전달 가능 ("어제 마을에서 거래를 했다")

---

## 5. 연산량 추정

### 5.1 Active Zone (턴당)

```
가정: 5×5 = 25노드, 노드당 승격 NPC 평균 2명, 최대 ~50명

NPC 자율행동 판정:   50명 × 욕구 체크 (dict 조회)        → ~0.1ms
관계 감쇠 체크:      50명 × familiarity 감쇠 (산술)       → ~0.05ms
스케줄 체크:         50명 × 시간대 매칭 (dict lookup)      → ~0.05ms
이동 처리:           ~5명 × 경로 계산 (1홉)               → ~0.1ms
태도 태그 생성:      ~5명 × 3단계 파이프라인               → ~0.2ms
──────────────────────────────────────────────────────
Python 총합:                                              → ~0.5ms

DB 쿼리:
  관계 조회:   SELECT WHERE node_id IN (25개)              → ~5ms
  NPC 조회:    SELECT WHERE node_id IN (25개)              → ~3ms
──────────────────────────────────────────────────────
DB 총합:                                                   → ~8ms

비교:
  LLM API 호출 (대화 1회):                                 → 1,000~3,000ms
```

**결론: Python + DB 연산은 LLM 대비 0.3% 미만. 병목은 항상 LLM이다.**

### 5.2 Background Zone (턴당)

```
이벤트 NPC 타이머:    ~5명 × elapsed += 1                  → 무시 가능
욕구 이탈 NPC 귀환:   ~3명 × 위치 업데이트                  → 무시 가능
──────────────────────────────────────────────────────
총합:                                                      → < 0.01ms
```

---

## 6. 특수 케이스

### 6.1 유랑형 NPC (Wandering Type)

npc-system.md의 유랑형 배경 존재는 통상 스케줄이 "이동"이므로, Active Zone 이탈이 정상 동작이다.

- 유랑형 NPC는 `desire_wandered`가 아닌 `schedule_normal`로 분류
- 홈 노드 없음 → 귀환 로직 미적용
- Active Zone 이탈 시 다음 스케줄 노드를 DB에 기록
- PC가 해당 노드에 도착하면 자연스럽게 등장

### 6.2 PC가 빠르게 이동하는 경우

PC가 매 턴 이동하면 Active Zone이 빠르게 이동한다. 이 때:

- 진입 노드의 NPC 로드가 매 턴 발생 → DB 쿼리 증가
- 하지만 SQLite 로컬 쿼리이므로 ~5ms, 병목 아님
- NPC가 아직 Background 처리 중인데 Active에 다시 진입할 수 있음 → 현재 상태로 즉시 활성화

### 6.3 NPC 밀집 노드

특정 노드(시장, 주요 시설)에 NPC가 10명 이상 밀집할 수 있다.

- Active Zone 내라면 전부 시뮬레이션 (50명까지 ~0.5ms이므로 문제 없음)
- 대화는 한 번에 1명이므로 LLM 부하는 동일
- 태도 태그 생성만 NPC 수에 비례하지만, 대화 상대에 대해서만 생성하면 됨

---

## 7. 구현 인터페이스

### 7.1 SimulationScope (Core 레벨)

`ACTIVE_RADIUS`는 설정 파일 또는 엔진 초기화 시 조절 가능하다. 밸런스 테스트 결과에 따라 2~4 범위에서 조정한다.

```python
@dataclass
class SimulationScope:
    """시뮬레이션 범위 계산

    ACTIVE_RADIUS 기본값 2 → 5×5 (25노드)
    조절 예: 1 → 3×3 (9노드), 3 → 7×7 (49노드), 4 → 9×9 (81노드)
    """
    active_radius: int = 2  # 기본값 2 (5×5). 설정으로 변경 가능.

    def get_active_nodes(self, px: int, py: int) -> set[tuple[int, int]]:
        r = self.active_radius
        return {
            (x, y)
            for x in range(px - r, px + r + 1)
            for y in range(py - r, py + r + 1)
        }

    def is_active(self, px: int, py: int, nx: int, ny: int) -> bool:
        r = self.active_radius
        return abs(px - nx) <= r and abs(py - ny) <= r
```

### 7.2 BackgroundTask

```python
@dataclass
class BackgroundTask:
    npc_id: str
    task_type: str              # "event_bound" | "desire_wandered"
    origin_node: str            # 출발 노드 "x_y"
    destination_node: str       # 목적지 "x_y" (또는 홈 노드)
    total_turns: int            # 소요 턴
    elapsed_turns: int = 0
    current_node: str = ""      # 현재 위치 (매 턴 업데이트)
    on_complete: Optional[str] = None  # 완료 시 이벤트

    @property
    def is_complete(self) -> bool:
        return self.elapsed_turns >= self.total_turns

    def tick(self) -> None:
        """턴 진행"""
        self.elapsed_turns += 1
        # 2턴마다 1노드 이동 (중간 경로 계산)
```

### 7.3 OffscreenInteraction

```python
@dataclass
class OffscreenInteraction:
    npc_id: str
    other_npc_id: str
    node_id: str
    turn: int
    interaction_type: str       # "trade" | "conflict" | "conversation"
    result_tags: List[str]
    affinity_delta: float
    trust_delta: float
```

---

## 8. EventBus 연동

| 이벤트 | 발행 시점 | 데이터 |
|--------|----------|--------|
| `zone_changed` | PC 이동 후 | `{entering_nodes, leaving_nodes}` |
| `npc_entered_active` | NPC가 Active Zone 진입 | `{npc_id, node_id}` |
| `npc_left_active` | NPC가 Active Zone 이탈 | `{npc_id, node_id, reason}` |
| `background_task_complete` | 백그라운드 작업 완료 | `{npc_id, task_type, destination}` |
| `npc_returning` | 욕구 이탈 NPC 귀환 시작 | `{npc_id, from_node, to_node, turns}` |
| `npc_intercepted` | PC가 귀환 중 NPC와 마주침 | `{npc_id, node_id}` |

---

## 9. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2025-02-08 | 최초 작성 |
