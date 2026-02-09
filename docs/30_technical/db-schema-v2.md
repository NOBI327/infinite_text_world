# ITW 통합 DB 스키마 v2

**버전**: 1.0  
**작성일**: 2026-02-10  
**상태**: 확정  
**관련**: db-schema.md, npc-system.md, relationship-system.md, quest-system.md, dialogue-system.md, item-system.md

---

## 1. 개요

### 1.1 목적

Phase 2 모듈(NPC, 관계, 퀘스트, 대화, 아이템)의 DB 테이블을 통합 정의한다. 기존 db-schema.md(v1)의 테이블은 그대로 유지하고, 신규 테이블을 추가한다.

### 1.2 설계 원칙

- **SQLite 단일 파일**: 모든 테이블이 하나의 SQLite DB에 존재
- **JSON 필드 활용**: 가변 구조 데이터는 TEXT(JSON)로 저장, Python에서 파싱
- **인덱스 최소화**: 빈번한 조회 패턴에만 인덱스 추가
- **FK 참조 무결성**: SQLite PRAGMA foreign_keys=ON 전제. 단, 순환 참조가 불가피한 경우 application-level 참조
- **설계 문서 1:1 대응**: 각 테이블은 설계 문서의 데이터 모델에 대응

### 1.3 기존 v1 테이블 (변경 없음)

| 테이블 | 출처 | 비고 |
|--------|------|------|
| `map_nodes` | db-schema.md | 좌표/tier/axiom/sensory |
| `resources` | db-schema.md | MapNode 1:N |
| `echoes` | db-schema.md | MapNode 1:N |
| `players` | db-schema.md | 위치/스탯/인벤토리 |
| `sub_grid_nodes` | db-schema.md | L3 depth |

### 1.4 v1 테이블 변경 사항

#### players 테이블 확장

`src/db/models.py`의 PlayerModel에 직접 컬럼을 추가한다 (현재 운영 DB 없음):

```python
# PlayerModel에 추가
currency = Column(Integer, default=0)
```

> **⚠ TODO**: 출시(Phase 4) 또는 외부 테스터 참여 시점에서 Alembic 등 마이그레이션 도구를 도입할 것.
> 그 이후의 스키마 변경은 반드시 마이그레이션 스크립트를 통해 수행한다.

---

## 2. NPC 테이블군

출처: npc-system.md

### 2.1 background_entities

승격 전 배경 존재. 승격 시 npcs로 이동 후 삭제하지 않고 `promoted = TRUE`로 마킹.

```sql
CREATE TABLE background_entities (
    entity_id       TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,                  -- "resident" | "wanderer" | "hostile"
    
    -- 위치
    current_node    TEXT NOT NULL,
    home_node       TEXT,                            -- 거주형만
    
    -- 역할/외형
    role            TEXT NOT NULL,                   -- "innkeeper", "traveler", "goblin"
    appearance_seed TEXT NOT NULL DEFAULT '{}',      -- JSON: AI 서술용 시드
    
    -- 승격
    promotion_score INTEGER NOT NULL DEFAULT 0,
    promoted        BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE면 npcs에 레코드 존재
    promoted_npc_id TEXT,                            -- FK → npcs.npc_id (승격 후)
    
    -- 전투 추적 (적대형)
    temp_combat_id  TEXT,
    
    -- 이름 시드
    name_seed       TEXT,                            -- JSON: NPCNameSeed
    
    -- 슬롯 (거주형)
    slot_id         TEXT,                            -- FK → background_slots.slot_id
    
    created_turn    INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_bg_entity_node ON background_entities(current_node);
CREATE INDEX idx_bg_entity_type ON background_entities(entity_type);
```

### 2.2 background_slots

거주형 배경인물의 시설 슬롯.

