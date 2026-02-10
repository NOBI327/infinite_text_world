# 구현 지시서 #07: models_v2.py (Phase 2 DB 모델)

**목적**: db-schema-v2.md에 정의된 15개 신규 테이블의 SQLAlchemy ORM 모델 구현  
**산출물**: `src/db/models_v2.py` + `src/db/models.py` 수정 + 테스트  
**예상 시간**: 30분  
**선행 조건**: 지시서 #00~#06 실행 완료

---

## 참조 문서 (반드시 읽을 것)

| 문서 | 경로 | 참조 내용 |
|------|------|-----------|
| DB 스키마 v2 | `docs/30_technical/db-schema-v2.md` | 전체 테이블 DDL, JSON 필드, 인덱스, 마이그레이션 순서 |
| 기존 모델 | `src/db/models.py` | Base, 기존 테이블, 컨벤션 확인 |
| DB 설정 | `src/db/database.py` | engine, SessionLocal, Base 위치 확인 |

---

## 작업 1: players.currency 컬럼 추가

**파일**: `src/db/models.py`

PlayerModel에 `currency` 컬럼을 추가한다.

```python
# PlayerModel 클래스 내부, 기존 컬럼 뒤에 추가
currency = Column(Integer, default=0)
```

**확인**: 기존 테스트가 깨지지 않는지 `pytest tests/` 실행하여 확인.

---

## 작업 2: models_v2.py 생성

**파일**: `src/db/models_v2.py`

### 2.1 파일 구조

```python
"""
ITW Phase 2 DB Models (NPC/관계/퀘스트/대화/아이템)

설계 문서: docs/30_technical/db-schema-v2.md
TODO: src/modules/ 모듈별 분리 (ModuleManager + 최소 2개 모듈 동작 시)
"""
from sqlalchemy import (
    Column, Text, Integer, Real, Boolean, LargeBinary,
    ForeignKey, UniqueConstraint, Index,
)
from src.db.database import Base
```

### 2.2 모델 정의 순서

db-schema-v2.md 섹션 9.2 마이그레이션 순서를 따른다:

```
1단계 (의존 없음):
  - ItemPrototypeModel
  - QuestChainModel

2단계 (v1 테이블 의존):
  - BackgroundSlotModel
  - BackgroundEntityModel
  - NPCModel

3단계 (npcs 의존):
  - NPCMemoryModel
  - RelationshipModel
  - QuestSeedModel
  - WorldPoolModel

4단계 (quests 의존):
  - QuestModel
  - QuestObjectiveModel
  - QuestChainEligibleModel
  - QuestUnresolvedThreadModel

5단계 (npcs + quests 의존):
  - DialogueSessionModel
  - DialogueTurnModel
  - ItemInstanceModel
```

### 2.3 모델 구현 규칙

1. **테이블명**: `__tablename__`은 db-schema-v2.md의 SQL DDL과 정확히 일치
2. **PK**: TEXT PK는 `Column(Text, primary_key=True)`, AUTOINCREMENT PK는 `Column(Integer, primary_key=True, autoincrement=True)`
3. **FK**: `ForeignKey("테이블명.컬럼명")` 형태. `ON DELETE CASCADE`는 `ForeignKey(..., ondelete="CASCADE")`
4. **DEFAULT**: SQL 기본값을 SQLAlchemy `default=` 또는 `server_default=`로 변환
   - `DEFAULT 0` → `default=0`
   - `DEFAULT FALSE` → `default=False`
   - `DEFAULT '{}'` → `default="{}"`
   - `DEFAULT '[]'` → `default="[]"`
   - `DEFAULT (datetime('now'))` → `server_default=text("datetime('now')")`
     - `from sqlalchemy import text` 필요
5. **JSON 필드**: 전부 `Column(Text)`. Python 파싱은 서비스 레이어에서 처리
6. **BLOB**: `Column(LargeBinary)` (npc_memories.embedding)
7. **REAL**: `Column(Real)` (Float가 아닌 Real — SQLite 친화적)
8. **UNIQUE 제약**: `UniqueConstraint`로 테이블 레벨에 선언
9. **인덱스**: `Index("인덱스명", 컬럼1, 컬럼2)` — db-schema-v2.md에 정의된 것만 생성
10. **relationship() 금지**: 이 단계에서는 SQLAlchemy `relationship()`을 사용하지 않는다. 모듈 분리 시 추가 예정

