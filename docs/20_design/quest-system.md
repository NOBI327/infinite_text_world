# ITW 퀘스트 시스템 설계서

**버전**: 1.0  
**작성일**: 2026-02-08  
**상태**: 확정  
**관련**: npc-system.md, relationship-system.md, overlay-layer-system.md, simulation-scope.md

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 퀘스트 시스템을 정의한다. 퀘스트는 Python이 발생을 제어하고, LLM이 내용을 생성하는 2단계 구조로 동작한다. NPC 대화와 환경 이벤트 두 경로로 발생하며, 완료된 퀘스트는 확률적으로 체이닝되어 연작을 형성한다.

### 1.2 핵심 원칙

- **Python 선행 제어**: 퀘스트 발생 여부는 Python이 확률 판정, LLM은 내용(이유, 서술)만 생성
- **PC 선택권**: 대화 퀘스트는 시드(떡밥)를 심고 PC가 반응해야 활성화 — 강제 발동 없음
- **확률적 체이닝**: 새 퀘스트 발생 시 기존 퀘스트와 연결 여부를 확률로 결정, LLM이 연결 서술 생성
- **오버레이 자동 연동**: 퀘스트 활성화 시 L4 Quest 오버레이 자동 생성
- **EventBus 통신**: 모듈간 직접 호출 금지

### 1.3 모듈 위치

- **Layer**: 3 (상호작용 모듈)
- **의존성**: npc_core, relationship, dialogue
- **위치**: `src/modules/quest/`

---

## 2. 퀘스트 발생 경로

### 2.1 두 가지 트리거

| 경로 | 트리거 | 발생 조건 | PC 선택권 |
|------|--------|-----------|-----------|
| **대화 퀘스트** | NPC 대화 시작 전 확률 판정 | 5% (단순 확률) | 있음 (시드 무시 가능) |
| **환경 퀘스트** | 오버레이 수치 임계값 초과 | 조건 충족 시 자동 | 수락/거부 가능 |

### 2.2 대화 퀘스트 흐름 (Quest Seed)

```
[Python] 대화 시작 전 확률 판정 (5%)
    │
    ├─ 실패 (95%) → 일반 대화 진행
    │
    └─ 성공 (5%) → quest_seed 생성
         │
         ├─ LLM에 "quest_seed_active" 플래그 + 시드 유형 전달
         │
         └─ LLM이 대화에 자연스러운 떡밥 포함
              │
              ├─ PC가 반응 → 퀘스트 활성화 (LLM이 META에 quest_accepted 반환)
              │    └─ Python이 퀘스트 DB 등록 + L4 오버레이 생성
              │
              └─ PC가 무시 → 시드를 NPC 기억(Tier 2)에 저장
                   └─ 시드에 TTL(수명) 부여
```

### 2.3 Quest Seed 상세

```python
@dataclass
class QuestSeed:
    """대화에 심어지는 퀘스트 떡밥"""
    seed_id: str                    # UUID
    npc_id: str                     # 시드를 가진 NPC
    seed_type: str                  # "personal", "rumor", "request", "warning"
    seed_tier: int                  # 1(대), 2(중), 3(소) — 서사 규모
    created_turn: int               # 생성 턴
    ttl_turns: int                  # 수명 (턴 단위)
    status: str                     # "active" | "accepted" | "expired" | "resolved_offscreen"
    context_tags: List[str]         # LLM에 전달할 컨텍스트 ["missing_person", "family"]
    expiry_result: Optional[str]    # TTL 만료 시 결과 태그 ("victim_found_dead", "problem_resolved")
```

#### Seed 유형

| 유형 | 예시 | TTL 기본값 |
|------|------|-----------|
| `personal` | "사촌이 안 돌아왔어..." | 15턴 |
| `rumor` | "동쪽 숲에서 이상한 소리가..." | 30턴 |
| `request` | "혹시 다음에 올 때 약초 좀..." | 20턴 |
| `warning` | "요즘 밤에 돌아다니면 위험해" | 10턴 |

#### Seed 수명 처리

```python
def process_seed_ttl(seed: QuestSeed, current_turn: int) -> None:
    """매 턴 시드 수명 체크"""
    elapsed = current_turn - seed.created_turn
    if elapsed >= seed.ttl_turns and seed.status == "active":
        seed.status = "expired"
        # 만료 결과를 NPC 기억에 기록
        # → 다음 대화 시 LLM이 참조하여 후속 서술 생성
        # 예: "안타깝게도 시체로 발견됐다네..."
```

#### PC가 만료 전 시드를 언급하는 경우

```
PC: "저번에 사촌 얘기 말이야..."
  → Python: NPC 기억에서 활성 시드 조회
    → 시드 TTL 남아있음 → LLM 컨텍스트에 시드 포함
      → NPC: "아! 아직도 찾는 중이라네, 도와주겠나?"
      → PC 수락 → 퀘스트 활성화
    → 시드 TTL 만료 → LLM 컨텍스트에 만료 결과 포함
      → NPC: "안타깝게도 시체로 발견됐다네. 더 빨리 갔더라면..."
      → 만료 결과가 새로운 시드가 될 수 있음 (복수, 조사 등)
```

### 2.4 환경 퀘스트 흐름

```
[오버레이 시스템] severity 임계값 초과 감지
    │
    └─ EventBus: "environment_quest_trigger" 발행
         │
         └─ [Quest 모듈] 퀘스트 자동 생성
              │
              ├─ LLM이 환경 상황 기반 퀘스트 내용 생성
              │
              └─ PC에게 알림 (NPC를 통해 전달, 또는 직접 감지)
                   │
                   ├─ PC 수락 → 퀘스트 활성화
                   └─ PC 거부 → 환경 악화 지속 (severity 상승)
```

#### 환경 퀘스트 트리거 조건

| 오버레이 | 임계값 | 퀘스트 예시 |
|---------|--------|------------|
| L2 Weather | severity ≥ 0.7 | 폭풍 대비, 피난 지원 |
| L3 Territory | 영역 분쟁 발생 | 중재, 방어, 정찰 |
| L5 Event | 이벤트 활성화 | 이벤트 관련 해결 과제 |

---

## 3. 퀘스트 구조

