"""#11-D 테스트: ItemModule, restock"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.registry import PrototypeRegistry
from src.core.item.restock import (
    ShopRestockConfig,
    calculate_restock_deficit,
    check_restock_needed,
)
from src.db.models import Base
from src.modules.base import GameContext
from src.modules.item.module import ItemModule
from src.services.item_service import ItemService

SEED_ITEMS_PATH = Path("src/data/seed_items.json")
AXIOM_TAG_MAPPING_PATH = Path("src/data/axiom_tag_mapping.json")


@pytest.fixture()
def setup():
    """인메모리 DB + ItemModule"""
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

    module = ItemModule(service)
    return module, service, db, bus


class TestItemModule:
    def test_name_and_dependencies(self, setup) -> None:
        module, service, db, bus = setup
        assert module.name == "item"
        assert module.dependencies == []

    def test_get_available_actions(self, setup) -> None:
        module, service, db, bus = setup
        ctx = GameContext(
            player_id="p1",
            current_node_id="0_0",
            current_turn=1,
            db_session=db,
        )
        actions = module.get_available_actions(ctx)
        assert len(actions) == 5
        action_names = [a.name for a in actions]
        assert "inventory" in action_names
        assert "pickup" in action_names
        assert "drop" in action_names
        assert "use" in action_names
        assert "browse" in action_names

    def test_on_node_enter_sets_context(self, setup) -> None:
        module, service, db, bus = setup
        # Place an item on the node
        service.create_instance("wpn_rusty_sword", "node", "3_5")

        ctx = GameContext(
            player_id="p1",
            current_node_id="3_5",
            current_turn=1,
            db_session=db,
        )
        module.on_node_enter("3_5", ctx)
        assert "item" in ctx.extra
        assert len(ctx.extra["item"]["node_items"]) == 1
        assert ctx.extra["item"]["node_items"][0]["prototype_id"] == "wpn_rusty_sword"

    def test_on_turn_restock(self, setup) -> None:
        module, service, db, bus = setup
        # Create a shelf
        shelf = service.create_instance("misc_shop_shelf", "node", "0_0")

        config = ShopRestockConfig(
            npc_id="npc1",
            shelf_instance_id=shelf.instance_id,
            stock_template=["wpn_rusty_sword"],
            restock_cooldown=5,
            max_stock_per_item=2,
        )
        module.register_restock_config(config)

        ctx = GameContext(
            player_id="p1",
            current_node_id="0_0",
            current_turn=5,
            db_session=db,
        )
        module.on_turn(ctx)

        # Should have created 2 swords on the shelf
        items = service.get_instances_by_owner("container", shelf.instance_id)
        sword_count = sum(1 for i in items if i.prototype_id == "wpn_rusty_sword")
        assert sword_count == 2


class TestRestock:
    def test_check_restock_needed(self) -> None:
        config = ShopRestockConfig(
            npc_id="n1",
            shelf_instance_id="shelf1",
            restock_cooldown=5,
        )
        assert check_restock_needed(config, 0) is True
        assert check_restock_needed(config, 1) is False
        assert check_restock_needed(config, 5) is True
        assert check_restock_needed(config, 10) is True

    def test_calculate_restock_deficit(self) -> None:
        config = ShopRestockConfig(
            npc_id="n1",
            shelf_instance_id="shelf1",
            stock_template=["wpn_rusty_sword", "tool_torch"],
            max_stock_per_item=3,
        )
        current_stock = {"wpn_rusty_sword": 1, "tool_torch": 3}
        deficit = calculate_restock_deficit(config, current_stock)
        assert deficit == {"wpn_rusty_sword": 2}
