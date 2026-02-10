"""Phase 2 DB Models 테스트

models_v2.py의 16개 테이블 생성, CRUD, CASCADE, UNIQUE, 인덱스를 검증한다.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, PlayerModel
from src.db.models_v2 import (
    BackgroundEntityModel,
    BackgroundSlotModel,
    DialogueSessionModel,
    DialogueTurnModel,
    ItemInstanceModel,
    ItemPrototypeModel,
    NPCMemoryModel,
    NPCModel,
    QuestChainEligibleModel,
    QuestChainModel,
    QuestModel,
    QuestObjectiveModel,
    QuestSeedModel,
    QuestUnresolvedThreadModel,
    RelationshipModel,
    WorldPoolModel,
)


@pytest.fixture()
def db_session():
    """인메모리 SQLite 세션 (테스트마다 초기화)"""
    engine = create_engine("sqlite:///:memory:")
    # FK 활성화
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


# ── 테이블 생성 검증 ──────────────────────────────────────


V2_TABLE_NAMES = [
    "item_prototypes",
    "quest_chains",
    "background_slots",
    "background_entities",
    "npcs",
    "npc_memories",
    "relationships",
    "quest_seeds",
    "world_pool",
    "quests",
    "quest_objectives",
    "quest_chain_eligible",
    "quest_unresolved_threads",
    "dialogue_sessions",
    "dialogue_turns",
    "item_instances",
]


class TestTableCreation:
    def test_all_v2_tables_exist(self, db_session: Session):
        inspector = inspect(db_session.bind)
        existing = inspector.get_table_names()
        for table_name in V2_TABLE_NAMES:
            assert table_name in existing, f"{table_name} 테이블이 존재하지 않음"

    def test_v2_table_count(self, db_session: Session):
        inspector = inspect(db_session.bind)
        existing = set(inspector.get_table_names())
        v2_set = set(V2_TABLE_NAMES)
        assert v2_set.issubset(existing)

    def test_v1_tables_still_exist(self, db_session: Session):
        inspector = inspect(db_session.bind)
        existing = inspector.get_table_names()
        for name in ["map_nodes", "resources", "echoes", "players", "sub_grid_nodes"]:
            assert name in existing


# ── PlayerModel.currency 검증 ─────────────────────────────


class TestPlayerCurrency:
    def test_currency_column_exists(self, db_session: Session):
        inspector = inspect(db_session.bind)
        columns = {c["name"] for c in inspector.get_columns("players")}
        assert "currency" in columns

    def test_currency_default_zero(self, db_session: Session):
        player = PlayerModel(
            player_id="p1",
            character_data={"WRITE": 3, "READ": 3, "EXEC": 3, "SUDO": 1},
            discovered_nodes=["0_0"],
        )
        db_session.add(player)
        db_session.commit()
        db_session.refresh(player)
        assert player.currency == 0


# ── CRUD 테스트 ───────────────────────────────────────────


def _make_npc(npc_id: str = "npc_001", **overrides) -> NPCModel:
    defaults = dict(
        npc_id=npc_id,
        full_name='{"given": "테스트"}',
        given_name="테스트",
        hexaco='{"H": 0.5, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}',
        character_sheet='{"WRITE": 3}',
        resonance_shield='{"Primordial": 0}',
        current_node="0_0",
        origin_type="promoted",
        role="innkeeper",
    )
    defaults.update(overrides)
    return NPCModel(**defaults)


def _make_bg_entity(entity_id: str = "bg_001", **overrides) -> BackgroundEntityModel:
    defaults = dict(
        entity_id=entity_id,
        entity_type="resident",
        current_node="0_0",
        role="innkeeper",
    )
    defaults.update(overrides)
    return BackgroundEntityModel(**defaults)


def _make_quest(quest_id: str = "q_001", **overrides) -> QuestModel:
    defaults = dict(
        quest_id=quest_id,
        title="테스트 퀘스트",
        description="테스트 설명",
        origin_type="conversation",
        quest_type="fetch",
        seed_tier=3,
        activated_turn=1,
    )
    defaults.update(overrides)
    return QuestModel(**defaults)


class TestCRUD:
    def test_item_prototype_crud(self, db_session: Session):
        proto = ItemPrototypeModel(
            item_id="iron_sword",
            name_kr="철검",
            item_type="equipment",
        )
        db_session.add(proto)
        db_session.commit()

        loaded = db_session.get(ItemPrototypeModel, "iron_sword")
        assert loaded is not None
        assert loaded.name_kr == "철검"
        assert loaded.bulk == 1
        assert loaded.is_dynamic is False

    def test_quest_chain_crud(self, db_session: Session):
        chain = QuestChainModel(chain_id="chain_001", created_turn=1)
        db_session.add(chain)
        db_session.commit()

        loaded = db_session.get(QuestChainModel, "chain_001")
        assert loaded is not None
        assert loaded.finalized is False
        assert loaded.total_quests == 0

    def test_background_slot_crud(self, db_session: Session):
        slot = BackgroundSlotModel(
            slot_id="slot_001",
            node_id="0_0",
            facility_id="inn_001",
            facility_type="inn",
            role="innkeeper",
        )
        db_session.add(slot)
        db_session.commit()

        loaded = db_session.get(BackgroundSlotModel, "slot_001")
        assert loaded is not None
        assert loaded.reset_interval == 24

    def test_background_entity_crud(self, db_session: Session):
        entity = _make_bg_entity()
        db_session.add(entity)
        db_session.commit()

        loaded = db_session.get(BackgroundEntityModel, "bg_001")
        assert loaded is not None
        assert loaded.promotion_score == 0
        assert loaded.promoted is False

    def test_npc_crud(self, db_session: Session):
        npc = _make_npc()
        db_session.add(npc)
        db_session.commit()

        loaded = db_session.get(NPCModel, "npc_001")
        assert loaded is not None
        assert loaded.given_name == "테스트"
        assert loaded.loyalty == pytest.approx(0.5)
        assert loaded.currency == 0

    def test_npc_memory_crud(self, db_session: Session):
        db_session.add(_make_npc())
        db_session.commit()

        mem = NPCMemoryModel(
            memory_id="mem_001",
            npc_id="npc_001",
            tier=2,
            memory_type="encounter",
            summary="처음 만남",
            turn_created=1,
        )
        db_session.add(mem)
        db_session.commit()

        loaded = db_session.get(NPCMemoryModel, "mem_001")
        assert loaded is not None
        assert loaded.emotional_valence == pytest.approx(0.0)

    def test_relationship_crud(self, db_session: Session):
        rel = RelationshipModel(
            relationship_id="rel_001",
            source_type="player",
            source_id="p1",
            target_type="npc",
            target_id="npc_001",
        )
        db_session.add(rel)
        db_session.commit()

        loaded = db_session.get(RelationshipModel, "rel_001")
        assert loaded is not None
        assert loaded.affinity == pytest.approx(0.0)
        assert loaded.familiarity == 0

    def test_quest_seed_crud(self, db_session: Session):
        db_session.add(_make_npc())
        db_session.commit()

        seed = QuestSeedModel(
            seed_id="seed_001",
            npc_id="npc_001",
            seed_type="rumor",
            seed_tier=3,
            created_turn=1,
            ttl_turns=10,
        )
        db_session.add(seed)
        db_session.commit()

        loaded = db_session.get(QuestSeedModel, "seed_001")
        assert loaded is not None

    def test_world_pool_crud(self, db_session: Session):
        db_session.add(_make_bg_entity("wp_001", entity_type="wanderer"))
        db_session.commit()

        wp = WorldPoolModel(
            entity_id="wp_001",
            entity_type="wanderer",
            promotion_score=10,
            last_known_node="1_1",
            registered_turn=5,
        )
        db_session.add(wp)
        db_session.commit()

        loaded = db_session.get(WorldPoolModel, "wp_001")
        assert loaded is not None
        assert loaded.promotion_score == 10

    def test_quest_crud(self, db_session: Session):
        quest = _make_quest()
        db_session.add(quest)
        db_session.commit()

        loaded = db_session.get(QuestModel, "q_001")
        assert loaded is not None
        assert loaded.title == "테스트 퀘스트"

    def test_quest_objective_crud(self, db_session: Session):
        db_session.add(_make_quest())
        db_session.commit()

        obj = QuestObjectiveModel(
            objective_id="obj_001",
            quest_id="q_001",
            description="아이템 찾기",
            objective_type="find_item",
        )
        db_session.add(obj)
        db_session.commit()

        loaded = db_session.get(QuestObjectiveModel, "obj_001")
        assert loaded is not None
        assert loaded.completed is False

    def test_quest_chain_eligible_crud(self, db_session: Session):
        db_session.add(_make_quest())
        db_session.commit()

        eligible = QuestChainEligibleModel(
            quest_id="q_001",
            npc_ref="innkeeper",
            ref_type="unborn",
            reason="quest_giver",
        )
        db_session.add(eligible)
        db_session.commit()

        loaded = db_session.get(QuestChainEligibleModel, eligible.id)
        assert loaded is not None
        assert loaded.ref_type == "unborn"

    def test_quest_unresolved_thread_crud(self, db_session: Session):
        thread = QuestUnresolvedThreadModel(
            thread_tag="strange_lights",
            created_turn=1,
        )
        db_session.add(thread)
        db_session.commit()

        loaded = db_session.get(QuestUnresolvedThreadModel, thread.id)
        assert loaded is not None
        assert loaded.resolved is False

    def test_dialogue_session_crud(self, db_session: Session):
        session_model = DialogueSessionModel(
            session_id="sess_001",
            player_id="p1",
            npc_id="npc_001",
            node_id="0_0",
            budget_total=6,
            started_turn=1,
        )
        db_session.add(session_model)
        db_session.commit()

        loaded = db_session.get(DialogueSessionModel, "sess_001")
        assert loaded is not None
        assert loaded.dialogue_turn_count == 0

    def test_dialogue_turn_crud(self, db_session: Session):
        db_session.add(
            DialogueSessionModel(
                session_id="sess_001",
                player_id="p1",
                npc_id="npc_001",
                node_id="0_0",
                budget_total=6,
                started_turn=1,
            )
        )
        db_session.commit()

        turn = DialogueTurnModel(
            turn_id="turn_001",
            session_id="sess_001",
            turn_index=0,
            pc_input="안녕",
            npc_narrative="반갑습니다",
        )
        db_session.add(turn)
        db_session.commit()

        loaded = db_session.get(DialogueTurnModel, "turn_001")
        assert loaded is not None

    def test_item_instance_crud(self, db_session: Session):
        proto = ItemPrototypeModel(
            item_id="iron_sword", name_kr="철검", item_type="equipment"
        )
        db_session.add(proto)
        db_session.commit()

        inst = ItemInstanceModel(
            instance_id="inst_001",
            prototype_id="iron_sword",
            owner_type="player",
            owner_id="p1",
            current_durability=100,
        )
        db_session.add(inst)
        db_session.commit()

        loaded = db_session.get(ItemInstanceModel, "inst_001")
        assert loaded is not None
        assert loaded.current_durability == 100


# ── CASCADE 삭제 테스트 ───────────────────────────────────


class TestCascadeDelete:
    def test_npc_delete_cascades_memories(self, db_session: Session):
        db_session.add(_make_npc())
        db_session.commit()
        db_session.add(
            NPCMemoryModel(
                memory_id="mem_c1",
                npc_id="npc_001",
                tier=2,
                memory_type="encounter",
                summary="기억",
                turn_created=1,
            )
        )
        db_session.commit()

        # NPC 삭제 → 기억도 삭제
        db_session.execute(text("PRAGMA foreign_keys=ON"))
        npc = db_session.get(NPCModel, "npc_001")
        db_session.delete(npc)
        db_session.commit()

        assert db_session.get(NPCMemoryModel, "mem_c1") is None

    def test_quest_delete_cascades_objectives(self, db_session: Session):
        db_session.add(_make_quest())
        db_session.commit()
        db_session.add(
            QuestObjectiveModel(
                objective_id="obj_c1",
                quest_id="q_001",
                description="목표",
                objective_type="reach_node",
            )
        )
        db_session.commit()

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        quest = db_session.get(QuestModel, "q_001")
        db_session.delete(quest)
        db_session.commit()

        assert db_session.get(QuestObjectiveModel, "obj_c1") is None

    def test_quest_delete_cascades_chain_eligible(self, db_session: Session):
        db_session.add(_make_quest())
        db_session.commit()
        eligible = QuestChainEligibleModel(
            quest_id="q_001",
            npc_ref="innkeeper",
            ref_type="existing",
            reason="quest_giver",
        )
        db_session.add(eligible)
        db_session.commit()
        eid = eligible.id

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        quest = db_session.get(QuestModel, "q_001")
        db_session.delete(quest)
        db_session.commit()

        assert db_session.get(QuestChainEligibleModel, eid) is None

    def test_session_delete_cascades_turns(self, db_session: Session):
        db_session.add(
            DialogueSessionModel(
                session_id="sess_c1",
                player_id="p1",
                npc_id="npc_001",
                node_id="0_0",
                budget_total=6,
                started_turn=1,
            )
        )
        db_session.commit()
        db_session.add(
            DialogueTurnModel(
                turn_id="turn_c1",
                session_id="sess_c1",
                turn_index=0,
                pc_input="A",
                npc_narrative="B",
            )
        )
        db_session.commit()

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        sess = db_session.get(DialogueSessionModel, "sess_c1")
        db_session.delete(sess)
        db_session.commit()

        assert db_session.get(DialogueTurnModel, "turn_c1") is None

    def test_bg_entity_delete_cascades_world_pool(self, db_session: Session):
        db_session.add(_make_bg_entity("bg_wp", entity_type="wanderer"))
        db_session.commit()
        db_session.add(
            WorldPoolModel(
                entity_id="bg_wp",
                entity_type="wanderer",
                promotion_score=5,
                last_known_node="1_1",
                registered_turn=1,
            )
        )
        db_session.commit()

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        entity = db_session.get(BackgroundEntityModel, "bg_wp")
        db_session.delete(entity)
        db_session.commit()

        assert db_session.get(WorldPoolModel, "bg_wp") is None


# ── UNIQUE 제약 테스트 ────────────────────────────────────


class TestUniqueConstraint:
    def test_relationship_unique_pair(self, db_session: Session):
        rel1 = RelationshipModel(
            relationship_id="rel_u1",
            source_type="player",
            source_id="p1",
            target_type="npc",
            target_id="npc_001",
        )
        rel2 = RelationshipModel(
            relationship_id="rel_u2",
            source_type="player",
            source_id="p1",
            target_type="npc",
            target_id="npc_001",
        )
        db_session.add(rel1)
        db_session.commit()
        db_session.add(rel2)
        with pytest.raises(IntegrityError):
            db_session.commit()


# ── 인덱스 존재 검증 ─────────────────────────────────────


EXPECTED_INDEXES = [
    ("background_entities", "idx_bg_entity_node"),
    ("background_entities", "idx_bg_entity_type"),
    ("background_slots", "idx_slot_node"),
    ("background_slots", "idx_slot_facility"),
    ("npcs", "idx_npc_node"),
    ("npcs", "idx_npc_role"),
    ("npc_memories", "idx_memory_npc"),
    ("npc_memories", "idx_memory_npc_tier"),
    ("relationships", "idx_rel_source"),
    ("relationships", "idx_rel_target"),
    ("quest_seeds", "idx_seed_npc"),
    ("quest_seeds", "idx_seed_status"),
    ("world_pool", "idx_wp_type"),
    ("quests", "idx_quest_status"),
    ("quests", "idx_quest_chain"),
    ("quests", "idx_quest_npc"),
    ("quest_objectives", "idx_objective_quest"),
    ("quest_chain_eligible", "idx_chain_eligible_quest"),
    ("quest_chain_eligible", "idx_chain_eligible_ref"),
    ("quest_unresolved_threads", "idx_thread_chain"),
    ("dialogue_sessions", "idx_session_player"),
    ("dialogue_sessions", "idx_session_npc"),
    ("dialogue_turns", "idx_turn_session"),
    ("item_instances", "idx_item_owner"),
    ("item_instances", "idx_item_proto"),
]


class TestIndexes:
    @pytest.mark.parametrize("table_name,index_name", EXPECTED_INDEXES)
    def test_index_exists(self, db_session: Session, table_name: str, index_name: str):
        inspector = inspect(db_session.bind)
        indexes = inspector.get_indexes(table_name)
        idx_names = {idx["name"] for idx in indexes}
        assert (
            index_name in idx_names
        ), f"{table_name}에 {index_name} 인덱스가 없음 (존재: {idx_names})"


# ── server_default 검증 ──────────────────────────────────


class TestServerDefaults:
    def test_quest_chain_created_at_auto(self, db_session: Session):
        chain = QuestChainModel(chain_id="chain_sd", created_turn=1)
        db_session.add(chain)
        db_session.commit()
        db_session.refresh(chain)
        assert chain.created_at is not None

    def test_relationship_status_default(self, db_session: Session):
        rel = RelationshipModel(
            relationship_id="rel_sd",
            source_type="player",
            source_id="p1",
            target_type="npc",
            target_id="npc_sd",
        )
        db_session.add(rel)
        db_session.commit()
        db_session.refresh(rel)
        assert rel.status == "stranger"

    def test_quest_status_default(self, db_session: Session):
        quest = _make_quest(quest_id="q_sd")
        db_session.add(quest)
        db_session.commit()
        db_session.refresh(quest)
        assert quest.status == "active"

    def test_dialogue_session_status_default(self, db_session: Session):
        sess = DialogueSessionModel(
            session_id="sess_sd",
            player_id="p1",
            npc_id="npc_001",
            node_id="0_0",
            budget_total=6,
            started_turn=1,
        )
        db_session.add(sess)
        db_session.commit()
        db_session.refresh(sess)
        assert sess.status == "active"