### 3.1 Quest 데이터 모델

```python
@dataclass
class Quest:
    quest_id: str                   # UUID
    title: str                      # LLM 생성 제목
    description: str                # LLM 생성 설명

    # 출처
    origin_type: str                # "conversation" | "environment"
    origin_npc_id: Optional[str]    # 대화 퀘스트: 의뢰 NPC
    origin_seed_id: Optional[str]   # 대화 퀘스트: 원본 시드
    origin_overlay_id: Optional[str]  # 환경 퀘스트: 트리거 오버레이

    # 유형
    quest_type: str                 # "fetch" | "deliver" | "escort" | "investigate"
                                    # | "resolve" | "negotiate" | "bond" | "rivalry"
    seed_tier: int                  # 1(대), 2(중), 3(소) — 서사 규모, 체이닝 확률 결정
    urgency: str                    # "normal" | "urgent"
    time_limit: Optional[int]       # urgent일 때만: 턴 제한

    # 상태
    status: str                     # "active" | "completed" | "failed" | "abandoned"
    result: Optional[str]           # "success" | "partial" | "failure" | "abandoned"
    activated_turn: int             # 활성화 턴
    completed_turn: Optional[int]   # 완료/실패 턴

    # 체이닝
    chain_id: Optional[str]         # 연작 ID (체이닝 시)
    chain_index: int = 0            # 연작 내 순서 (0부터)
    is_chain_finale: bool = False   # 완결 퀘스트 여부
    chain_eligible_npcs: List[ChainEligibleNPC] = field(default_factory=list)  # 연작 가능 NPC
    unresolved_threads: List[str] = field(default_factory=list)  # 미해결 복선 태그

    # 관련 엔티티
    related_npc_ids: List[str]      # 관련 NPC들
    target_node_ids: List[str]      # 목적지 노드들
    overlay_id: Optional[str]       # 생성된 L4 오버레이 ID

    # 해결 기록
    resolution_method: Optional[str] = None    # PC가 취한 수단 요약
    resolution_comment: Optional[str] = None   # NPC 한줄평 (대사)
    resolution_method_tag: Optional[str] = None  # 수단 태그 ("unconventional_transport" 등)
    resolution_impression_tag: Optional[str] = None  # NPC 인상 태그 ("grateful_but_bewildered" 등)

    # 보상 (결과에 따라 Python이 계산)
    rewards: Optional[QuestRewards] = None

    # 메타
    tags: List[str] = field(default_factory=list)  # ["missing_person", "family", "mountain"]
    created_at: str = ""
    updated_at: str = ""
```

### 3.2 퀘스트 유형

| 카테고리 | 유형 | 설명 | 예시 |
|---------|------|------|------|
| **전달** | `fetch` | 아이템 수집/수거 | "산에서 약초를 가져다줘" |
| | `deliver` | 아이템/메시지 전달 | "이 편지를 동쪽 마을에 전해줘" |
| | `escort` | NPC 호위 | "사촌을 찾아서 데려와줘" |
| **해결** | `investigate` | 조사/탐색 | "숲에서 나는 이상한 소리를 조사해줘" |
| | `resolve` | 문제 해결 | "폭풍으로 무너진 다리를 수리해" |
| | `negotiate` | 협상/중재 | "두 상인의 분쟁을 중재해줘" |
| **관계** | `bond` | 우정/동맹 관련 | "한스의 대장간 확장을 도와줘" |
| | `rivalry` | 적대/경쟁 관련 | "고렉이 보낸 도적을 처리해" |

### 3.3 긴급도

| 긴급도 | 시간 제한 | 실패 조건 | 예시 |
|--------|----------|-----------|------|
| `normal` | 없음 | 포기만 실패 | 약초 수집, 물건 전달 |
| `urgent` | 있음 (턴 제한) | 턴 초과 시 실패 | 실종자 수색, 폭풍 대비 |

### 3.4 퀘스트 결과 4단계

| 결과 | 조건 | 보상 | 관계 영향 |
|------|------|------|----------|
| **success** | 모든 목표 달성 | 전체 보상 | affinity/trust 상승 |
| **partial** | 일부 목표 달성 | 부분 보상 (50~80%) | affinity 소폭 상승, trust 변동 없음 |
| **failure** | urgent 시간 초과, 핵심 목표 미달성 | 보상 없음 | trust 하락 |
| **abandoned** | PC가 포기 선언 | 보상 없음 | affinity/trust 하락 |

---

## 4. 퀘스트 보상

### 4.1 보상 구조

```python
@dataclass
class QuestRewards:
    """퀘스트 완료 시 보상. result에 따라 Python이 계산."""
    relationship_deltas: Dict[str, RelationshipDelta]  # npc_id → 변동값
    items: List[str]                                    # 아이템 ID 목록
    world_changes: List[WorldChange]                    # 노드 상태 변경
    experience: int = 0                                 # 경험치 (추후 확장)
```

### 4.2 관계 변동 (결과별)

| 결과 | 의뢰 NPC affinity | 의뢰 NPC trust | 관련 NPC |
|------|------------------|----------------|----------|
| success | +5 ~ +15 | +10 ~ +20 | 개별 판정 |
| partial | +2 ~ +5 | 0 | 개별 판정 |
| failure | 0 | -5 ~ -10 | 0 |
| abandoned | -3 ~ -5 | -10 ~ -15 | 0 |

### 4.3 월드 변화

```python
@dataclass
class WorldChange:
    """퀘스트 결과로 인한 노드 상태 변경"""
    node_id: str                # 영향 받는 노드
    change_type: str            # "tag_add" | "tag_remove" | "overlay_modify" | "npc_spawn"
    data: Dict[str, Any]        # 변경 내용
```

예시:
- 다리 수리 퀘스트 성공 → 노드에 `bridge_repaired` 태그 추가, 이동 비용 감소
- 도적 소탕 성공 → L3 Territory 오버레이 severity 감소
- 실종자 수색 성공 → 새 NPC 등장 (구출된 사촌)

---

## 5. 퀘스트 체이닝

### 5.1 시드 티어 시스템

퀘스트 시드 생성 시 Python이 확률적으로 서사 규모(티어)를 결정한다. 티어는 체이닝 확률과 LLM의 복선 설치량을 제어한다.

