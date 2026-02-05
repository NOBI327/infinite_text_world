"""Tests for database persistence (save/load) functionality."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.engine import (
    PlayerState,
    _model_to_node,
    _model_to_player,
    _node_to_model,
    _player_to_model,
)
from src.core.world_generator import (
    AxiomVector,
    Echo,
    MapNode,
    NodeTier,
    Resource,
    SensoryData,
)
from src.db.models import Base, EchoModel, MapNodeModel, PlayerModel, ResourceModel


@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture()
def session(engine) -> Session:
    """Provide a database session with tables created."""
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    sess = session_factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture()
def sample_node() -> MapNode:
    """Create a sample MapNode for testing."""
    vector = AxiomVector()
    vector.add("axiom_ignis", 0.8)
    vector.add("axiom_aqua", 0.3)

    sensory = SensoryData(
        visual_far="멀리서 불빛이 보인다",
        visual_near="화염이 타오르는 공간",
        atmosphere="뜨거운 열기",
        sound_hint="타닥타닥 소리",
        smell_hint="연기 냄새",
    )

    return MapNode(
        x=5,
        y=10,
        tier=NodeTier.UNCOMMON,
        axiom_vector=vector,
        sensory_data=sensory,
        cluster_id="cls_test_001",
        development_level=2,
        discovered_by=["player_1", "player_2"],
    )


@pytest.fixture()
def sample_player() -> PlayerState:
    """Create a sample PlayerState for testing."""
    player = PlayerState(
        player_id="test_player_001",
        x=3,
        y=7,
        supply=15,
        fame=50,
        discovered_nodes=["0_0", "1_0", "0_1"],
        inventory={"res_ore": 10, "res_herb": 5},
        active_effects=[{"type": "buff", "duration": 10}],
        investigation_penalty=1,
        equipped_tags=["fire_resist", "speed_boost"],
    )
    player.character.level = 5
    player.character.set_stat("WRITE", 3)
    player.character.set_stat("READ", 2)
    return player


class TestNodePersistence:
    """Tests for MapNode persistence."""

    def test_save_and_load_node(self, session: Session, sample_node: MapNode):
        """Test basic node save and load."""
        # Save
        model = _node_to_model(sample_node)
        session.add(model)
        session.commit()

        # Load
        loaded_model = session.get(MapNodeModel, sample_node.coordinate)
        assert loaded_model is not None

        loaded_node = _model_to_node(loaded_model)

        # Verify
        assert loaded_node.x == sample_node.x
        assert loaded_node.y == sample_node.y
        assert loaded_node.tier == sample_node.tier
        assert loaded_node.cluster_id == sample_node.cluster_id
        assert loaded_node.development_level == sample_node.development_level
        assert loaded_node.discovered_by == sample_node.discovered_by
        assert loaded_node.axiom_vector.get("axiom_ignis") == pytest.approx(0.8)
        assert loaded_node.axiom_vector.get("axiom_aqua") == pytest.approx(0.3)
        assert (
            loaded_node.sensory_data.atmosphere == sample_node.sensory_data.atmosphere
        )

    def test_node_with_resources(self, session: Session, sample_node: MapNode):
        """Test node with resources save and load."""
        # Add resources to node
        sample_node.resources = [
            Resource(
                id="res_ore", max_amount=100, current_amount=80, npc_competition=0.1
            ),
            Resource(
                id="res_herb", max_amount=50, current_amount=30, npc_competition=0.2
            ),
        ]

        # Save node
        model = _node_to_model(sample_node)
        session.add(model)
        session.flush()

        # Save resources
        for res in sample_node.resources:
            res_model = ResourceModel(
                node_coordinate=sample_node.coordinate,
                resource_type=res.id,
                max_amount=res.max_amount,
                current_amount=res.current_amount,
                npc_competition=res.npc_competition,
            )
            session.add(res_model)
        session.commit()

        # Load
        loaded_model = session.get(MapNodeModel, sample_node.coordinate)
        loaded_node = _model_to_node(loaded_model)

        # Verify resources
        assert len(loaded_node.resources) == 2
        ore_res = next((r for r in loaded_node.resources if r.id == "res_ore"), None)
        assert ore_res is not None
        assert ore_res.max_amount == 100
        assert ore_res.current_amount == 80
        assert ore_res.npc_competition == pytest.approx(0.1)

    def test_node_with_echoes(self, session: Session, sample_node: MapNode):
        """Test node with echoes save and load."""
        # Add echoes to node
        sample_node.echoes = [
            Echo(
                echo_type="Short",
                visibility="Public",
                base_difficulty=2,
                timestamp="2024-01-01T12:00:00",
                flavor_text="누군가 이곳을 지나갔다",
                source_player_id="player_abc",
            ),
            Echo(
                echo_type="Long",
                visibility="Hidden",
                base_difficulty=3,
                timestamp="2024-01-02T08:00:00",
                flavor_text="오래된 전투의 흔적",
                source_player_id=None,
            ),
        ]

        # Save node
        model = _node_to_model(sample_node)
        session.add(model)
        session.flush()

        # Save echoes
        for echo in sample_node.echoes:
            echo_model = EchoModel(
                node_coordinate=sample_node.coordinate,
                echo_type=echo.echo_type,
                visibility=echo.visibility,
                base_difficulty=echo.base_difficulty,
                timestamp=echo.timestamp,
                flavor_text=echo.flavor_text,
                source_player_id=echo.source_player_id,
            )
            session.add(echo_model)
        session.commit()

        # Load
        loaded_model = session.get(MapNodeModel, sample_node.coordinate)
        loaded_node = _model_to_node(loaded_model)

        # Verify echoes
        assert len(loaded_node.echoes) == 2
        public_echo = next(
            (e for e in loaded_node.echoes if e.visibility == "Public"), None
        )
        assert public_echo is not None
        assert public_echo.echo_type == "Short"
        assert public_echo.base_difficulty == 2
        assert public_echo.source_player_id == "player_abc"

        hidden_echo = next(
            (e for e in loaded_node.echoes if e.visibility == "Hidden"), None
        )
        assert hidden_echo is not None
        assert hidden_echo.source_player_id is None

    def test_upsert_existing_node(self, session: Session, sample_node: MapNode):
        """Test updating an existing node."""
        # Initial save
        model = _node_to_model(sample_node)
        session.add(model)
        session.commit()

        # Modify node
        sample_node.development_level = 5
        sample_node.discovered_by.append("player_3")
        sample_node.axiom_vector.add("axiom_terra", 0.5)

        # Upsert (update existing)
        existing = session.get(MapNodeModel, sample_node.coordinate)
        assert existing is not None

        existing.development_level = sample_node.development_level
        existing.discovered_by = sample_node.discovered_by
        existing.axiom_vector = sample_node.axiom_vector.to_dict()
        session.commit()

        # Reload and verify
        session.expire_all()
        reloaded = session.get(MapNodeModel, sample_node.coordinate)
        reloaded_node = _model_to_node(reloaded)

        assert reloaded_node.development_level == 5
        assert "player_3" in reloaded_node.discovered_by
        assert reloaded_node.axiom_vector.get("axiom_terra") == pytest.approx(0.5)


class TestPlayerPersistence:
    """Tests for PlayerState persistence."""

    def test_save_and_load_player(self, session: Session, sample_player: PlayerState):
        """Test basic player save and load."""
        # Save
        model = _player_to_model(sample_player)
        session.add(model)
        session.commit()

        # Load
        loaded_model = session.get(PlayerModel, sample_player.player_id)
        assert loaded_model is not None

        loaded_player = _model_to_player(loaded_model)

        # Verify basic fields
        assert loaded_player.player_id == sample_player.player_id
        assert loaded_player.x == sample_player.x
        assert loaded_player.y == sample_player.y
        assert loaded_player.supply == sample_player.supply
        assert loaded_player.fame == sample_player.fame
        assert (
            loaded_player.investigation_penalty == sample_player.investigation_penalty
        )

        # Verify lists and dicts
        assert loaded_player.discovered_nodes == sample_player.discovered_nodes
        assert loaded_player.inventory == sample_player.inventory
        assert loaded_player.equipped_tags == sample_player.equipped_tags
        assert len(loaded_player.active_effects) == 1

        # Verify character sheet
        assert loaded_player.character.name == sample_player.character.name
        assert loaded_player.character.level == 5
        assert loaded_player.character.get_stat("WRITE") == 3
        assert loaded_player.character.get_stat("READ") == 2
