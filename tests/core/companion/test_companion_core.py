"""Companion Core 테스트 — models, acceptance, conditions, return_logic

instruction-13 #13-A 대응. 최소 20개 테스트.
"""

import pytest

from src.core.companion.models import CompanionState
from src.core.companion.acceptance import (
    QUEST_COMPANION_ACCEPT_BASE,
    quest_companion_accept_chance,
    roll_quest_companion,
    voluntary_companion_accept,
)
from src.core.companion.conditions import (
    roll_condition,
    generate_condition_data,
    check_condition_expired,
)
from src.core.companion.return_logic import determine_return_destination


# ── models ──────────────────────────────────────────────


class TestCompanionState:
    def test_creation_with_required_fields(self) -> None:
        state = CompanionState(
            companion_id="c1",
            player_id="p1",
            npc_id="npc1",
        )
        assert state.companion_id == "c1"
        assert state.player_id == "p1"
        assert state.npc_id == "npc1"

    def test_default_values(self) -> None:
        state = CompanionState(
            companion_id="c1",
            player_id="p1",
            npc_id="npc1",
        )
        assert state.companion_type == "voluntary"
        assert state.quest_id is None
        assert state.status == "active"
        assert state.started_turn == 0
        assert state.ended_turn is None
        assert state.disband_reason is None
        assert state.condition_type is None
        assert state.condition_data is None
        assert state.condition_met is False
        assert state.origin_node_id == ""
        assert state.created_at == ""


# ── acceptance ──────────────────────────────────────────


class TestQuestCompanionAcceptance:
    def test_base_chance_90_percent(self) -> None:
        chance = quest_companion_accept_chance(npc_hexaco_a=0.5)
        assert chance == pytest.approx(QUEST_COMPANION_ACCEPT_BASE)

    def test_rescue_98_percent(self) -> None:
        chance = quest_companion_accept_chance(npc_hexaco_a=0.5, is_rescue=True)
        assert chance == pytest.approx(0.98)

    def test_low_agreeableness_reduces_chance(self) -> None:
        chance = quest_companion_accept_chance(npc_hexaco_a=0.1)
        assert chance == pytest.approx(0.80)

    def test_rescue_low_a_still_high(self) -> None:
        chance = quest_companion_accept_chance(npc_hexaco_a=0.1, is_rescue=True)
        assert chance == pytest.approx(0.88)

    def test_max_capped_at_99(self) -> None:
        chance = quest_companion_accept_chance(npc_hexaco_a=1.0, is_rescue=True)
        assert chance <= 0.99

    def test_roll_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.0)
        assert roll_quest_companion(npc_hexaco_a=0.5) is True

    def test_roll_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.99)
        assert roll_quest_companion(npc_hexaco_a=0.5) is False


class TestVoluntaryCompanionAcceptance:
    def test_stranger_always_rejected(self) -> None:
        accepted, reason = voluntary_companion_accept(
            "stranger", trust=50, npc_hexaco={"X": 0.5}
        )
        assert accepted is False
        assert reason == "insufficient_relationship"

    def test_rival_always_rejected(self) -> None:
        accepted, reason = voluntary_companion_accept(
            "rival", trust=50, npc_hexaco={"X": 0.5}
        )
        assert accepted is False
        assert reason == "insufficient_relationship"

    def test_friend_high_trust_high_chance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # base=0.50 + trust(60)=+0.15 = 0.65
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.60)
        accepted, reason = voluntary_companion_accept(
            "friend", trust=60, npc_hexaco={"X": 0.5, "E": 0.5, "C": 0.5}
        )
        assert accepted is True
        assert reason is None

    def test_friend_low_trust_reduced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # base=0.50 + trust(10)=-0.15 = 0.35
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.36)
        accepted, reason = voluntary_companion_accept(
            "friend", trust=10, npc_hexaco={"X": 0.5, "E": 0.5, "C": 0.5}
        )
        assert accepted is False
        assert reason == "personality_reluctance"

    def test_bonded_high_chance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # base=0.85 + trust(60)=+0.15 = capped at 0.95
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.90)
        accepted, reason = voluntary_companion_accept(
            "bonded", trust=60, npc_hexaco={"X": 0.5, "E": 0.5, "C": 0.5}
        )
        assert accepted is True

    def test_personality_x_boost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # base=0.50 + X(0.8)=+0.10 = 0.60
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.55)
        accepted, _ = voluntary_companion_accept(
            "friend", trust=30, npc_hexaco={"X": 0.8, "E": 0.5, "C": 0.5}
        )
        assert accepted is True

    def test_personality_e_danger_penalty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # base=0.50, E(0.8) with danger=1.0: -0.20, = 0.30
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.31)
        accepted, _ = voluntary_companion_accept(
            "friend",
            trust=30,
            npc_hexaco={"X": 0.5, "E": 0.8, "C": 0.5},
            pc_destination_danger=1.0,
        )
        assert accepted is False

    def test_personality_c_penalty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # base=0.50 - C(0.8)=0.10 = 0.40
        monkeypatch.setattr("src.core.companion.acceptance.random.random", lambda: 0.41)
        accepted, _ = voluntary_companion_accept(
            "friend", trust=30, npc_hexaco={"X": 0.5, "E": 0.5, "C": 0.8}
        )
        assert accepted is False