| 티어 | 서사 규모 | 발생 비율 | 체이닝 확률 | LLM 지시 |
|------|----------|----------|------------|----------|
| **Tier 3 (소)** | 심부름, 단발 사건 | 60% | 10% | 복선 없이 완결적 서술 |
| **Tier 2 (중)** | 속사정 있는 이야기 | 30% | 50% | 1~2개 복선 설치 |
| **Tier 1 (대)** | 복선 많은 이야기 | 10% | 80% | 다수 복선, 미해결 요소 남기기 |

#### 티어별 예시

**Tier 3 (소)**: 마을에 오던 행상인이 낭떠러지로 떨어졌다. 구출하면 끝. 심각한 상황이라도 1회로 완결되는 이야기.

**Tier 2 (중)**: 뒷산에서 사라진 사촌. 장작을 주우러 갔다가 옆 산에서 드래곤을 피해온 고블린 부족을 조우, 입막음 때문에 갇혀 있었다. 사촌 구출 → 고블린 문제 해결로 이어질 수 있음.

**Tier 1 (대)**: 납치된 의뢰주의 딸을 구하러 산적을 찾아가는데, 산적도 다른 컬트로부터 의뢰받아 납치한 것이었다. 컬트는 어떤 '재능'을 가진 여자아이들을 모은다는데... 복선이 점진적으로 풀리는 장편 서사.

#### 티어 결정

```python
SEED_TIER_WEIGHTS = {
    3: 0.60,  # 소: 60%
    2: 0.30,  # 중: 30%
    1: 0.10,  # 대: 10%
}

CHAIN_PROBABILITY_BY_TIER = {
    3: 0.10,  # 소: 10% — 가끔 "이게 이거랑!?" 놀라움
    2: 0.50,  # 중: 50%
    1: 0.80,  # 대: 80%
}

def determine_seed_tier() -> int:
    """시드 생성 시 티어 확률 판정"""
    roll = random.random()
    if roll < 0.60:
        return 3
    elif roll < 0.90:
        return 2
    else:
        return 1
```

### 5.2 체이닝 흐름

체이닝은 **퀘스트 완료 시가 아니라, 새 시드 생성 시점(5% 판정)에** 기존 퀘스트 DB를 참조하여 결정한다.

```
새 시드 발생 (5% 판정 성공)
  │
  ├─ [1] Python: 완료된 퀘스트 DB에서 해당 NPC가 chain_eligible에 포함된 퀘스트 검색
  │     (실제 NPC ID 매칭 + role 태그 매칭)
  │
  ├─ 매칭 없음 → 독립 시드 생성 (새 티어 판정)
  │
  └─ 매칭 있음 → 연작 후보 발견
       │
       ├─ [2] 원본 퀘스트의 seed_tier에 따른 체이닝 확률 판정
       │     Tier 3: 10%, Tier 2: 50%, Tier 1: 80%
       │
       ├─ 실패 → 독립 시드 생성
       │
       └─ 성공 → 연작 시드 생성
            │
            ├─ chain_id 계승
            ├─ 원본 체인의 unresolved_threads(미해결 복선) 전달
            └─ LLM에게 연작 지시 + 복선 컨텍스트 전달
```

### 5.3 chain_eligible_npcs (연작 가능 NPC)

퀘스트 완료 시, Python이 퀘스트 태그와 관련 NPC를 기반으로 `chain_eligible_npcs` 목록을 자동 생성하여 퀘스트 DB에 저장한다. Tier 3은 이 목록이 비어 있거나 최소한이고, Tier 2/1은 복선에 따라 확장된다.

```python
@dataclass
class ChainEligibleNPC:
    """연작 퀘스트를 부여할 수 있는 NPC"""
    npc_ref: str            # 실제 npc_id 또는 role 태그
    ref_type: str           # "existing" | "unborn"
    node_hint: Optional[str]  # unborn일 때 등장 예상 위치 ("3_5" 등)
    reason: str             # "quest_giver", "witness", "antagonist", "foreshadowed"
```

#### 기존 NPC vs 미생성 NPC

| ref_type | npc_ref 예시 | 설명 |
|----------|-------------|------|
| `existing` | `"npc_hans_042"` | 이미 존재하는 NPC. 직접 ID 매칭. |
| `unborn` | `"cult_leader"` | 복선에서 암시된 인물. role 태그로 저장. |

#### 미생성 NPC 매칭

```python
def match_unborn_npc(
    eligible: ChainEligibleNPC,
    new_npc: NPC,
) -> bool:
    """새로 승격된 NPC가 미생성 연작 NPC와 매칭되는지 판정"""
    if eligible.ref_type != "unborn":
        return False
    
    # role 태그 매칭
    role_match = eligible.npc_ref in new_npc.tags
    
    # 위치 힌트 매칭 (있으면)
    location_match = True
    if eligible.node_hint:
        location_match = new_npc.current_node == eligible.node_hint
    
    return role_match and location_match
```

**매칭 시점**: NPC가 승격(`npc_promoted` 이벤트)될 때, quest 모듈이 DB의 모든 unborn eligible을 스캔하여 매칭. 매칭되면 해당 NPC에게 연작 시드 발생 확률을 부여한다.

#### chain_eligible 생성 예시

```
퀘스트: "실종된 사촌" (Tier 2) 완료
  → Python이 자동 생성:
  
chain_eligible_npcs = [
    ChainEligibleNPC(
        npc_ref="npc_hans_042",   # 의뢰주 한스
        ref_type="existing",
        node_hint=None,
        reason="quest_giver",
    ),
    ChainEligibleNPC(
        npc_ref="npc_fritz_043",  # 구출된 사촌 프리츠
        ref_type="existing",
        node_hint=None,
        reason="witness",
    ),
    ChainEligibleNPC(
        npc_ref="goblin_chief",   # 복선: 고블린을 이끄는 존재
        ref_type="unborn",
        node_hint="5_8",          # 동쪽 산 너머
        reason="foreshadowed",
    ),
]

unresolved_threads = ["strange_lights_eastern_mountain", "goblin_migration_cause"]
```

### 5.4 시드 생성 시 DB 참조