### 2.4 모델 예시 (BackgroundEntityModel)

db-schema-v2.md의 DDL을 그대로 옮기면 된다. 아래를 참고만 하고, **실제 DDL은 반드시 db-schema-v2.md에서 확인**할 것:

```python
class BackgroundEntityModel(Base):
    __tablename__ = "background_entities"

    entity_id = Column(Text, primary_key=True)
    entity_type = Column(Text, nullable=False)

    # 위치
    current_node = Column(Text, nullable=False)
    home_node = Column(Text)

    # 역할/외형
    role = Column(Text, nullable=False)
    appearance_seed = Column(Text, nullable=False, default="{}")

    # 승격
    promotion_score = Column(Integer, nullable=False, default=0)
    promoted = Column(Boolean, nullable=False, default=False)
    promoted_npc_id = Column(Text, ForeignKey("npcs.npc_id"))

    # 전투 추적
    temp_combat_id = Column(Text)

    # 이름/슬롯
    name_seed = Column(Text)
    slot_id = Column(Text, ForeignKey("background_slots.slot_id"))

    created_turn = Column(Integer, nullable=False, default=0)
    updated_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_bg_entity_node", "current_node"),
        Index("idx_bg_entity_type", "entity_type"),
    )
```

### 2.5 전체 모델 목록 (15개)

아래 모델을 **전부** 구현한다. 각 모델의 DDL은 db-schema-v2.md의 해당 섹션을 참조:

| 모델 클래스명 | 테이블명 | DDL 위치 |
|-------------|---------|---------|
| `ItemPrototypeModel` | `item_prototypes` | 섹션 6.1 |
| `QuestChainModel` | `quest_chains` | 섹션 4.4 |
| `BackgroundSlotModel` | `background_slots` | 섹션 2.2 |
| `BackgroundEntityModel` | `background_entities` | 섹션 2.1 |
| `NPCModel` | `npcs` | 섹션 2.3 |
| `NPCMemoryModel` | `npc_memories` | 섹션 2.4 |
| `RelationshipModel` | `relationships` | 섹션 3.1 |
| `QuestSeedModel` | `quest_seeds` | 섹션 4.1 |
| `WorldPoolModel` | `world_pool` | 섹션 2.5 |
| `QuestModel` | `quests` | 섹션 4.2 |
| `QuestObjectiveModel` | `quest_objectives` | 섹션 4.3 |
| `QuestChainEligibleModel` | `quest_chain_eligible` | 섹션 4.5 |
| `QuestUnresolvedThreadModel` | `quest_unresolved_threads` | 섹션 4.6 |
| `DialogueSessionModel` | `dialogue_sessions` | 섹션 5.1 |
| `DialogueTurnModel` | `dialogue_turns` | 섹션 5.2 |
| `ItemInstanceModel` | `item_instances` | 섹션 6.2 |

---

## 작업 3: DB 초기화에 models_v2 등록

**파일**: `src/main.py`

`lifespan` 함수 내 `Base.metadata.create_all()` 호출 전에 models_v2를 import하여 Base에 등록되도록 한다:

```python
import src.db.models  # noqa: F401 — 기존
import src.db.models_v2  # noqa: F401 — 추가
```

> `Base.metadata.create_all()`은 import된 모든 모델의 테이블을 생성하므로, import만 하면 된다.

---

## 작업 4: 테스트

**파일**: `tests/test_models_v2.py`

### 4.1 테이블 생성 테스트

모든 16개 테이블(v2 15개 + players.currency)이 정상 생성되는지 확인:

