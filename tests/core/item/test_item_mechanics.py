"""#11-B 테스트: 인벤토리, 내구도, 거래, 선물, Constraints"""

from __future__ import annotations

import pytest

from src.core.item.models import ItemType, ItemPrototype, ItemInstance
from src.core.item.inventory import (
    calculate_inventory_capacity,
    calculate_current_bulk,
    can_add_item,
)
from src.core.item.durability import apply_durability_loss, get_durability_ratio
from src.core.item.trade import (
    calculate_trade_price,
    evaluate_haggle,
    calculate_counter_price,
)
from src.core.item.gift import calculate_gift_affinity
from src.core.item.constraints import build_item_constraints


def _make_proto(
    item_id: str = "test_item",
    base_value: int = 100,
    bulk: int = 3,
    max_durability: int = 30,
    durability_loss_per_use: int = 2,
    broken_result: str | None = "mat_iron_scrap",
    tags: tuple[str, ...] = (),
    axiom_tags: dict[str, int] | None = None,
) -> ItemPrototype:
    return ItemPrototype(
        item_id=item_id,
        item_type=ItemType.EQUIPMENT,
        weight=2.0,
        bulk=bulk,
        base_value=base_value,
        primary_material="Iron",
        axiom_tags=axiom_tags or {},
        max_durability=max_durability,
        durability_loss_per_use=durability_loss_per_use,
        broken_result=broken_result,
        tags=tags,
    )


def _make_instance(
    instance_id: str = "inst-1",
    prototype_id: str = "test_item",
    current_durability: int = 30,
    owner_type: str = "player",
    owner_id: str = "p1",
) -> ItemInstance:
    return ItemInstance(
        instance_id=instance_id,
        prototype_id=prototype_id,
        owner_type=owner_type,
        owner_id=owner_id,
        current_durability=current_durability,
    )


# ── Inventory ─────────────────────────────────────────────────


class TestInventory:
    def test_capacity_default_exec(self) -> None:
        # EXEC=2 (기본) → 50
        assert calculate_inventory_capacity({"EXEC": 2}) == 50

    def test_capacity_high_exec(self) -> None:
        # EXEC=4 → 50 + (4-2)*5 = 60
        assert calculate_inventory_capacity({"EXEC": 4}) == 60

    def test_capacity_low_exec_minimum(self) -> None:
        # EXEC=0 → 50 + (0-2)*5 = 40
        assert calculate_inventory_capacity({"EXEC": 0}) == 40
        # EXEC=-2 → 50 + (-2-2)*5 = 30
        assert calculate_inventory_capacity({"EXEC": -2}) == 30
        # EXEC=-4 → 50 + (-4-2)*5 = 20 → clamped to 30
        assert calculate_inventory_capacity({"EXEC": -4}) == 30

    def test_capacity_missing_exec(self) -> None:
        # default EXEC=2
        assert calculate_inventory_capacity({}) == 50

    def test_current_bulk(self) -> None:
        assert calculate_current_bulk([3, 2, 1, 4]) == 10
        assert calculate_current_bulk([]) == 0

    def test_can_add_item_yes(self) -> None:
        assert can_add_item(current_bulk=40, capacity=50, item_bulk=10) is True

    def test_can_add_item_no(self) -> None:
        assert can_add_item(current_bulk=45, capacity=50, item_bulk=6) is False

    def test_can_add_item_exact(self) -> None:
        assert can_add_item(current_bulk=47, capacity=50, item_bulk=3) is True


# ── Durability ────────────────────────────────────────────────


class TestDurability:
    def test_normal_loss(self) -> None:
        proto = _make_proto(max_durability=30, durability_loss_per_use=2)
        inst = _make_instance(current_durability=30)
        result = apply_durability_loss(inst, proto)
        assert result["broken"] is False
        assert result["new_durability"] == 28
        assert inst.current_durability == 28

    def test_broken_with_result(self) -> None:
        proto = _make_proto(
            max_durability=10,
            durability_loss_per_use=5,
            broken_result="mat_iron_scrap",
        )
        inst = _make_instance(current_durability=3)
        result = apply_durability_loss(inst, proto)
        assert result["broken"] is True
        assert result["new_durability"] == 0
        assert result["broken_result"] == "mat_iron_scrap"
        assert inst.current_durability == 0

    def test_broken_no_result_vanish(self) -> None:
        proto = _make_proto(
            max_durability=10,
            durability_loss_per_use=5,
            broken_result=None,
        )
        inst = _make_instance(current_durability=2)
        result = apply_durability_loss(inst, proto)
        assert result["broken"] is True
        assert result["broken_result"] is None

    def test_indestructible(self) -> None:
        proto = _make_proto(max_durability=0, durability_loss_per_use=0)
        inst = _make_instance(current_durability=0)
        result = apply_durability_loss(inst, proto)
        assert result["broken"] is False
        assert result["new_durability"] == 0

    def test_ratio_normal(self) -> None:
        proto = _make_proto(max_durability=30)
        inst = _make_instance(current_durability=15)
        assert get_durability_ratio(inst, proto) == pytest.approx(0.5)

    def test_ratio_indestructible(self) -> None:
        proto = _make_proto(max_durability=0)
        inst = _make_instance(current_durability=0)
        assert get_durability_ratio(inst, proto) == 1.0