```python
def generate_seed_with_chain_check(
    npc_id: str,
    quest_db: QuestDatabase,
) -> QuestSeed:
    """시드 생성 시 기존 퀘스트 DB를 참조하여 연작 여부 결정"""
    
    # 1. 해당 NPC가 chain_eligible에 포함된 완료 퀘스트 검색
    eligible_quests = quest_db.find_quests_with_eligible_npc(npc_id)
    
    if not eligible_quests:
        # 독립 시드
        tier = determine_seed_tier()
        return QuestSeed(tier=tier, chain_id=None, ...)
    
    # 2. 가장 최근 관련 퀘스트의 티어로 체이닝 확률 판정
    best_match = max(eligible_quests, key=lambda q: q.completed_turn)
    chain_prob = CHAIN_PROBABILITY_BY_TIER[best_match.seed_tier]
    
    if random.random() < chain_prob:
        # 연작 시드
        return QuestSeed(
            seed_tier=best_match.seed_tier,  # 원본 티어 계승
            chain_id=best_match.chain_id or generate_chain_id(),
            unresolved_threads=best_match.unresolved_threads,
            ...
        )
    else:
        # 확률 실패 → 독립 시드
        tier = determine_seed_tier()
        return QuestSeed(tier=tier, chain_id=None, ...)
```

### 5.5 완결 판정

체이닝된 퀘스트가 완료될 때, 체인 길이에 따라 완결 여부를 판정한다:

```python
def should_finalize_chain(chain_id: str, quests: List[Quest]) -> bool:
    """체인 완결 여부 판정"""
    chain_quests = [q for q in quests if q.chain_id == chain_id]
    chain_length = len(chain_quests)
    
    finalize_chances = {
        1: 0.0,     # 1개: 완결 불가
        2: 0.20,    # 2개: 20%
        3: 0.40,    # 3개: 40%
        4: 0.60,    # 4개: 60%
        5: 0.80,    # 5개: 80%
    }
    chance = finalize_chances.get(chain_length, 0.95)  # 6개 이상: 95%
    return random.random() < chance
```

완결 시 `is_chain_finale = True`, `chain_eligible_npcs`를 비워서 더 이상 연작되지 않음.

### 5.6 LLM 체이닝 서술

체이닝이 결정되면, LLM에게 기존 체인 컨텍스트 + 티어 정보 + 미해결 복선 + **PC 경향 정보**를 전달한다:

```python
chain_context = {
    "chain_id": "chain_001",
    "seed_tier": 2,
    "previous_quests": [
        {
            "title": "실종된 사촌",
            "result": "success",
            "summary": "고블린에게 붙잡힌 프리츠를 구출",
            "resolution_method": "고블린 야영지에 화염 공리로 기습",
            "resolution_comment": "한스: '사촌을 찾아줘서 고맙네. 그런데 고블린이 왜 거기 있었을까...'"
        },
    ],
    "unresolved_threads": ["strange_lights_eastern_mountain", "goblin_migration_cause"],
    "chain_eligible_source": {
        "npc_ref": "goblin_chief",
        "ref_type": "unborn",
        "node_hint": "5_8",
    },
    "pc_tendency": {
        "recent_methods": ["axiom_exploit", "direct_combat", "axiom_exploit"],
        "dominant_style": "axiom_researcher",
        "impression_tags": ["impressed", "bewildered", "impressed"]
    },
    "is_finale": false,
    "instruction": "Tier 2 연작이다. 미해결 복선을 활용하라. PC는 공리 연구형 플레이 경향이 있으므로, 공리 역학이 핵심이 되는 상황을 설계하되 단순 반복이 아닌 새로운 도전을 제시하라."
}
```

#### PC 경향 (pc_tendency)

Python이 완료된 퀘스트의 `resolution_method_tag`와 `resolution_impression_tag`를 집계하여 PC의 플레이 경향을 산출한다. LLM은 이를 참조하여 시나리오에 반영한다.

```python
def calculate_pc_tendency(completed_quests: List[Quest]) -> dict:
    """최근 완료 퀘스트에서 PC 경향 산출"""
    recent = sorted(completed_quests, key=lambda q: q.completed_turn, reverse=True)[:5]
    
    methods = [q.resolution_method_tag for q in recent if q.resolution_method_tag]
    impressions = [q.resolution_impression_tag for q in recent if q.resolution_impression_tag]
    
    # 최빈 수단으로 dominant_style 결정
    style_map = {
        "direct_combat": "brawler",
        "stealth": "infiltrator",
        "negotiation": "diplomat",
        "axiom_exploit": "axiom_researcher",
        "environment_exploit": "tactician",
        "hired_help": "commander",
        "unconventional": "wildcard",
    }
    
    if methods:
        dominant = max(set(methods), key=methods.count)
        dominant_style = style_map.get(dominant, "versatile")
    else:
        dominant_style = "unknown"
    
    return {
        "recent_methods": methods,
        "dominant_style": dominant_style,
        "impression_tags": impressions,
    }
```

**LLM이 PC 경향을 반영하는 방식:**
- 정면돌파형(brawler) → 매복, 수적 열세, 지형 불리 등 전투에 변주를 줌
- 공리연구형(axiom_researcher) → 미지의 공리, 복합 도메인 퍼즐 제시
- 외교형(diplomat) → 양측 다 일리 있는 분쟁, 숨겨진 이해관계
- 종잡을수없는형(wildcard) → NPC들이 PC를 경계하거나 호기심을 보이는 상황

#### 티어별 LLM 지시 차이

| 티어 | 체인 서술 지시 |
|------|-------------|
| Tier 3 | "이전 퀘스트와 가볍게 연결하라. 새 복선은 설치하지 마라." |
| Tier 2 | "이전 퀘스트의 배후를 1단계 더 드러내라. 복선 1개 유지. PC 경향을 고려한 상황을 만들어라." |
| Tier 1 | "미해결 복선을 활용하되 전부 해결하지 마라. 새 복선 추가. 스케일을 확장하라. PC 경향의 약점을 찌르는 상황을 포함하라." |

#### 완결 퀘스트 (is_finale: true) 지시

체인 완결로 판정된 퀘스트는 LLM에게 **복선 완전 회수**를 명시적으로 지시한다:

```python
finale_context = {
    "chain_id": "chain_001",
    "seed_tier": 2,
    "is_finale": true,
    "unresolved_threads": ["strange_lights_eastern_mountain", "goblin_migration_cause"],
    "instruction": (
        "이것은 체인의 최종 퀘스트이다. 반드시 다음을 지켜라:\n"
        "1. unresolved_threads의 모든 미해결 복선을 이번 퀘스트 안에서 해소하라.\n"
        "2. 새로운 복선을 설치하지 마라.\n"
        "3. 체인 전체를 관통하는 결말을 제시하라.\n"
        "4. PC 경향을 반영한 최종 도전을 설계하라."
    ),
}
```

**검증**: Python이 LLM 반환 META를 검사하여 `unresolved_threads`가 전부 resolved 상태인지, 새 복선 태그가 없는지 확인. 미해소 복선이 남아있으면 재생성 요청.

---

## 6. 오버레이 연동

### 6.1 퀘스트 → L4 오버레이 자동 생성

퀘스트가 활성화되면 L4 Quest 오버레이가 자동 생성된다.

```python
def create_quest_overlay(quest: Quest) -> QuestOverlay:
    """퀘스트 활성화 시 L4 오버레이 생성"""
    return QuestOverlay(
        overlay_id=generate_id(),
        quest_id=quest.quest_id,
        affected_nodes=quest.target_node_ids,
        severity=0.3 if quest.urgency == "normal" else 0.6,
        effects={
            "dialogue_tags": quest.tags,          # NPC 대화에 주입
            "encounter_modifier": 1.2,            # 조우 확률 변경
            "economy_modifier": None,             # 경제 수정자 (해당 시)
        },
    )
```

### 6.2 오버레이 효과

| 효과 | 설명 |
|------|------|
| `dialogue_tags` | 퀘스트 태그가 해당 노드 NPC 대화에 주입됨 — NPC가 퀘스트 관련 언급 |
| `encounter_modifier` | 퀘스트 관련 조우(적대 NPC, 대상 등) 확률 변경 |
| `economy_modifier` | 퀘스트가 경제에 영향 (물자 부족, 가격 변동 등) |

### 6.3 퀘스트 종료 시

```
퀘스트 완료/실패/포기
  → L4 오버레이 severity 감소 또는 제거
  → 결과에 따른 월드 변화 적용 (WorldChange)
  → 관련 NPC 관계 변동
```

---

## 7. 퀘스트 판정

### 7.1 수단의 자유 원칙

퀘스트 해결에서 PC의 자유는 **"어떤 스탯을 쓸까"가 아니라 "어떤 수단으로 목표를 달성할까"**에 있다. 목표(Objective)만 달성하면 수단은 전적으로 PC의 발상에 달려 있다.

```
목표: "실종된 프리츠를 찾아 데려와라"

가능한 수단:
  - 직접 산을 구석구석 수색한다
  - 용병을 여러 명 데려가서 수색 범위를 넓힌다
  - 추적 능력이 있는 NPC에게 도움을 요청한다
  - 높은 곳에서 화염 공리로 신호를 보낸다
  - 프리츠를 잡은 자에게 협상을 시도한다
  - (가능하다면) 하늘을 나는 수단으로 수색한다
```

수단이 결정되면 그에 맞는 판정이 따라온다:

```
PC의 수단 선언 (자유 텍스트)
  → LLM이 수단을 해석, META에 판정 제안 반환
    → Python이 Protocol T.A.G. (d6 Dice Pool) 판정 실행
      → 결과를 LLM에 전달 → 서술 생성
```

#### 예시: "산적 소굴에서 인질 구출" 퀘스트

| PC가 선택한 수단 | LLM 해석 | 결과 판정 |
|-----------------|---------|----------|
| 직접 쳐들어가서 싸운다 | 전면 전투 | EXEC 다회 판정 |
| 밤에 몰래 잠입한다 | 은밀 침투 | READ 판정 → 실패 시 EXEC 전투로 전환 |
| 산적 두목에게 몸값 협상을 건다 | 교섭 | WRITE 판정 |
| 뒷산에서 큰 바위를 굴려 입구를 막고 연기를 피워 훈연한다 | 환경 활용 | SUDO 판정 |
| 산적이 쓰는 화염 공리의 약점을 조사하고 물 공리로 상쇄한다 | 공리 역학 활용 | READ → EXEC + 공리 보너스 |
| 마을 전체에 호소하여 민병대를 조직한다 | 군중 동원 | WRITE(설득) → EXEC(지휘) |

**핵심**: Python은 "산적 소굴 = EXEC 판정"이라고 고정하지 않는다. PC의 수단을 LLM이 해석하고, 그에 맞는 판정을 제안한다.

### 7.2 공리 역학 활용 (전투 핵심)

전투 해결의 주된 경로는 **적 NPC의 공리(Axiom)를 파악하고, 공리 간 역학 관계를 이용하는 것**이다. 단순한 능력치 비교로 해결하는 구조를 취하지 않는다.

#### 공리 역학 흐름

```
1. 사전 조사 (선택적)
   PC: "저 산적이 쓰는 마법을 관찰한다"
   → READ 판정 → 성공 시 적의 공리 일부 공개
   → 예: "화염 계열 공리(Fire Axiom, Domain: Force, Resonance: Destruction)"

2. 약점 분석
   PC: "화염의 약점이 뭐지?"
   → 공리 시스템 참조: 같은 Domain은 amplify(×1.1), 같은 Resonance는 resist(×0.8)
   → 시스템: "Water 계열(같은 Force Domain)은 amplify로 상쇄 가능"

3. 역학 적용
   PC: "물 공리를 써서 화염을 상쇄한다"
   → EXEC 판정 + 공리 역학 보너스 적용
   → 결과에 따라 전투 서술 생성
```

#### 공리 정보 공개 단계

| 조사 깊이 | READ 판정 결과 | 공개 정보 |
|-----------|---------------|----------|
| 관찰 (자동) | — | 외형 힌트만 ("불꽃이 감돈다") |
| 기본 조사 | Success | Domain + 대략적 Tier |
| 정밀 조사 | Critical Success | Domain + Resonance + Tier + 약점 힌트 |
| 반복 교전 | 누적 familiarity | 공리 전체 프로필 |

