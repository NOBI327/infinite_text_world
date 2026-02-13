"""ItemService 통합 테스트 (인메모리 SQLite + EventBus)

#11-C 검증: 최소 17개 테스트 케이스.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.registry import PrototypeRegistry
from src.db.models import Base, PlayerModel
from src.db.models_v2 import ItemPrototypeModel, NPCModel
from src.services.item_service import ItemService

SEED_ITEMS_PATH = Path("src/data/seed_items.json")
AXIOM_TAG_MAPPING_PATH = Path("src/data/axiom_tag_mapping.json")


@pytest.fixture()
def setup():
    """인메모리 DB + EventBus + ItemService"""
    engine = create_engine("sqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    bus = EventBus()

    registry = PrototypeRegistry()
    registry.load_from_json(SEED_ITEMS_PATH)

    axiom_mapping = AxiomTagMapping()
    axiom_mapping.load_from_json(AXIOM_TAG_MAPPING_PATH)

    service = ItemService(db, bus, registry, axiom_mapping)
    service.sync_prototypes_to_db()

    return service, db, bus, registry


@pytest.fixture()
def setup_with_player(setup):
    """setup + 테스트 플레이어"""
    service, db, bus, registry = setup
    player = PlayerModel(
        player_id="p1",
        x=0,
        y=0,
        character_data={"stats": {"WRITE": 2, "READ": 2, "EXEC": 2, "SUDO": 1}},
        currency=500,
    )
    db.add(player)
    db.commit()
    return service, db, bus, registry


@pytest.fixture()
def setup_with_npc(setup_with_player):
    """setup + 테스트 NPC"""
    service, db, bus, registry = setup_with_player
    import json

    npc = NPCModel(
        npc_id="npc1",
        full_name="Hans the Blacksmith",
        given_name="Hans",
        hexaco=json.dumps({"H": 0.5, "E": 0.5, "X": 0.7, "A": 0.5, "C": 0.5, "O": 0.5}),
        character_sheet=json.dumps({"WRITE": 2, "READ": 2, "EXEC": 2, "SUDO": 1}),
        resonance_shield=json.dumps({}),
        current_node="0_0",
        origin_type="resident",
        role="blacksmith",
        currency=1000,
    )
    db.add(npc)
    db.commit()
    return service, db, bus, registry


# ── create_instance ──────────────────────────────────────────


class TestCreateInstance:
    def test_create_basic(self, setup) -> None:
        service, db, bus, registry = setup
        inst = service.create_instance("wpn_rusty_sword", "player", "p1")
        assert inst.prototype_id == "wpn_rusty_sword"
        assert inst.owner_type == "player"
        assert inst.owner_id == "p1"
        assert inst.current_durability == 30  # max_durability from prototype

    def test_create_emits_event(self, setup) -> None:
        service, db, bus, registry = setup
        events: list[GameEvent] = []
        bus.subscribe(EventTypes.ITEM_CREATED, lambda e: events.append(e))
        service.create_instance("wpn_rusty_sword", "player", "p1")
        assert len(events) == 1
        assert events[0].data["prototype_id"] == "wpn_rusty_sword"


# ── get_instance ─────────────────────────────────────────────


class TestGetInstance:
    def test_get_existing(self, setup) -> None:
        service, db, bus, registry = setup
        created = service.create_instance("wpn_rusty_sword", "player", "p1")
        fetched = service.get_instance(created.instance_id)
        assert fetched is not None
        assert fetched.instance_id == created.instance_id

    def test_get_nonexistent(self, setup) -> None:
        service, db, bus, registry = setup
        assert service.get_instance("nonexistent") is None


# ── get_instances_by_owner ───────────────────────────────────


class TestGetInstancesByOwner:
    def test_multiple_items(self, setup) -> None:
        service, db, bus, registry = setup
        service.create_instance("wpn_rusty_sword", "player", "p1")
        service.create_instance("tool_torch", "player", "p1")
        service.create_instance("con_bandage", "npc", "n1")

        player_items = service.get_instances_by_owner("player", "p1")
        assert len(player_items) == 2


# ── transfer_item ────────────────────────────────────────────


class TestTransferItem:
    def test_transfer_success(self, setup) -> None:
        service, db, bus, registry = setup
        inst = service.create_instance("wpn_rusty_sword", "player", "p1")
        events: list[GameEvent] = []
        bus.subscribe(EventTypes.ITEM_TRANSFERRED, lambda e: events.append(e))

        result = service.transfer_item(inst.instance_id, "npc", "n1", reason="gift")
        assert result is True
        assert len(events) == 1

        updated = service.get_instance(inst.instance_id)
        assert updated is not None
        assert updated.owner_type == "npc"
        assert updated.owner_id == "n1"

    def test_transfer_nonexistent(self, setup) -> None:
        service, db, bus, registry = setup
        assert service.transfer_item("fake", "npc", "n1") is False


# ── use_item ─────────────────────────────────────────────────


class TestUseItem:
    def test_durability_loss(self, setup) -> None:
        service, db, bus, registry = setup
        inst = service.create_instance("wpn_rusty_sword", "player", "p1")
        result = service.use_item(inst.instance_id)
        assert result["broken"] is False
        assert result["new_durability"] == 28  # 30 - 2

    def test_item_breaks_with_result(self, setup) -> None:
        service, db, bus, registry = setup
        # Create with 1 durability so it breaks on use
        inst = service.create_instance(
            "wpn_rusty_sword", "player", "p1", current_durability=1
        )
        broken_events: list[GameEvent] = []
        bus.subscribe(EventTypes.ITEM_BROKEN, lambda e: broken_events.append(e))

        result = service.use_item(inst.instance_id)
        assert result["broken"] is True
        assert result["broken_result"] == "mat_iron_scrap"
        assert len(broken_events) == 1

        # Original should be deleted
        assert service.get_instance(inst.instance_id) is None

        # broken_result item should be created
        scraps = service.get_instances_by_owner("player", "p1")
        assert len(scraps) == 1
        assert scraps[0].prototype_id == "mat_iron_scrap"

    def test_indestructible(self, setup) -> None:
        service, db, bus, registry = setup
        # tool_flint_steel has max_durability=0
        inst = service.create_instance("tool_flint_steel", "player", "p1")
        result = service.use_item(inst.instance_id)
        assert result["broken"] is False


# ── calculate_price ──────────────────────────────────────────


class TestCalculatePrice:
    def test_basic_price(self, setup) -> None:
        service, db, bus, registry = setup
        inst = service.create_instance("wpn_rusty_sword", "player", "p1")
        price = service.calculate_price(inst.instance_id, "stranger", True, 0.5)
        # base_value=25, buy=*1.5, stranger=*1.0, h=0.5 (no mod), dur=1.0
        assert price == 38  # round(25 * 1.5)


# ── process_haggle ───────────────────────────────────────────


class TestProcessHaggle:
    def test_accept(self, setup) -> None:
        service, db, bus, registry = setup
        result = service.process_haggle(90, 100, "stranger", 0.8)
        assert result["result"] == "accept"
        assert result["counter_price"] is None

    def test_counter(self, setup) -> None:
        service, db, bus, registry = setup
        result = service.process_haggle(60, 100, "stranger", 0.8)
        assert result["result"] == "counter"
        assert result["counter_price"] == 80

    def test_reject(self, setup) -> None:
        service, db, bus, registry = setup
        result = service.process_haggle(40, 100, "stranger", 0.8)
        assert result["result"] == "reject"


# ── execute_trade ────────────────────────────────────────────


class TestExecuteTrade:
    def test_successful_trade(self, setup_with_npc) -> None:
        service, db, bus, registry = setup_with_npc
        inst = service.create_instance("wpn_rusty_sword", "npc", "npc1")

        result = service.execute_trade(
            inst.instance_id,
            buyer_type="player",
            buyer_id="p1",
            seller_type="npc",
            seller_id="npc1",
            price=30,
        )
        assert result is True

        # Buyer currency decreased
        player = db.query(PlayerModel).filter(PlayerModel.player_id == "p1").first()
        assert player is not None
        assert player.currency == 470  # 500 - 30

        # Seller currency increased
        npc = db.query(NPCModel).filter(NPCModel.npc_id == "npc1").first()
        assert npc is not None
        assert npc.currency == 1030  # 1000 + 30

        # Item transferred
        updated = service.get_instance(inst.instance_id)
        assert updated is not None
        assert updated.owner_type == "player"

    def test_insufficient_funds(self, setup_with_npc) -> None:
        service, db, bus, registry = setup_with_npc
        inst = service.create_instance("wpn_rusty_sword", "npc", "npc1")

        result = service.execute_trade(
            inst.instance_id,
            buyer_type="player",
            buyer_id="p1",
            seller_type="npc",
            seller_id="npc1",
            price=9999,
        )
        assert result is False


# ── process_gift ─────────────────────────────────────────────


class TestProcessGift:
    def test_gift_normal(self, setup) -> None:
        service, db, bus, registry = setup
        inst = service.create_instance("wpn_rusty_sword", "player", "p1")

        result = service.process_gift(
            inst.instance_id,
            from_type="player",
            from_id="p1",
            to_npc_id="n1",
            npc_desire_tags=["weapon", "iron"],
        )
        assert result["affinity_delta"] >= 1
        assert result["transferred"] is True


# ── get_item_constraints ─────────────────────────────────────


class TestGetItemConstraints:
    def test_constraints_build(self, setup) -> None:
        service, db, bus, registry = setup
        service.create_instance("wpn_rusty_sword", "player", "p1")
        service.create_instance("tool_torch", "player", "p1")

        constraints = service.get_item_constraints("p1")
        assert "wpn_rusty_sword" in constraints["pc_items"]
        assert "tool_torch" in constraints["pc_items"]
        assert "Scindere" in constraints["pc_axiom_powers"]
        assert "Ignis" in constraints["pc_axiom_powers"]


# ── sync_prototypes_to_db ────────────────────────────────────


class TestSyncPrototypes:
    def test_sync_count(self, setup) -> None:
        service, db, bus, registry = setup
        # Already synced in fixture, verify DB count
        count = db.query(ItemPrototypeModel).count()
        assert count == 60

    def test_sync_idempotent(self, setup) -> None:
        service, db, bus, registry = setup
        # Second sync should add 0
        second_count = service.sync_prototypes_to_db()
        assert second_count == 0


# ── inventory ────────────────────────────────────────────────


class TestInventory:
    def test_get_inventory_bulk(self, setup) -> None:
        service, db, bus, registry = setup
        service.create_instance("wpn_rusty_sword", "player", "p1")  # bulk=3
        service.create_instance("tool_torch", "player", "p1")  # bulk=2
        bulk = service.get_inventory_bulk("player", "p1")
        assert bulk == 5

    def test_can_add_to_inventory(self, setup) -> None:
        service, db, bus, registry = setup
        # Empty inventory, default EXEC=2 → capacity 50, adding bulk=3
        assert (
            service.can_add_to_inventory("player", "p1", "wpn_rusty_sword", {"EXEC": 2})
            is True
        )