```sql
CREATE TABLE background_slots (
    slot_id         TEXT PRIMARY KEY,
    node_id         TEXT NOT NULL,
    facility_id     TEXT NOT NULL,
    facility_type   TEXT NOT NULL,                   -- "inn", "smithy", "market", ...
    
    -- 역할
    role            TEXT NOT NULL,                   -- "innkeeper", "patron", "servant"
    is_required     BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 현재 배치
    entity_id       TEXT,                            -- FK → background_entities.entity_id
    
    -- 리셋 관리
    reset_interval  INTEGER NOT NULL DEFAULT 24,
    last_reset_turn INTEGER NOT NULL DEFAULT 0,
    
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_slot_node ON background_slots(node_id);
CREATE INDEX idx_slot_facility ON background_slots(facility_id);
```

### 2.3 npcs

승격 완료된 NPC. npc-system.md 섹션 13 NPC 완전 데이터 모델 대응.

```sql
CREATE TABLE npcs (
    npc_id              TEXT PRIMARY KEY,
    
    -- 명칭 (NPCFullName 직렬화)
    full_name           TEXT NOT NULL,               -- JSON: NPCFullName 전체
    given_name          TEXT NOT NULL,               -- 검색용 단축 이름
    
    -- 성격
    hexaco              TEXT NOT NULL,               -- JSON: {"H": 0.6, "E": 0.4, ...}
    
    -- 능력치
    character_sheet     TEXT NOT NULL,               -- JSON: CharacterSheet
    resonance_shield    TEXT NOT NULL,               -- JSON: ResonanceShield
    axiom_proficiencies TEXT NOT NULL DEFAULT '{}',  -- JSON: {"Ignis": 45, "Ferrum": 60}
    
    -- 위치
    home_node           TEXT,
    current_node        TEXT NOT NULL,
    
    -- 자율 행동
    routine             TEXT,                        -- JSON: DailyRoutine (Phase A)
    state               TEXT NOT NULL DEFAULT '{}',  -- JSON: NPCState (욕구 등)
    
    -- 소속
    lord_id             TEXT,                        -- FK → npcs.npc_id (자기 참조)
    faction_id          TEXT,
    loyalty             REAL NOT NULL DEFAULT 0.5,
    
    -- 경제
    currency            INTEGER NOT NULL DEFAULT 0,
    
    -- 메타
    origin_type         TEXT NOT NULL,               -- "promoted" | "scripted"
    origin_entity_type  TEXT,                        -- "resident" | "wanderer" | "hostile"
    role                TEXT NOT NULL,               -- 직업 역할
    tags                TEXT NOT NULL DEFAULT '[]',  -- JSON: 검색용 태그
    
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_interaction_turn INTEGER
);

CREATE INDEX idx_npc_node ON npcs(current_node);
CREATE INDEX idx_npc_role ON npcs(role);
```

### 2.4 npc_memories

NPC 기억 3계층. npc-system.md 섹션 10.

```sql
CREATE TABLE npc_memories (
    memory_id           TEXT PRIMARY KEY,
    npc_id              TEXT NOT NULL,               -- FK → npcs.npc_id
    
    -- 계층
    tier                INTEGER NOT NULL,            -- 1, 2, 3
    
    -- 내용
    memory_type         TEXT NOT NULL,               -- "encounter" | "trade" | "combat" | "quest" | "betrayal" | "favor"
    summary             TEXT NOT NULL,               -- 1-2문장 요약
    
    -- 감정/중요도
    emotional_valence   REAL NOT NULL DEFAULT 0.0,   -- -1.0 ~ +1.0
    importance          REAL NOT NULL DEFAULT 0.0,   -- 0.0 ~ 1.0
    
    -- 벡터 검색용 (Tier 3)
    embedding           BLOB,                        -- float32 배열 직렬화
    
    -- Tier 1 고정
    is_fixed            BOOLEAN NOT NULL DEFAULT FALSE,
    fixed_slot          INTEGER,                     -- 1 또는 2
    
    -- 메타
    turn_created        INTEGER NOT NULL,
    related_node        TEXT,
    related_entity_id   TEXT,                        -- 관련 player/npc ID
    source_session_id   TEXT,                        -- FK → dialogue_sessions.session_id (대화 기억 시)

    FOREIGN KEY (npc_id) REFERENCES npcs(npc_id) ON DELETE CASCADE
);

CREATE INDEX idx_memory_npc ON npc_memories(npc_id);
CREATE INDEX idx_memory_npc_tier ON npc_memories(npc_id, tier);
```