#### META JSON: 판정 제안

```json
{
  "meta": {
    "action_interpretation": {
      "approach": "axiom_exploit",
      "stat": "EXEC",
      "modifiers": [
        {"source": "axiom_counter", "value": 1.1, "reason": "Water vs Fire (same Domain amplify)"},
        {"source": "prior_investigation", "value": 1, "reason": "약점 파악 보너스 다이스"}
      ],
      "description": "PC가 화염 공리의 약점을 파악하고 물 공리로 상쇄를 시도한다"
    }
  }
}
```

### 7.3 NPC 한줄평 (Resolution Comment)

퀘스트 완료 또는 실패 후, LLM이 의뢰 NPC의 시점에서 **PC가 취한 수단에 대한 한줄평**을 생성한다. 이 한줄평은 두 곳에 저장된다:

| 저장 위치 | 용도 | 예시 |
|----------|------|------|
| NPC 기억 (Tier 2) | 태도 태그에 영향, 후속 대화에서 참조 | `"quest_method:unconventional"` |
| 퀘스트 DB (`resolution_comment`) | 체이닝 시 LLM 컨텍스트로 활용 | "사촌을 찾아줘서 고맙네. 그, 그런데 그 이상한 하늘나는 십자가 붙은 상자는 뭔가?" |

#### META JSON: 한줄평 반환

```json
{
  "meta": {
    "quest_result": "success",
    "resolution_comment": {
      "npc_dialogue": "사촌을 찾아줘서 고맙네. 그, 그런데 그 이상한 하늘나는 십자가 붙은 상자는 뭔가?",
      "method_tag": "unconventional_transport",
      "impression_tag": "grateful_but_bewildered"
    }
  }
}
```

#### 한줄평이 태도에 미치는 영향

한줄평의 `impression_tag`는 NPC 기억에 저장되어, relationship-system.md의 3단계 태도 태그 파이프라인에서 기억 보정(3단계)으로 반영된다.

| impression_tag | 태도 태그 보정 |
|---------------|--------------|
| `grateful` | `deeply_grateful` |
| `impressed` | `respects_capability` |
| `bewildered` | `finds_pc_strange` |
| `disappointed` | `questions_judgment` |
| `terrified` | `fears_pc_methods` |

### 7.4 결과 판정

퀘스트 전체 결과는 목표(Objective) 달성 비율로 판정한다. 각 목표의 달성 여부는 위 수단별 판정의 누적이다.

```python
def evaluate_quest_result(quest: Quest, objectives: List[Objective]) -> str:
    """퀘스트 결과 판정"""
    completed = [o for o in objectives if o.completed]
    total = len(objectives)
    
    if not completed:
        return "failure"
    
    completion_ratio = len(completed) / total
    
    if completion_ratio >= 1.0:
        return "success"
    elif completion_ratio >= 0.5:
        return "partial"
    else:
        return "failure"
```

### 7.5 판정에서 LLM과 Python의 역할 분담

| 역할 | 담당 | 예시 |
|------|------|------|
| PC 수단 해석 | LLM | "바위를 굴린다" → 환경 활용 접근으로 해석 |
| 판정 스탯/방식 제안 | LLM (META) | `stat: "SUDO"`, `modifiers: [...]` |
| 실제 다이스 판정 | Python | d6 Dice Pool, Protocol T.A.G. |
| 스탯 제안 검증 | Python | LLM이 비합리적 스탯 제안 시 보정 |
| 공리 역학 계산 | Python | Domain/Resonance 매칭, 보너스/페널티 적용 |
| 결과 서술 | LLM | 판정 결과를 받아 서술 생성 |
| 한줄평 생성 | LLM | 수단에 대한 NPC 반응 서술 |
| 한줄평 저장 | Python | NPC 기억 + 퀘스트 DB 이중 저장 |

---

## 8. LLM 연동

### 8.1 퀘스트 시드 생성 시 LLM 프롬프트

Python이 시드 발생을 결정하면, LLM에게 다음 컨텍스트를 전달한다:

```json
{
  "quest_seed": {
    "active": true,
    "seed_type": "personal",
    "context_tags": ["missing_person", "family", "mountain"],
    "instruction": "대화 중 자연스럽게 이 상황을 언급하라. 직접적인 의뢰가 아닌 걱정/고민으로 표현하라."
  }
}
```

### 8.2 퀘스트 활성화 시 LLM 프롬프트

PC가 시드에 반응하면, LLM에게 퀘스트 내용 생성을 요청한다:

```json
{
  "quest_generation": {
    "seed_type": "personal",
    "context_tags": ["missing_person", "family", "mountain"],
    "npc_personality": {"H": 0.6, "E": 0.7, "X": 0.4, "A": 0.8, "C": 0.5, "O": 0.3},
    "relationship_status": "friend",
    "instruction": "이 NPC의 성격과 PC와의 관계를 반영하여 퀘스트 상세를 생성하라."
  }
}
```

### 8.3 LLM META JSON 반환 형식

```json
{
  "narrative": "한스가 걱정스러운 표정으로...",
  "meta": {
    "quest_seed_response": "accepted",
    "quest_details": {
      "title": "실종된 사촌",
      "description": "한스의 사촌 프리츠가 이틀 전 동쪽 산에 장작을 주우러 갔다가 돌아오지 않았다.",
      "quest_type": "investigate",
      "urgency": "urgent",
      "time_limit": 20,
      "target_hints": ["eastern_mountain", "logging_trail"],
      "tags": ["missing_person", "family", "mountain", "search"],
      "objectives_hint": [
        {"description": "동쪽 산에서 프리츠를 찾아라", "hint_type": "find_npc", "hint_target": "fritz"},
        {"description": "프리츠를 마을로 데려와라", "hint_type": "escort_to", "hint_target": "village"}
      ]
    },
    "relationship_delta": {
      "affinity": 3,
      "reason": "trusted_with_personal_matter"
    }
  }
}
```

### 8.4 만료된 시드 참조 시