```python
"""models_v2 테이블 생성 및 기본 CRUD 테스트"""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from src.db.database import Base
import src.db.models  # noqa: F401
import src.db.models_v2  # noqa: F401


@pytest.fixture
def db_session():
    """인메모리 SQLite 세션"""
    engine = create_engine("sqlite:///:memory:")
    # FK 활성화
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_all_v2_tables_created(db_session):
    """v2 테이블 15개가 전부 생성되는지 확인"""
    inspector = inspect(db_session.bind)
    tables = set(inspector.get_table_names())

    expected_v2 = {
        "background_entities", "background_slots", "npcs", "npc_memories",
        "world_pool", "relationships", "quest_seeds", "quests",
        "quest_objectives", "quest_chains", "quest_chain_eligible",
        "quest_unresolved_threads", "dialogue_sessions", "dialogue_turns",
        "item_prototypes", "item_instances",
    }
    assert expected_v2.issubset(tables), f"Missing tables: {expected_v2 - tables}"


def test_players_currency_column(db_session):
    """players 테이블에 currency 컬럼이 존재하는지 확인"""
    inspector = inspect(db_session.bind)
    columns = {col["name"] for col in inspector.get_columns("players")}
    assert "currency" in columns
```

### 4.2 기본 CRUD 테스트 (대표 3개 테이블)

전체 15개에 대해 일일이 CRUD를 작성하지 않고, 의존 관계 검증이 중요한 대표 3개만 작성:

```python
from src.db.models_v2 import (
    NPCModel, NPCMemoryModel, ItemPrototypeModel,
    ItemInstanceModel, RelationshipModel,
)


def test_npc_crud(db_session):
    """NPC 생성 및 조회"""
    npc = NPCModel(
        npc_id="npc_001",
        full_name='{"given": "Aldric", "family": "Voss"}',
        given_name="Aldric",
        hexaco='{"H": 0.6, "E": 0.4, "X": 0.5, "A": 0.7, "C": 0.3, "O": 0.8}',
        character_sheet='{}',
        resonance_shield='{}',
        current_node="3_5",
        origin_type="promoted",
        role="innkeeper",
    )
    db_session.add(npc)
    db_session.commit()

    loaded = db_session.query(NPCModel).filter_by(npc_id="npc_001").first()
    assert loaded is not None
    assert loaded.given_name == "Aldric"
    assert loaded.currency == 0  # default


def test_npc_memory_cascade_delete(db_session):
    """NPC 삭제 시 기억도 CASCADE 삭제"""
    npc = NPCModel(
        npc_id="npc_002", full_name='{}', given_name="Test",
        hexaco='{}', character_sheet='{}', resonance_shield='{}',
        current_node="1_1", origin_type="scripted", role="guard",
    )
    db_session.add(npc)
    db_session.flush()

    memory = NPCMemoryModel(
        memory_id="mem_001", npc_id="npc_002",
        tier=1, memory_type="encounter",
        summary="Met the player", turn_created=10,
    )
    db_session.add(memory)
    db_session.commit()

    db_session.delete(npc)
    db_session.commit()

    assert db_session.query(NPCMemoryModel).filter_by(memory_id="mem_001").first() is None


def test_item_prototype_and_instance(db_session):
    """아이템 원형 + 인스턴스 생성"""
    proto = ItemPrototypeModel(
        item_id="iron_sword",
        name_kr="철검",
        item_type="equipment",
        weight=2.5,
        base_value=100,
        max_durability=50,
    )
    db_session.add(proto)
    db_session.flush()

    instance = ItemInstanceModel(
        instance_id="inst_001",
        prototype_id="iron_sword",
        owner_type="player",
        owner_id="player_001",
        current_durability=50,
    )
    db_session.add(instance)
    db_session.commit()

    loaded = db_session.query(ItemInstanceModel).filter_by(instance_id="inst_001").first()
    assert loaded is not None
    assert loaded.prototype_id == "iron_sword"


def test_relationship_unique_constraint(db_session):
    """관계 UNIQUE 제약 검증"""
    rel1 = RelationshipModel(
        relationship_id="rel_001",
        source_type="player", source_id="p1",
        target_type="npc", target_id="npc_001",
    )
    rel2 = RelationshipModel(
        relationship_id="rel_002",
        source_type="player", source_id="p1",
        target_type="npc", target_id="npc_001",
    )
    db_session.add(rel1)
    db_session.commit()

    db_session.add(rel2)
    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()
```

