"""#11-A 테스트: Item Core 모델, Registry, AxiomTagMapping"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.item.models import ItemType, ItemPrototype, ItemInstance
from src.core.item.registry import PrototypeRegistry
from src.core.item.axiom_mapping import AxiomTagMapping, AxiomTagInfo

SEED_ITEMS_PATH = Path("src/data/seed_items.json")
AXIOM_TAG_MAPPING_PATH = Path("src/data/axiom_tag_mapping.json")


# ── ItemPrototype ─────────────────────────────────────────────


class TestItemPrototype:
    def test_creation(self) -> None:
        proto = ItemPrototype(
            item_id="test_sword",
            item_type=ItemType.EQUIPMENT,
            weight=2.5,
            bulk=3,
            base_value=25,
            primary_material="Iron",
            axiom_tags={"Scindere": 2, "Ferrum": 1},
            max_durability=30,
            durability_loss_per_use=2,
            broken_result="mat_iron_scrap",
            tags=("weapon", "melee"),
            name_kr="테스트 검",
        )
        assert proto.item_id == "test_sword"
        assert proto.item_type == ItemType.EQUIPMENT
        assert proto.bulk == 3
        assert proto.tags == ("weapon", "melee")

    def test_frozen_immutable(self) -> None:
        proto = ItemPrototype(
            item_id="test_sword",
            item_type=ItemType.EQUIPMENT,
            weight=2.5,
            bulk=3,
            base_value=25,
            primary_material="Iron",
            axiom_tags={"Scindere": 2},
            max_durability=30,
            durability_loss_per_use=2,
            broken_result=None,
        )
        with pytest.raises(AttributeError):
            proto.item_id = "changed"  # type: ignore[misc]


# ── ItemInstance ──────────────────────────────────────────────


class TestItemInstance:
    def test_creation_and_mutability(self) -> None:
        inst = ItemInstance(
            instance_id="uuid-1",
            prototype_id="test_sword",
            owner_type="player",
            owner_id="p1",
            current_durability=30,
        )
        assert inst.instance_id == "uuid-1"
        assert inst.owner_type == "player"

        # mutable
        inst.current_durability = 20
        assert inst.current_durability == 20
        inst.state_tags.append("wet")
        assert "wet" in inst.state_tags


# ── ItemType ──────────────────────────────────────────────────


class TestItemType:
    def test_enum_values(self) -> None:
        assert ItemType.EQUIPMENT.value == "equipment"
        assert ItemType.CONSUMABLE.value == "consumable"
        assert ItemType.MATERIAL.value == "material"
        assert ItemType.MISC.value == "misc"


# ── PrototypeRegistry ────────────────────────────────────────


class TestPrototypeRegistry:
    @pytest.fixture()
    def registry(self) -> PrototypeRegistry:
        reg = PrototypeRegistry()
        reg.load_from_json(SEED_ITEMS_PATH)
        return reg

    def test_load_from_json_count(self, registry: PrototypeRegistry) -> None:
        assert registry.count() == 60

    def test_get_existing(self, registry: PrototypeRegistry) -> None:
        proto = registry.get("wpn_rusty_sword")
        assert proto is not None
        assert proto.item_type == ItemType.EQUIPMENT
        assert proto.name_kr == "녹슨 철검"
        assert "Scindere" in proto.axiom_tags

    def test_get_nonexistent(self, registry: PrototypeRegistry) -> None:
        assert registry.get("nonexistent_item") is None

    def test_register_dynamic(self) -> None:
        reg = PrototypeRegistry()
        proto = ItemPrototype(
            item_id="dyn_fire_blade",
            item_type=ItemType.EQUIPMENT,
            weight=2.0,
            bulk=3,
            base_value=100,
            primary_material="Iron",
            axiom_tags={"Ignis": 3, "Scindere": 2},
            max_durability=50,
            durability_loss_per_use=1,
            broken_result="mat_iron_scrap",
            tags=("weapon", "fire"),
            name_kr="화염 검",
        )
        reg.register(proto)
        assert reg.count() == 1
        assert reg.get("dyn_fire_blade") is not None

    def test_search_by_tags_single(self, registry: PrototypeRegistry) -> None:
        results = registry.search_by_tags(["weapon"])
        assert len(results) > 0
        for r in results:
            assert "weapon" in r.tags

    def test_search_by_tags_multi_or(self, registry: PrototypeRegistry) -> None:
        results = registry.search_by_tags(["weapon", "healing"])
        weapon_or_healing = [
            r for r in results if "weapon" in r.tags or "healing" in r.tags
        ]
        assert len(results) == len(weapon_or_healing)
        assert len(results) > 0

    def test_search_by_axiom(self, registry: PrototypeRegistry) -> None:
        results = registry.search_by_axiom("Ferrum")
        assert len(results) > 0
        for r in results:
            assert "Ferrum" in r.axiom_tags


# ── AxiomTagMapping ──────────────────────────────────────────


class TestAxiomTagMapping:
    @pytest.fixture()
    def mapping(self) -> AxiomTagMapping:
        m = AxiomTagMapping()
        m.load_from_json(AXIOM_TAG_MAPPING_PATH)
        return m

    def test_load_from_json_count(self, mapping: AxiomTagMapping) -> None:
        assert len(mapping.get_all_tags()) == 23

    def test_get_existing(self, mapping: AxiomTagMapping) -> None:
        info = mapping.get("Ignis")
        assert info is not None
        assert isinstance(info, AxiomTagInfo)
        assert info.domain == "Primordial"
        assert info.resonance == "Destruction"

    def test_get_nonexistent(self, mapping: AxiomTagMapping) -> None:
        assert mapping.get("NonExistentTag") is None

    def test_get_domain(self, mapping: AxiomTagMapping) -> None:
        assert mapping.get_domain("Ferrum") == "Material"
        assert mapping.get_domain("NonExistent") is None

    def test_get_resonance(self, mapping: AxiomTagMapping) -> None:
        assert mapping.get_resonance("Scindere") == "Destruction"
        assert mapping.get_resonance("NonExistent") is None