```json
{
  "expired_seed": {
    "seed_type": "personal",
    "context_tags": ["missing_person", "family", "mountain"],
    "expiry_result": "victim_found_dead",
    "instruction": "시드가 만료되었다. NPC가 결과를 자연스럽게 전달하라. 이 결과가 새로운 퀘스트 시드가 될 수 있다."
  }
}
```

---

## 9. EventBus 인터페이스

### 9.1 퀘스트 모듈이 발행하는 이벤트

| 이벤트 | 데이터 | 구독 예상 |
|--------|--------|----------|
| `quest_activated` | `{quest_id, quest_type, related_npc_ids, target_node_ids}` | overlay, npc_behavior, dialogue |
| `quest_completed` | `{quest_id, result, rewards, chain_id}` | relationship, overlay, npc_memory, world |
| `quest_failed` | `{quest_id, reason, chain_id}` | relationship, overlay, npc_memory |
| `quest_abandoned` | `{quest_id, chain_id}` | relationship, overlay, npc_memory |
| `quest_seed_created` | `{seed_id, npc_id, seed_type, ttl_turns}` | npc_memory |
| `quest_seed_expired` | `{seed_id, npc_id, expiry_result}` | npc_memory |
| `quest_chain_formed` | `{chain_id, quest_ids}` | dialogue (체인 컨텍스트 참조용) |
| `quest_chain_finalized` | `{chain_id, total_quests, overall_result}` | relationship, world |
| `npc_needed` | `{quest_id, npc_role, node_id}` | npc_core |
| `chain_eligible_matched` | `{quest_id, chain_id, npc_ref, matched_npc_id}` | dialogue, npc_memory |

### 9.2 퀘스트 모듈이 구독하는 이벤트

| 이벤트 | 발행자 | 처리 |
|--------|--------|------|
| `dialogue_started` | dialogue | 대화 퀘스트 시드 발생 확률 판정 (5%) |
| `dialogue_ended` | dialogue | META에서 quest_seed_response 확인, 퀘스트 활성화 |
| `environment_quest_trigger` | overlay | 환경 퀘스트 생성 |
| `npc_created` | npc_core | 퀘스트 관련 NPC 연결 |
| `npc_promoted` | npc_core | unborn chain_eligible NPC 매칭 스캔 |
| `turn_processed` | ModuleManager | 시드 TTL 체크, urgent 퀘스트 시간 체크 |
| `objective_completed` | (게임 액션) | 퀘스트 목표 달성 체크, 결과 판정 |

---

## 10. 동시 퀘스트 관리

### 10.1 제한 없음 (자연 조절)

동시 활성 퀘스트에 하드 제한을 두지 않는다. 대신 자연스러운 조절 메커니즘이 작동한다:

| 조절 메커니즘 | 효과 |
|-------------|------|
| 대화 퀘스트 발생 확률 5% | 대화 20회에 1회 꼴 — 자연적으로 희소 |
| 시드 TTL | 무시한 시드는 자동 만료 — 쌓이지 않음 |
| urgent 퀘스트 시간 제한 | 긴급 퀘스트는 자연 소멸 |
| 퀘스트 쿨다운 | 같은 NPC에게서 연속 시드 발생 방지 (최소 5회 대화 간격) |

### 10.2 쿨다운

```python
NPC_QUEST_COOLDOWN = 5  # 같은 NPC에게서 최소 5회 대화 후 다시 시드 가능

def can_generate_seed(npc_id: str, conversation_count: int) -> bool:
    """해당 NPC에게서 시드 생성 가능 여부"""
    last_seed = get_last_seed_for_npc(npc_id)
    if last_seed is None:
        return True
    
    conversations_since = conversation_count - last_seed.conversation_count
    return conversations_since >= NPC_QUEST_COOLDOWN
```

---

## 11. Simulation Scope 연동

### 11.1 Active Zone 내 퀘스트

Active Zone 안의 퀘스트는 풀 시뮬레이션:
- NPC 대화 시드 판정
- 목표 달성 체크
- 오버레이 효과 적용
- 시간 제한 카운트

### 11.2 Zone 밖 퀘스트 관련 NPC

simulation-scope.md의 `event_bound` NPC 처리:
- 퀘스트 관련 NPC는 Zone 밖에서도 `BackgroundTask`로 추적
- 퀘스트 목적지로 이동 중인 NPC의 진행도 매 턴 업데이트
- PC가 접근하면 풀 시뮬레이션 재개

### 11.3 시드 TTL과 Zone

시드 TTL은 Zone과 무관하게 글로벌로 감소한다:
- NPC가 Background Zone에 있어도 시드 수명은 흘러감
- 이는 "PC가 없어도 세상은 돌아간다" 원칙과 일치

---

## 12. 데이터 모델 요약

### 12.1 DB 테이블 (예정)

| 테이블 | 주요 필드 |
|--------|----------|
| `quests` | quest_id, title, description, origin_type, quest_type, seed_tier, urgency, status, result, chain_id, chain_index, is_chain_finale, activated_turn, completed_turn, resolution_method, resolution_comment, resolution_method_tag, resolution_impression_tag |
| `quest_seeds` | seed_id, npc_id, seed_type, seed_tier, created_turn, ttl_turns, status, context_tags, expiry_result, chain_id (연작 시드일 때) |
| `quest_chain_eligible` | id, quest_id, npc_ref, ref_type, node_hint, reason |
| `quest_unresolved_threads` | id, quest_id (or chain_id), thread_tag, created_turn, resolved |
| `quest_objectives` | objective_id, quest_id, description, completed, completed_turn |
| `quest_rewards` | reward_id, quest_id, reward_type, data |
| `quest_chains` | chain_id, created_turn, finalized, total_quests |

### 12.2 Objective

```python
@dataclass
class Objective:
    """퀘스트 목표 단위"""
    objective_id: str
    quest_id: str
    description: str                # LLM 생성
    objective_type: str             # "reach_node" | "find_item" | "talk_to_npc" | "resolve_check"
    target: Dict[str, Any]          # {"node_id": "3_5"} or {"npc_id": "npc_fritz"} etc.
    completed: bool = False
    completed_turn: Optional[int] = None
```

#### Objective 생성 흐름: LLM 제안 → Python 검증/구조화

