"""Quest Core 로직 테스트 (#12-B) — seed, result, objective, chain"""

import random
from unittest.mock import patch

from src.core.quest.chain_logic import (
    build_chain_context,
    build_chain_eligible_npcs,
    match_unborn_npc,
)
from src.core.quest.models import ChainEligibleNPC, Objective, Quest, QuestSeed
from src.core.quest.objective_logic import (
    create_fallback_objectives,
    generate_replacement_objectives,
    map_hint_to_objective_type,
    validate_objectives_hint,
)
from src.core.quest.result_logic import (
    calculate_pc_tendency,
    calculate_rewards,
    evaluate_quest_result,
)
from src.core.quest.seed_logic import (
    process_seed_ttl,
    select_seed_type,
    try_generate_seed,
)


class TestSeedLogic:
    """시드 생성 + TTL 테스트"""

    def test_try_generate_seed_cooldown_fail(self):
        result = try_generate_seed(
            npc_id="npc_001",
            current_turn=10,
            last_seed_conversation_count=8,
            current_conversation_count=10,  # 2 < 5
        )
        assert result is None

    def test_try_generate_seed_roll_fail(self):
        with patch("src.core.quest.seed_logic.roll_seed_chance", return_value=False):
            result = try_generate_seed(
                npc_id="npc_001",
                current_turn=10,
                last_seed_conversation_count=None,
                current_conversation_count=10,
            )
        assert result is None

    def test_try_generate_seed_success(self):
        with (
            patch("src.core.quest.seed_logic.roll_seed_chance", return_value=True),
            patch("src.core.quest.seed_logic.determine_seed_tier", return_value=2),
            patch("src.core.quest.seed_logic.select_seed_type", return_value="rumor"),
        ):
            result = try_generate_seed(
                npc_id="npc_001",
                current_turn=10,
                last_seed_conversation_count=None,
                current_conversation_count=10,
            )
        assert result is not None
        assert isinstance(result, QuestSeed)
        assert result.npc_id == "npc_001"
        assert result.seed_type == "rumor"
        assert result.seed_tier == 2
        assert result.created_turn == 10
        assert result.chain_id is None

    def test_try_generate_seed_with_chaining(self):
        eligible = [Quest(quest_id="q_done", status="completed")]
        with (
            patch("src.core.quest.seed_logic.roll_seed_chance", return_value=True),
            patch("src.core.quest.seed_logic.determine_seed_tier", return_value=1),
            patch("src.core.quest.seed_logic.roll_chain_chance", return_value=True),
            patch(
                "src.core.quest.seed_logic.select_seed_type", return_value="personal"
            ),
        ):
            result = try_generate_seed(
                npc_id="npc_001",
                current_turn=20,
                last_seed_conversation_count=None,
                current_conversation_count=20,
                eligible_quests=eligible,
            )
        assert result is not None
        assert result.chain_id is not None
        assert result.chain_id.startswith("chain_")

    def test_process_seed_ttl_not_expired(self):
        seed = QuestSeed(
            seed_id="s1",
            npc_id="n1",
            seed_type="rumor",
            seed_tier=3,
            created_turn=10,
            ttl_turns=20,
        )
        assert process_seed_ttl(seed, 25) is False
        assert seed.status == "active"

    def test_process_seed_ttl_expired(self):
        seed = QuestSeed(
            seed_id="s1",
            npc_id="n1",
            seed_type="rumor",
            seed_tier=3,
            created_turn=10,
            ttl_turns=20,
        )
        assert process_seed_ttl(seed, 30) is True
        assert seed.status == "expired"

    def test_select_seed_type_returns_valid(self):
        random.seed(42)
        for _ in range(20):
            t = select_seed_type()
            assert t in ("personal", "rumor", "request", "warning")