# ── Trade ─────────────────────────────────────────────────────


class TestTrade:
    def test_buy_price_basic(self) -> None:
        # base_value=100, buy, stranger, hexaco_h=0.5, full durability
        price = calculate_trade_price(100, "stranger", True, 0.5, 1.0)
        assert price == 150  # 100 * 1.5

    def test_sell_price_basic(self) -> None:
        price = calculate_trade_price(100, "stranger", False, 0.5, 1.0)
        assert price == 50  # 100 * 0.5

    def test_friend_discount(self) -> None:
        price_friend = calculate_trade_price(100, "friend", True, 0.5, 1.0)
        price_nemesis = calculate_trade_price(100, "nemesis", True, 0.5, 1.0)
        assert price_friend < price_nemesis

    def test_hexaco_h_bonus(self) -> None:
        # H >= 0.7 → 0.9x
        price_honest = calculate_trade_price(100, "stranger", True, 0.8, 1.0)
        # H <= 0.3 → 1.2x
        price_selfish = calculate_trade_price(100, "stranger", True, 0.2, 1.0)
        assert price_honest < price_selfish

    def test_durability_affects_price(self) -> None:
        price_full = calculate_trade_price(100, "stranger", True, 0.5, 1.0)
        price_half = calculate_trade_price(100, "stranger", True, 0.5, 0.5)
        assert price_half < price_full

    def test_minimum_price(self) -> None:
        # Very low base_value should still be >= 1
        price = calculate_trade_price(1, "stranger", False, 0.5, 0.3)
        assert price >= 1

    def test_haggle_accept(self) -> None:
        # High A, proposed >= 70% of calculated
        result = evaluate_haggle(80, 100, "stranger", 0.8)
        assert result == "accept"

    def test_haggle_counter(self) -> None:
        # High A (threshold=0.7), proposed 60% → between 0.55 and 0.7
        result = evaluate_haggle(60, 100, "stranger", 0.8)
        assert result == "counter"

    def test_haggle_reject(self) -> None:
        # High A (threshold=0.7), proposed very low
        result = evaluate_haggle(40, 100, "stranger", 0.8)
        assert result == "reject"

    def test_haggle_low_a(self) -> None:
        # Low A (threshold=0.9), proposed 75% → counter
        result = evaluate_haggle(75, 100, "stranger", 0.1)
        assert result == "counter"

    def test_counter_price(self) -> None:
        assert calculate_counter_price(60, 100) == 80


# ── Gift ──────────────────────────────────────────────────────


class TestGift:
    def test_basic_gift(self) -> None:
        # base_value < 40, no matching tags → just +1
        delta = calculate_gift_affinity(10, ["weapon"], ["healing"])
        assert delta == 1

    def test_value_bonus(self) -> None:
        # base_value >= 100 → +2
        delta = calculate_gift_affinity(100, [], [])
        assert delta == 3  # 1 base + 2 value

    def test_value_bonus_medium(self) -> None:
        # base_value >= 40 → +1
        delta = calculate_gift_affinity(50, [], [])
        assert delta == 2  # 1 base + 1 value

    def test_desire_matching(self) -> None:
        # 2 matching tags
        delta = calculate_gift_affinity(
            10, ["weapon", "iron"], ["weapon", "iron", "bladed"]
        )
        assert delta == 3  # 1 base + 2 matching

    def test_max_clamping(self) -> None:
        # value + matching → could exceed 5
        delta = calculate_gift_affinity(100, ["a", "b", "c", "d"], ["a", "b", "c", "d"])
        assert delta == 5


# ── Constraints ───────────────────────────────────────────────


class TestConstraints:
    def test_build_normal(self) -> None:
        protos = {
            "wpn_sword": _make_proto(
                item_id="wpn_sword",
                axiom_tags={"Scindere": 2, "Ferrum": 1},
            ),
            "tool_torch": _make_proto(
                item_id="tool_torch",
                axiom_tags={"Ignis": 1, "Lux": 1},
            ),
        }
        instances = [
            _make_instance(instance_id="i1", prototype_id="wpn_sword"),
            _make_instance(instance_id="i2", prototype_id="tool_torch"),
        ]
        result = build_item_constraints(instances, protos.get)

        assert "wpn_sword" in result["pc_items"]
        assert "tool_torch" in result["pc_items"]
        assert result["pc_axiom_powers"]["Scindere"] == 2
        assert result["pc_axiom_powers"]["Ferrum"] == 1
        assert result["pc_axiom_powers"]["Ignis"] == 1
        assert result["pc_axiom_powers"]["Lux"] == 1

    def test_build_empty_inventory(self) -> None:
        result = build_item_constraints([], lambda x: None)
        assert result["pc_items"] == []
        assert result["pc_axiom_powers"] == {}

    def test_build_max_power(self) -> None:
        """같은 태그가 여러 아이템에 있으면 최대 강도를 사용"""
        protos = {
            "a": _make_proto(item_id="a", axiom_tags={"Ignis": 1}),
            "b": _make_proto(item_id="b", axiom_tags={"Ignis": 3}),
        }
        instances = [
            _make_instance(instance_id="i1", prototype_id="a"),
            _make_instance(instance_id="i2", prototype_id="b"),
        ]
        result = build_item_constraints(instances, protos.get)
        assert result["pc_axiom_powers"]["Ignis"] == 3