```
퀘스트 활성화 시 LLM이 META에 목표를 제안한다.
Python이 이를 검증하여 구조화된 Objective로 변환한다.

LLM 제안 (META):
  objectives_hint: [
    {"description": "동쪽 산에서 프리츠를 찾아라", "hint_type": "find_npc", "hint_target": "fritz"},
    {"description": "프리츠를 마을로 데려와라", "hint_type": "escort_to", "hint_target": "village"}
  ]

Python 검증:
  1. hint_type → objective_type 매핑 (유효성 체크)
  2. hint_target → 실제 엔티티 ID 매칭 (DB 조회)
  3. 검증 실패 시 → 퀘스트 유형 기반 fallback 목표 자동 생성
```

#### hint_type → objective_type 매핑

| LLM hint_type | objective_type | 완료 조건 (Python 자동 판정) |
|---------------|---------------|--------------------------|
| `find_npc` | `talk_to_npc` | 해당 NPC와 대화 시 |
| `escort_to` | `reach_node` | NPC와 함께 목표 노드 도착 시 |
| `fetch_item` | `find_item` | 해당 아이템 획득 시 |
| `deliver_item` | `reach_node` + `find_item` | 목표 노드에서 아이템 전달 시 |
| `investigate_area` | `reach_node` | 해당 노드에서 investigate 액션 시 |
| `resolve_problem` | `resolve_check` | Protocol T.A.G. 판정 성공 시 |
| (인식 불가) | fallback | 퀘스트 유형별 기본 목표 생성 |

#### Fallback 목표 (퀘스트 유형별)

LLM 제안이 검증 실패하거나 비어있을 때 Python이 자동 생성:

```python
FALLBACK_OBJECTIVES = {
    "fetch": [{"type": "find_item", "description": "요청된 물품을 구하라"}],
    "deliver": [{"type": "reach_node", "description": "목적지에 도착하라"}],
    "escort": [{"type": "reach_node", "description": "대상을 목적지에 호위하라"}],
    "investigate": [{"type": "reach_node", "description": "해당 지역을 조사하라"}],
    "resolve": [{"type": "resolve_check", "description": "문제를 해결하라"}],
    "negotiate": [{"type": "talk_to_npc", "description": "관련자와 대화하라"}],
    "bond": [{"type": "talk_to_npc", "description": "대상과 교류하라"}],
    "rivalry": [{"type": "resolve_check", "description": "위협에 대응하라"}],
}
```

---

## 13. 전체 흐름 예시

### 13.1 대화 퀘스트 전체 흐름 (Tier 2 예시)

```
턴 42: PC가 대장장이 한스와 대화 시작
  → Python: 5% 확률 판정 → 성공!
  → 티어 판정: Tier 2 (중) — 속사정 있는 이야기
  → QuestSeed 생성 (tier: 2, type: personal, ttl: 15, tags: [missing_person, family])
  → LLM 프롬프트에 quest_seed 플래그 + tier 2 지시 추가
    ("1~2개 복선을 설치하라. 표면 아래 더 큰 이야기가 있음을 암시하라.")

한스: "요즘 걱정이 많아... 사촌 프리츠가 이틀 전 동쪽 산에 갔는데 소식이 없어.
       그런데 이상한 건, 요즘 동쪽 산에서 이상한 불빛이 보인다는 소문이 있거든..."
       (← Tier 2이므로 복선 1개 설치: "이상한 불빛")

PC: "내가 찾아볼까?"
  → LLM META: quest_seed_response: "accepted"
  → Python: 퀘스트 활성화
    → Quest 생성 (tier: 2, type: investigate, urgency: urgent, time_limit: 20)
    → L4 오버레이 생성 (target_nodes: [동쪽 산 노드들])
    → EventBus: quest_activated 발행

턴 50: 동쪽 산에서 고블린 야영지 발견
  → PC: "고블린이 쓰는 무기를 관찰한다"
  → READ 판정 → Success → "독 공리(Poison Axiom, Domain: Organic)"
  → PC: "유기물 도메인이면... 화염으로 정화할 수 있겠는데?"
  → LLM: axiom_exploit 접근으로 해석
  → EXEC 판정 + 공리 카운터 보너스 → 고블린 제압

턴 55: 프리츠 구출, 퀘스트 완료
  → result: "success"
  → 체이닝 판정: Tier 2이므로 50% → 성공!
  → 복선 활용: "이상한 불빛" → 후속 퀘스트 시드
  → chain_id: "chain_eastern_mountain"
  → 후속: "동쪽 산의 불빛" 퀘스트 (고블린이 피해온 드래곤 관련)
```

### 13.2 시드 만료 흐름

```
턴 42: 시드 생성 (tier: 2, ttl: 15)
턴 42~56: PC가 시드 무시, 다른 지역 탐험
턴 57: 시드 TTL 만료
  → seed.status = "expired"
  → seed.expiry_result = "victim_found_dead"
  → NPC 기억에 기록: "cousin_fritz_died"

턴 70: PC가 한스와 다시 대화
  → LLM 컨텍스트에 만료 시드 포함
  → 한스: "프리츠가... 시체로 발견됐다네. 산적에게 당한 것 같아."
  → 만료 결과가 새로운 시드 가능 (복수 퀘스트)
    → Python: 5% 판정 → 새 시드 발생 시 "avenge_cousin" 태그
    → 이전 시드가 Tier 2였으므로 복선("이상한 불빛")은 NPC 기억에 남아 있음
      → 후속 시드에서 재활용 가능
```

### 13.3 Tier 3 (소) 단발 퀘스트 예시

```
턴 80: 마을 입구에서 NPC와 대화
  → 시드 발생 (5%) → Tier 3 (소)
  → NPC: "아까 행상인이 다리에서 떨어졌다던데, 아직 못 올라왔을걸?"
  
PC: "가서 끌어올려줄게"
  → Quest 생성 (tier: 3, type: fetch, urgency: urgent, time_limit: 5)
  → EXEC 판정 → 행상인 구출 → success
  → 보상: 행상인이 할인 제공, affinity +5
  → 체이닝 판정: Tier 3이므로 10% → 실패 → 단독 완결
```

---

## 14. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-08 | 최초 작성 |