class TestResultLogic:
    """결과 판정 + 보상 테스트"""

    def _make_quest(self, **kwargs):
        defaults = {
            "quest_id": "q_001",
            "quest_type": "deliver",
            "seed_tier": 2,
            "origin_npc_id": "npc_001",
            "activated_turn": 0,
        }
        defaults.update(kwargs)
        return Quest(**defaults)

    def _make_obj(self, status="active", is_replacement=False, **kwargs):
        defaults = {
            "objective_id": f"obj_{id(kwargs)}",
            "quest_id": "q_001",
            "description": "test",
            "objective_type": "deliver",
            "status": status,
            "is_replacement": is_replacement,
        }
        defaults.update(kwargs)
        return Objective(**defaults)

    def test_evaluate_all_completed_success(self):
        quest = self._make_quest()
        objs = [
            self._make_obj(status="completed", objective_id="o1"),
            self._make_obj(status="completed", objective_id="o2"),
        ]
        assert evaluate_quest_result(quest, objs, 10) == "success"

    def test_evaluate_partial_with_replacement(self):
        quest = self._make_quest()
        objs = [
            self._make_obj(status="failed", objective_id="o1"),
            self._make_obj(status="completed", is_replacement=True, objective_id="o2"),
        ]
        assert evaluate_quest_result(quest, objs, 10) == "partial"

    def test_evaluate_urgent_time_exceeded(self):
        quest = self._make_quest(urgency="urgent", time_limit=5)
        objs = [self._make_obj(status="active", objective_id="o1")]
        # current_turn=10 > activated_turn(0) + time_limit(5)
        assert evaluate_quest_result(quest, objs, 10) == "failure"

    def test_evaluate_active_remaining_none(self):
        quest = self._make_quest()
        objs = [self._make_obj(status="active", objective_id="o1")]
        assert evaluate_quest_result(quest, objs, 3) is None

    def test_evaluate_all_failed_failure(self):
        quest = self._make_quest()
        objs = [
            self._make_obj(status="failed", objective_id="o1"),
            self._make_obj(status="failed", objective_id="o2"),
        ]
        assert evaluate_quest_result(quest, objs, 10) == "failure"

    def test_calculate_rewards_success(self):
        quest = self._make_quest(seed_tier=1)
        rewards = calculate_rewards(quest, "success")
        assert "npc_001" in rewards.relationship_deltas
        delta = rewards.relationship_deltas["npc_001"]
        assert delta.affinity > 0
        assert delta.trust > 0
        assert rewards.experience == 100

    def test_calculate_rewards_partial(self):
        quest = self._make_quest(seed_tier=2)
        rewards = calculate_rewards(quest, "partial")
        delta = rewards.relationship_deltas["npc_001"]
        assert delta.affinity >= 0
        assert rewards.experience == 25

    def test_calculate_rewards_failure(self):
        quest = self._make_quest(seed_tier=3)
        rewards = calculate_rewards(quest, "failure")
        delta = rewards.relationship_deltas["npc_001"]
        assert delta.trust <= 0
        assert rewards.experience == 0

    def test_calculate_pc_tendency_empty(self):
        result = calculate_pc_tendency([])
        assert result["dominant_style"] == "unknown"
        assert result["recent_methods"] == []
        assert result["impression_tags"] == []

    def test_calculate_pc_tendency_with_methods(self):
        quests = [
            Quest(
                quest_id=f"q_{i}",
                status="completed",
                completed_turn=i,
                resolution_method_tag="axiom_exploit",
                resolution_impression_tag="impressed",
            )
            for i in range(3)
        ]
        result = calculate_pc_tendency(quests)
        assert result["dominant_style"] == "axiom_researcher"
        assert len(result["recent_methods"]) == 3
        assert "impressed" in result["impression_tags"]