### 2.5 world_pool

유랑형/적대형 재조우 풀. npc-system.md 섹션 6.

```sql
CREATE TABLE world_pool (
    entity_id       TEXT PRIMARY KEY,               -- FK → background_entities.entity_id
    entity_type     TEXT NOT NULL,                   -- "wanderer" | "hostile"
    promotion_score INTEGER NOT NULL,
    last_known_node TEXT NOT NULL,
    registered_turn INTEGER NOT NULL,
    
    FOREIGN KEY (entity_id) REFERENCES background_entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX idx_wp_type ON world_pool(entity_type);
```

---

## 3. 관계 테이블

출처: relationship-system.md

### 3.1 relationships

PC-NPC 및 NPC-NPC 관계. relationship-system.md 섹션 9.1.

```sql
CREATE TABLE relationships (
    relationship_id     TEXT PRIMARY KEY,
    
    -- 방향: source → target
    source_type         TEXT NOT NULL,               -- "player" | "npc"
    source_id           TEXT NOT NULL,
    target_type         TEXT NOT NULL,               -- "player" | "npc"
    target_id           TEXT NOT NULL,
    
    -- 3축 수치
    affinity            REAL NOT NULL DEFAULT 0.0,   -- -100 ~ +100
    trust               REAL NOT NULL DEFAULT 0.0,   -- 0 ~ 100
    familiarity         INTEGER NOT NULL DEFAULT 0,  -- 0 ~ ∞
    
    -- 상태
    status              TEXT NOT NULL DEFAULT 'stranger',  -- RelationshipStatus enum
    tags                TEXT NOT NULL DEFAULT '[]',  -- JSON: ["debt_owed", "saved_life"]
    
    -- 메타
    last_interaction_turn INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(source_type, source_id, target_type, target_id)
);

CREATE INDEX idx_rel_source ON relationships(source_type, source_id);
CREATE INDEX idx_rel_target ON relationships(target_type, target_id);
```

---

## 4. 퀘스트 테이블군

출처: quest-system.md

### 4.1 quest_seeds

퀘스트 시드(떡밥). quest-system.md 섹션 2.3.

```sql
CREATE TABLE quest_seeds (
    seed_id         TEXT PRIMARY KEY,
    npc_id          TEXT NOT NULL,                   -- FK → npcs.npc_id
    
    seed_type       TEXT NOT NULL,                   -- "personal" | "rumor" | "request" | "warning"
    seed_tier       INTEGER NOT NULL,                -- 1(대) | 2(중) | 3(소)
    
    created_turn    INTEGER NOT NULL,
    ttl_turns       INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- "active" | "accepted" | "expired" | "resolved_offscreen"
    
    context_tags    TEXT NOT NULL DEFAULT '[]',      -- JSON: ["missing_person", "family"]
    expiry_result   TEXT,                            -- 만료 시 결과 태그
    
    -- 체이닝
    chain_id        TEXT,                            -- FK → quest_chains.chain_id (연작 시드)
    
    -- 대화 쿨다운 추적
    conversation_count_at_creation INTEGER NOT NULL DEFAULT 0,
    
    FOREIGN KEY (npc_id) REFERENCES npcs(npc_id)
);

CREATE INDEX idx_seed_npc ON quest_seeds(npc_id);
CREATE INDEX idx_seed_status ON quest_seeds(status);
```

### 4.2 quests

활성/완료 퀘스트. quest-system.md 섹션 3.1.