# ── conditions ──────────────────────────────────────────


class TestConditions:
    def test_roll_condition_40_percent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.companion.conditions.random.random", lambda: 0.30)
        has_cond, cond_type = roll_condition()
        assert has_cond is True
        assert cond_type is not None

    def test_roll_condition_no_condition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.core.companion.conditions.random.random", lambda: 0.50)
        has_cond, cond_type = roll_condition()
        assert has_cond is False
        assert cond_type is None

    def test_generate_time_limit_data(self) -> None:
        data = generate_condition_data("time_limit")
        assert "turn_limit" in data
        assert 20 <= data["turn_limit"] <= 40

    def test_generate_payment_data(self) -> None:
        data = generate_condition_data("payment")
        assert "amount" in data
        assert 30 <= data["amount"] <= 80

    def test_generate_safety_guarantee_data(self) -> None:
        data = generate_condition_data("safety_guarantee")
        assert data["danger_threshold"] == pytest.approx(0.7)
        assert data["warned"] is False

    def test_generate_destination_only_data(self) -> None:
        data = generate_condition_data("destination_only")
        assert data["destination"] == ""

    def test_generate_item_request_data(self) -> None:
        data = generate_condition_data("item_request")
        assert data["item_id"] == ""

    def test_check_time_limit_expired(self) -> None:
        expired, warned = check_condition_expired(
            "time_limit",
            {"turn_limit": 30},
            started_turn=10,
            current_turn=40,
            pc_node="1_1",
        )
        assert expired is True

    def test_check_time_limit_not_expired(self) -> None:
        expired, warned = check_condition_expired(
            "time_limit",
            {"turn_limit": 30},
            started_turn=10,
            current_turn=30,
            pc_node="1_1",
        )
        assert expired is False

    def test_check_safety_warn_then_expire(self) -> None:
        # First call: not warned yet → warn
        expired1, warned1 = check_condition_expired(
            "safety_guarantee",
            {"danger_threshold": 0.7, "warned": False},
            started_turn=0,
            current_turn=10,
            pc_node="1_1",
            node_danger=0.8,
        )
        assert expired1 is False
        assert warned1 is True

        # Second call: warned → expire
        expired2, warned2 = check_condition_expired(
            "safety_guarantee",
            {"danger_threshold": 0.7, "warned": True},
            started_turn=0,
            current_turn=11,
            pc_node="1_1",
            node_danger=0.8,
        )
        assert expired2 is True
        assert warned2 is True

    def test_check_destination_only_expired(self) -> None:
        expired, _ = check_condition_expired(
            "destination_only",
            {"destination": "5_3"},
            started_turn=0,
            current_turn=10,
            pc_node="5_3",
        )
        assert expired is True

    def test_check_destination_only_not_expired(self) -> None:
        expired, _ = check_condition_expired(
            "destination_only",
            {"destination": "5_3"},
            started_turn=0,
            current_turn=10,
            pc_node="3_3",
        )
        assert expired is False


# ── return_logic ────────────────────────────────────────


class TestReturnLogic:
    def test_escort_complete_stays(self) -> None:
        dest = determine_return_destination(
            npc_home_node="1_1",
            disband_reason="quest_complete",
            quest_type="escort",
            client_npc_node="2_2",
        )
        assert dest is None

    def test_quest_complete_returns_to_client(self) -> None:
        dest = determine_return_destination(
            npc_home_node="1_1",
            disband_reason="quest_complete",
            quest_type="rescue",
            client_npc_node="3_3",
        )
        assert dest == "3_3"

    def test_resident_returns_home(self) -> None:
        dest = determine_return_destination(
            npc_home_node="1_1",
            disband_reason="pc_dismiss",
            quest_type=None,
            client_npc_node=None,
        )
        assert dest == "1_1"

    def test_wanderer_stays(self) -> None:
        dest = determine_return_destination(
            npc_home_node=None,
            disband_reason="pc_dismiss",
            quest_type=None,
            client_npc_node=None,
        )
        assert dest is None

    def test_quest_failed_returns_to_client(self) -> None:
        dest = determine_return_destination(
            npc_home_node="1_1",
            disband_reason="quest_failed",
            quest_type="escort",
            client_npc_node="2_2",
        )
        assert dest == "2_2"