class TestObjectiveLogic:
    """목표 관련 로직 테스트"""

    def test_map_hint_valid(self):
        assert map_hint_to_objective_type("find_npc") == "talk_to_npc"
        assert map_hint_to_objective_type("escort_to") == "escort"
        assert map_hint_to_objective_type("fetch_item") == "deliver"
        assert map_hint_to_objective_type("go_to") == "reach_node"

    def test_map_hint_invalid(self):
        assert map_hint_to_objective_type("unknown_hint") is None

    def test_create_fallback_objectives(self):
        objs = create_fallback_objectives("deliver", "q_001")
        assert len(objs) >= 1
        assert objs[0].objective_type == "deliver"
        assert objs[0].quest_id == "q_001"

    def test_generate_replacement_target_dead(self):
        failed = Objective(
            objective_id="obj_f1",
            quest_id="q_001",
            description="호위 대상 보호",
            objective_type="escort",
            status="failed",
            fail_reason="target_dead",
        )
        quest = Quest(quest_id="q_001", origin_npc_id="npc_001")
        context = {"client_npc_id": "npc_001"}

        replacements = generate_replacement_objectives(failed, quest, context)
        # client_consult(1) + target_dead auto_fallbacks(2) = 3
        assert len(replacements) == 3
        assert replacements[0].replacement_origin == "client_consult"
        assert all(r.is_replacement for r in replacements)

    def test_generate_replacement_time_expired(self):
        failed = Objective(
            objective_id="obj_f2",
            quest_id="q_001",
            description="시간 내 도달",
            objective_type="reach_node",
            status="failed",
            fail_reason="time_expired",
        )
        quest = Quest(quest_id="q_001")
        context = {}

        replacements = generate_replacement_objectives(failed, quest, context)
        # client_consult만 (time_expired에는 auto_fallback 없음)
        assert len(replacements) == 1
        assert replacements[0].replacement_origin == "client_consult"

    def test_validate_objectives_hint_valid(self):
        hints = [
            {"hint_type": "find_npc", "description": "NPC를 찾아라", "target": {}},
            {"hint_type": "go_to", "description": "지역 이동", "target": {}},
        ]
        objs = validate_objectives_hint(hints, "investigate", "q_001")
        assert len(objs) == 2
        assert objs[0].objective_type == "talk_to_npc"
        assert objs[1].objective_type == "reach_node"

    def test_validate_objectives_hint_all_fail_fallback(self):
        hints = [
            {"hint_type": "invalid1", "description": "bad"},
            {"hint_type": "invalid2", "description": "bad"},
        ]
        objs = validate_objectives_hint(hints, "deliver", "q_001")
        # All failed → fallback
        assert len(objs) >= 1
        assert objs[0].objective_type == "deliver"


class TestChainLogic:
    """체이닝 로직 테스트"""

    def test_match_unborn_npc_success(self):
        eligible = ChainEligibleNPC(
            npc_ref="innkeeper",
            ref_type="unborn",
            reason="foreshadowed",
        )
        assert match_unborn_npc(eligible, ["innkeeper", "merchant"], "node_1") is True

    def test_match_unborn_npc_tag_mismatch(self):
        eligible = ChainEligibleNPC(
            npc_ref="blacksmith",
            ref_type="unborn",
            reason="foreshadowed",
        )
        assert match_unborn_npc(eligible, ["innkeeper", "merchant"], "node_1") is False

    def test_match_unborn_npc_node_hint_mismatch(self):
        eligible = ChainEligibleNPC(
            npc_ref="innkeeper",
            ref_type="unborn",
            node_hint="town_square",
            reason="foreshadowed",
        )
        assert match_unborn_npc(eligible, ["innkeeper"], "different_node") is False

    def test_build_chain_eligible_tier3(self):
        quest = Quest(
            quest_id="q_001",
            origin_npc_id="npc_001",
            related_npc_ids=["npc_001", "npc_002"],
            tags=["danger", "mystery"],
        )
        result = build_chain_eligible_npcs(quest, seed_tier=3)
        # Tier 3: 의뢰주만
        assert len(result) == 1
        assert result[0].npc_ref == "npc_001"
        assert result[0].reason == "quest_giver"

    def test_build_chain_eligible_tier1(self):
        quest = Quest(
            quest_id="q_001",
            origin_npc_id="npc_001",
            related_npc_ids=["npc_001", "npc_002", "npc_003"],
            tags=["danger", "mystery"],
        )
        result = build_chain_eligible_npcs(quest, seed_tier=1)
        # Tier 1: 의뢰주(1) + related(2) + unborn tags(2) = 5
        assert len(result) == 5
        ref_types = [r.ref_type for r in result]
        assert "existing" in ref_types
        assert "unborn" in ref_types

    def test_build_chain_context(self):
        prev_quests = [
            Quest(
                quest_id="q_prev",
                title="Previous",
                result="success",
                resolution_method_tag="negotiation",
            )
        ]
        ctx = build_chain_context(
            chain_id="chain_001",
            previous_quests=prev_quests,
            unresolved_threads=["thread_1"],
            pc_tendency={"dominant_style": "diplomat"},
            is_finale=False,
            seed_tier=2,
        )
        assert "chain_context" in ctx
        cc = ctx["chain_context"]
        assert cc["chain_id"] == "chain_001"
        assert cc["chain_length"] == 1
        assert cc["is_finale"] is False
        assert cc["seed_tier"] == 2
        assert len(cc["previous_quests"]) == 1
        assert cc["unresolved_threads"] == ["thread_1"]