```sql
CREATE TABLE quests (
    quest_id            TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    
    -- 출처
    origin_type         TEXT NOT NULL,               -- "conversation" | "environment"
    origin_npc_id       TEXT,                        -- FK → npcs.npc_id
    origin_seed_id      TEXT,                        -- FK → quest_seeds.seed_id
    origin_overlay_id   TEXT,
    
    -- 유형
    quest_type          TEXT NOT NULL,               -- "fetch" | "deliver" | "escort" | "investigate" | "resolve" | "negotiate" | "bond" | "rivalry"
    seed_tier           INTEGER NOT NULL,            -- 1 | 2 | 3
    urgency             TEXT NOT NULL DEFAULT 'normal', -- "normal" | "urgent"
    time_limit          INTEGER,                     -- urgent일 때만
    
    -- 상태
    status              TEXT NOT NULL DEFAULT 'active', -- "active" | "completed" | "failed" | "abandoned"
    result              TEXT,                        -- "success" | "partial" | "failure" | "abandoned"
    activated_turn      INTEGER NOT NULL,
    completed_turn      INTEGER,
    
    -- 체이닝
    chain_id            TEXT,                        -- FK → quest_chains.chain_id
    chain_index         INTEGER NOT NULL DEFAULT 0,
    is_chain_finale     BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- 관련 엔티티
    related_npc_ids     TEXT NOT NULL DEFAULT '[]',  -- JSON: ["npc_id_1", "npc_id_2"]
    target_node_ids     TEXT NOT NULL DEFAULT '[]',  -- JSON: ["3_5", "5_8"]
    overlay_id          TEXT,
    
    -- 해결 기록
    resolution_method       TEXT,
    resolution_comment      TEXT,
    resolution_method_tag   TEXT,
    resolution_impression_tag TEXT,
    
    -- 보상
    rewards             TEXT,                        -- JSON: QuestRewards 직렬화
    
    -- 메타
    tags                TEXT NOT NULL DEFAULT '[]',  -- JSON
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_quest_status ON quests(status);
CREATE INDEX idx_quest_chain ON quests(chain_id);
CREATE INDEX idx_quest_npc ON quests(origin_npc_id);
```

### 4.3 quest_objectives

퀘스트 목표. quest-system.md 섹션 12.2.

```sql
CREATE TABLE quest_objectives (
    objective_id    TEXT PRIMARY KEY,
    quest_id        TEXT NOT NULL,                   -- FK → quests.quest_id
    
    description     TEXT NOT NULL,
    objective_type  TEXT NOT NULL,                   -- "reach_node" | "find_item" | "talk_to_npc" | "resolve_check"
    target          TEXT NOT NULL DEFAULT '{}',      -- JSON: {"node_id": "3_5"} 등
    
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    completed_turn  INTEGER,
    
    FOREIGN KEY (quest_id) REFERENCES quests(quest_id) ON DELETE CASCADE
);

CREATE INDEX idx_objective_quest ON quest_objectives(quest_id);
```

### 4.4 quest_chains

연작 퀘스트 체인. quest-system.md 섹션 5.

```sql
CREATE TABLE quest_chains (
    chain_id        TEXT PRIMARY KEY,
    created_turn    INTEGER NOT NULL,
    finalized       BOOLEAN NOT NULL DEFAULT FALSE,
    total_quests    INTEGER NOT NULL DEFAULT 0,
    
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 4.5 quest_chain_eligible

연작 가능 NPC. quest-system.md 섹션 5.3.

```sql
CREATE TABLE quest_chain_eligible (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id        TEXT NOT NULL,                   -- FK → quests.quest_id
    
    npc_ref         TEXT NOT NULL,                   -- 실제 npc_id 또는 role 태그
    ref_type        TEXT NOT NULL,                   -- "existing" | "unborn"
    node_hint       TEXT,                            -- unborn일 때 예상 위치
    reason          TEXT NOT NULL,                   -- "quest_giver" | "witness" | "antagonist" | "foreshadowed"
    
    -- unborn 매칭 결과
    matched_npc_id  TEXT,                            -- 매칭된 실제 npc_id
    matched_turn    INTEGER,
    
    FOREIGN KEY (quest_id) REFERENCES quests(quest_id) ON DELETE CASCADE
);