### 4.3 인덱스 존재 확인 테스트

```python
def test_v2_indexes_exist(db_session):
    """주요 인덱스가 생성되었는지 확인"""
    inspector = inspect(db_session.bind)

    expected_indexes = {
        "background_entities": ["idx_bg_entity_node", "idx_bg_entity_type"],
        "npcs": ["idx_npc_node", "idx_npc_role"],
        "npc_memories": ["idx_memory_npc", "idx_memory_npc_tier"],
        "relationships": ["idx_rel_source", "idx_rel_target"],
        "quests": ["idx_quest_status", "idx_quest_chain", "idx_quest_npc"],
        "item_instances": ["idx_item_owner", "idx_item_proto"],
    }

    for table, idx_names in expected_indexes.items():
        actual = {idx["name"] for idx in inspector.get_indexes(table)}
        for idx_name in idx_names:
            assert idx_name in actual, f"Missing index {idx_name} on {table}"
```

---

## 작업 5: 검증

```bash
# 1. 린트
ruff check src/db/models_v2.py tests/test_models_v2.py

# 2. 기존 테스트 무파손 확인
pytest tests/ -v

# 3. 신규 테스트
pytest tests/test_models_v2.py -v

# 4. 커버리지 확인
pytest --cov=src/db --cov-report=term-missing tests/test_models_v2.py
```

---

## 작업 6: SRC_INDEX.md 갱신

`docs/SRC_INDEX.md`에 아래 항목 추가:

```markdown
### db/models_v2.py
- **목적:** Phase 2 SQLAlchemy ORM 모델 (NPC/관계/퀘스트/대화/아이템)
- **핵심:** 15개 신규 테이블 모델. db-schema-v2.md 대응.
- **TODO:** src/modules/ 모듈별 파일 분리 예정.
```

---

## 커밋

```bash
git add src/db/models.py src/db/models_v2.py src/main.py tests/test_models_v2.py docs/SRC_INDEX.md
git commit -m "feat: add Phase 2 DB models (models_v2.py) with 15 new tables

- NPC: background_entities, background_slots, npcs, npc_memories, world_pool
- Relationship: relationships
- Quest: quest_seeds, quests, quest_objectives, quest_chains, quest_chain_eligible, quest_unresolved_threads
- Dialogue: dialogue_sessions, dialogue_turns
- Item: item_prototypes, item_instances
- Add players.currency column to existing PlayerModel
- Register models_v2 in main.py lifespan
- Add tests for table creation, CRUD, cascade, indexes

Ref: docs/30_technical/db-schema-v2.md"
```

---

## 체크리스트

- [ ] `src/db/models.py` — PlayerModel에 `currency` 컬럼 추가
- [ ] `src/db/models_v2.py` — 15개 모델 전부 구현
- [ ] `src/main.py` — `import src.db.models_v2` 추가
- [ ] `tests/test_models_v2.py` — 테이블 생성 / CRUD / CASCADE / UNIQUE / 인덱스 테스트
- [ ] `ruff check` 통과
- [ ] `pytest` 전체 통과 (기존 247+ 신규)
- [ ] `docs/SRC_INDEX.md` 갱신
- [ ] 커밋 완료

---

## 주의사항

1. **db-schema-v2.md가 진실**: 이 지시서의 예시 코드와 DDL이 다르면, DDL을 따를 것
2. **relationship() 쓰지 말 것**: 모듈 분리 전까지 SQLAlchemy relationship은 사용하지 않는다
3. **server_default 주의**: `datetime('now')` 같은 SQL 함수는 반드시 `server_default=text(...)` 사용
4. **FK 순서 주의**: BackgroundEntityModel.promoted_npc_id → npcs.npc_id인데, 파일 내 정의 순서상 NPCModel이 뒤에 올 수 있음. SQLAlchemy는 문자열 FK(`"npcs.npc_id"`)로 해결되므로 순서 무관하지만, **마이그레이션 순서(2.2절)**대로 정의하는 것을 권장
5. **기존 테스트 깨뜨리지 말 것**: models.py 수정은 currency 추가 한 줄뿐