CREATE INDEX idx_chain_eligible_quest ON quest_chain_eligible(quest_id);
CREATE INDEX idx_chain_eligible_ref ON quest_chain_eligible(ref_type, npc_ref);
```

### 4.6 quest_unresolved_threads

미해결 복선 태그. quest-system.md 섹션 5.

```sql
CREATE TABLE quest_unresolved_threads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id        TEXT,                            -- FK → quests.quest_id (or chain-level)
    chain_id        TEXT,                            -- FK → quest_chains.chain_id
    
    thread_tag      TEXT NOT NULL,                   -- "strange_lights_eastern_mountain"
    created_turn    INTEGER NOT NULL,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_turn   INTEGER,
    
    FOREIGN KEY (quest_id) REFERENCES quests(quest_id) ON DELETE SET NULL,
    FOREIGN KEY (chain_id) REFERENCES quest_chains(chain_id) ON DELETE SET NULL
);

CREATE INDEX idx_thread_chain ON quest_unresolved_threads(chain_id);
```

---

## 5. 대화 테이블군

출처: dialogue-system.md

### 5.1 dialogue_sessions

대화 세션 이력. dialogue-system.md 섹션 9.3.

```sql
CREATE TABLE dialogue_sessions (
    session_id          TEXT PRIMARY KEY,
    player_id           TEXT NOT NULL,               -- FK → players.id
    npc_id              TEXT NOT NULL,               -- FK → npcs.npc_id
    node_id             TEXT NOT NULL,
    
    -- 예산
    budget_total        INTEGER NOT NULL,
    
    -- 상태
    status              TEXT NOT NULL DEFAULT 'active',  -- "active" | "ended_by_pc" | "ended_by_npc" | "ended_by_budget" | "ended_by_system"
    started_turn        INTEGER NOT NULL,
    ended_turn          INTEGER,
    dialogue_turn_count INTEGER NOT NULL DEFAULT 0,
    
    -- 시드
    seed_id             TEXT,                        -- FK → quest_seeds.seed_id
    seed_result         TEXT,                        -- "accepted" | "ignored" | null
    
    -- 누적 결과
    total_affinity_delta REAL NOT NULL DEFAULT 0.0,
    
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_session_player ON dialogue_sessions(player_id);
CREATE INDEX idx_session_npc ON dialogue_sessions(npc_id);
```

### 5.2 dialogue_turns

대화 턴 이력. 디버그/분석용. dialogue-system.md 섹션 9.3.

```sql
CREATE TABLE dialogue_turns (
    turn_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,                   -- FK → dialogue_sessions.session_id
    turn_index      INTEGER NOT NULL,
    
    pc_input        TEXT NOT NULL,
    npc_narrative   TEXT NOT NULL,
    raw_meta        TEXT NOT NULL DEFAULT '{}',      -- JSON: LLM 원본 META
    validated_meta  TEXT NOT NULL DEFAULT '{}',      -- JSON: Python 검증 후 META
    
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (session_id) REFERENCES dialogue_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_turn_session ON dialogue_turns(session_id);
```

---

## 6. 아이템 테이블군

출처: item-system.md

### 6.1 item_prototypes

아이템 원형. item-system.md 섹션 11.1.

```sql
CREATE TABLE item_prototypes (
    item_id             TEXT PRIMARY KEY,
    name_kr             TEXT NOT NULL,
    item_type           TEXT NOT NULL,               -- "equipment" | "consumable" | "material" | "misc"
    
    -- 물리
    weight              REAL NOT NULL DEFAULT 0.0,
    bulk                INTEGER NOT NULL DEFAULT 1,
    base_value          INTEGER NOT NULL DEFAULT 0,
    
    -- 재질 & 공리
    primary_material    TEXT NOT NULL DEFAULT '',
    axiom_tags          TEXT NOT NULL DEFAULT '{}',  -- JSON: {"Ignis": 1, "Lux": 2}
    
    -- 내구도
    max_durability      INTEGER NOT NULL DEFAULT 0,  -- 0 = 파괴 불가
    durability_loss_per_use INTEGER NOT NULL DEFAULT 0,
    broken_result       TEXT,                        -- FK → item_prototypes.item_id (파괴 시 변환)
    
    -- 용기
    container_capacity  INTEGER NOT NULL DEFAULT 0,
    
    -- 서술 & 검색
    flavor_text         TEXT NOT NULL DEFAULT '',
    tags                TEXT NOT NULL DEFAULT '[]',  -- JSON: ["flammable", "fragile"]
    
    -- 동적 생성 여부
    is_dynamic          BOOLEAN NOT NULL DEFAULT FALSE
);
```

### 6.2 item_instances

아이템 개체. item-system.md 섹션 11.2.

```sql
CREATE TABLE item_instances (
    instance_id         TEXT PRIMARY KEY,
    prototype_id        TEXT NOT NULL,               -- FK → item_prototypes.item_id
    
    -- 위치
    owner_type          TEXT NOT NULL,               -- "player" | "npc" | "node" | "container"
    owner_id            TEXT NOT NULL,
    
    -- 상태
    current_durability  INTEGER NOT NULL,
    state_tags          TEXT NOT NULL DEFAULT '[]',  -- JSON: ["wet", "rusty"]
    
    -- 메타
    acquired_turn       INTEGER NOT NULL DEFAULT 0,
    custom_name         TEXT,
    
    FOREIGN KEY (prototype_id) REFERENCES item_prototypes(item_id)
);

CREATE INDEX idx_item_owner ON item_instances(owner_type, owner_id);
CREATE INDEX idx_item_proto ON item_instances(prototype_id);
```

---

## 7. 테이블 관계도

```
players ─────────────┐
    │                │
    │ 1:N            │ 1:N
    ▼                ▼
dialogue_sessions   relationships (source)
    │ 1:N               │
    ▼                   │
dialogue_turns          │
                        │
npcs ───────────────────┘
    │                ▲
    │ 1:N            │ promoted_npc_id
    ├─► npc_memories │
    │                background_entities
    │ 1:N               │
    ├─► relationships   ├─► background_slots
    │   (target)        │
    │ 1:N               └─► world_pool
    ├─► quest_seeds
    │       │
    │       ▼
    │   quests ─────────► quest_chains
    │       │ 1:N           │
    │       ├─► quest_objectives
    │       ├─► quest_chain_eligible
    │       └─► quest_unresolved_threads
    │
    │ N:N (owner)
    └─► item_instances ─► item_prototypes
```

---

## 8. JSON 필드 스키마 요약

구현 시 Python 측에서 TypedDict 또는 Pydantic 모델로 파싱/검증할 JSON 필드 목록.

| 테이블 | 컬럼 | 스키마 | 출처 |
|--------|------|--------|------|
| `npcs` | `full_name` | NPCFullName | npc-system 7.2 |
| `npcs` | `hexaco` | `{"H": float, "E": float, ...}` | npc-system 8.1 |
| `npcs` | `character_sheet` | CharacterSheet | core_rule.py |
| `npcs` | `resonance_shield` | ResonanceShield | npc-system 11.2 |
| `npcs` | `axiom_proficiencies` | `{axiom_name: int}` | npc-system 11.3 |
| `npcs` | `routine` | DailyRoutine | npc-system 12.4 |
| `npcs` | `state` | NPCState (욕구 등) | npc-system 12.2 |
| `background_entities` | `appearance_seed` | 자유 형식 dict | npc-system 2.2 |
| `background_entities` | `name_seed` | NPCNameSeed | npc-system 7.1 |
| `relationships` | `tags` | `list[str]` | relationship 9.1 |
| `quest_seeds` | `context_tags` | `list[str]` | quest 2.3 |
| `quests` | `related_npc_ids` | `list[str]` | quest 3.1 |
| `quests` | `target_node_ids` | `list[str]` | quest 3.1 |
| `quests` | `rewards` | QuestRewards | quest 4.1 |
| `quests` | `tags` | `list[str]` | quest 3.1 |
| `quest_objectives` | `target` | `{"node_id": str}` 등 | quest 12.2 |
| `dialogue_turns` | `raw_meta` | META JSON (dialogue 4.2) | dialogue 4.2 |
| `dialogue_turns` | `validated_meta` | META JSON | dialogue 4.2 |
| `item_prototypes` | `axiom_tags` | `{tag: int}` | item 2.1 |
| `item_prototypes` | `tags` | `list[str]` | item 2.1 |
| `item_instances` | `state_tags` | `list[str]` | item 2.2 |

---

## 9. 마이그레이션 전략

### 9.1 원칙

- v1 테이블은 변경하지 않는다 (players.currency 추가 제외)
- v2 테이블은 전부 신규 CREATE
- 모듈별 독립 마이그레이션 가능 (NPC 없이 Item만 먼저 등)

### 9.2 마이그레이션 순서

의존 관계에 따른 테이블 생성 순서:

```
1단계 (의존 없음):
    item_prototypes
    quest_chains

2단계 (v1 테이블 의존):
    background_slots
    background_entities
    npcs
    players.currency 컬럼 추가 (models.py 직접 수정)

3단계 (npcs 의존):
    npc_memories
    relationships
    quest_seeds
    world_pool

4단계 (quests 의존):
    quests
    quest_objectives
    quest_chain_eligible
    quest_unresolved_threads

5단계 (npcs + quests 의존):
    dialogue_sessions
    dialogue_turns
    item_instances
```

### 9.3 SQLAlchemy 모델 위치

```
src/db/models.py          ← 기존 v1 모델 (players.currency 추가)
src/db/models_v2.py       ← 신규 v2 모델 전체
```

> **⚠ TODO**: `src/modules/` 구조가 구현되면(지시서 #01~#04 완료 후), models_v2.py를 모듈별 파일로 분리할 것:
> `npc_models.py`, `relationship_models.py`, `quest_models.py`, `dialogue_models.py`, `item_models.py`.
> 분리 시점: ModuleManager + 최소 2개 모듈이 동작할 때.

---

## 10. 인덱스 전략

### 10.1 빈번한 조회 패턴

| 패턴 | 쿼리 | 인덱스 |
|------|------|--------|
| 노드의 NPC 목록 | `WHERE current_node = ?` | `idx_npc_node` |
| 노드의 배경 존재 | `WHERE current_node = ?` | `idx_bg_entity_node` |
| NPC 기억 조회 | `WHERE npc_id = ? AND tier = ?` | `idx_memory_npc_tier` |
| PC-NPC 관계 조회 | `WHERE source_type = ? AND source_id = ? AND target_id = ?` | UNIQUE 제약 |
| 활성 퀘스트 목록 | `WHERE status = 'active'` | `idx_quest_status` |
| NPC 인벤토리 | `WHERE owner_type = 'npc' AND owner_id = ?` | `idx_item_owner` |
| 선반 아이템 | `WHERE owner_type = 'container' AND owner_id = ?` | `idx_item_owner` |
| 활성 시드 목록 | `WHERE status = 'active'` | `idx_seed_status` |
| 체이닝 후보 검색 | `WHERE ref_type = 'unborn' AND npc_ref = ?` | `idx_chain_eligible_ref` |

### 10.2 조회 성능 참고

SQLite 특성상 테이블당 수천 행 수준에서는 인덱스 효과가 미미하다. 현재 인덱스는 향후 데이터 증가에 대비한 설계이며, Phase 2 알파 테스트 수준에서는 성능 병목이 되지 않는다.

---

## 11. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2026-02-10 | 최초 작성: NPC/관계/퀘스트/대화/아이템 통합 스키마 |
