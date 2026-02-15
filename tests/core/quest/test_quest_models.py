"""Quest Core 모델 + 열거형 + 확률 판정 테스트 (#12-A)"""

import random

from src.core.quest.enums import (
    ObjectiveStatus,
    ObjectiveType,
    QuestResult,
    QuestStatus,
    QuestType,
    SeedStatus,
    SeedType,
    Urgency,
)
from src.core.quest.models import (
    ChainEligibleNPC,
    Objective,
    Quest,
    QuestRewards,
    QuestSeed,
    RelationshipDelta,
    WorldChange,
)
from src.core.quest.probability import (
    can_generate_seed,
    determine_seed_tier,
    get_default_ttl,
    roll_chain_chance,
    roll_seed_chance,
    should_finalize_chain,
)


class TestQuestModels:
    """도메인 모델 생성 테스트"""

    def test_quest_seed_creation(self):
        seed = QuestSeed(
            seed_id="seed_001",
            npc_id="npc_001",
            seed_type="personal",
            seed_tier=2,
            created_turn=10,
            ttl_turns=15,
            context_tags=["merchant", "worried"],
        )
        assert seed.seed_id == "seed_001"
        assert seed.npc_id == "npc_001"
        assert seed.seed_type == "personal"
        assert seed.seed_tier == 2
        assert seed.created_turn == 10
        assert seed.ttl_turns == 15
        assert seed.status == "active"
        assert seed.context_tags == ["merchant", "worried"]
        assert seed.chain_id is None
        assert seed.unresolved_threads == []

    def test_quest_creation(self):
        quest = Quest(
            quest_id="q_001",
            title="Test Quest",
            description="A test quest",
            quest_type="deliver",
            seed_tier=3,
            activated_turn=5,
            related_npc_ids=["npc_001", "npc_002"],
        )
        assert quest.quest_id == "q_001"
        assert quest.title == "Test Quest"
        assert quest.origin_type == "conversation"
        assert quest.status == "active"
        assert quest.result is None
        assert quest.chain_id is None
        assert quest.chain_index == 0
        assert quest.is_chain_finale is False
        assert quest.related_npc_ids == ["npc_001", "npc_002"]
        assert quest.target_node_ids == []
        assert quest.rewards is None
        assert quest.tags == []

    def test_objective_creation(self):
        obj = Objective(
            objective_id="obj_001",
            quest_id="q_001",
            description="Deliver the item",
            objective_type="deliver",
            target={"item_id": "sword_001", "target_npc": "npc_002"},
        )
        assert obj.objective_id == "obj_001"
        assert obj.quest_id == "q_001"
        assert obj.objective_type == "deliver"
        assert obj.status == "active"
        assert obj.completed_turn is None
        assert obj.failed_turn is None
        assert obj.is_replacement is False
        assert obj.replaced_objective_id is None

    def test_chain_eligible_npc_creation(self):
        eligible = ChainEligibleNPC(
            npc_ref="innkeeper",
            ref_type="unborn",
            node_hint="town_square",
            reason="quest_giver",
        )
        assert eligible.npc_ref == "innkeeper"
        assert eligible.ref_type == "unborn"
        assert eligible.node_hint == "town_square"
        assert eligible.reason == "quest_giver"

    def test_quest_rewards_creation(self):
        rewards = QuestRewards(
            relationship_deltas={
                "npc_001": RelationshipDelta(
                    affinity=10, trust=15, reason="quest_success"
                )
            },
            items=["gold_coin"],
            experience=100,
        )
        assert "npc_001" in rewards.relationship_deltas
        assert rewards.relationship_deltas["npc_001"].affinity == 10
        assert rewards.items == ["gold_coin"]
        assert rewards.experience == 100
        assert rewards.world_changes == []

    def test_world_change_creation(self):
        change = WorldChange(
            node_id="node_001",
            change_type="tag_add",
            data={"tag": "liberated"},
        )
        assert change.node_id == "node_001"
        assert change.change_type == "tag_add"
        assert change.data == {"tag": "liberated"}

    def test_relationship_delta_creation(self):
        delta = RelationshipDelta(affinity=5, trust=-3, reason="betrayal")
        assert delta.affinity == 5
        assert delta.trust == -3
        assert delta.familiarity == 0
        assert delta.reason == "betrayal"


class TestEnums:
    """열거형 테스트"""

    def test_quest_type_values(self):
        assert QuestType.DELIVER.value == "deliver"
        assert QuestType.ESCORT.value == "escort"
        assert QuestType.INVESTIGATE.value == "investigate"
        assert QuestType.RESOLVE.value == "resolve"
        assert QuestType.NEGOTIATE.value == "negotiate"
        assert QuestType.BOND.value == "bond"
        assert QuestType.RIVALRY.value == "rivalry"
        assert len(QuestType) == 7

    def test_objective_type_values(self):
        assert ObjectiveType.REACH_NODE.value == "reach_node"
        assert ObjectiveType.DELIVER.value == "deliver"
        assert ObjectiveType.ESCORT.value == "escort"
        assert ObjectiveType.TALK_TO_NPC.value == "talk_to_npc"
        assert ObjectiveType.RESOLVE_CHECK.value == "resolve_check"
        assert len(ObjectiveType) == 5

    def test_quest_status_and_seed_status(self):
        assert QuestStatus.ACTIVE.value == "active"
        assert QuestStatus.COMPLETED.value == "completed"
        assert QuestStatus.FAILED.value == "failed"
        assert QuestStatus.ABANDONED.value == "abandoned"
        assert len(QuestStatus) == 4

        assert SeedStatus.ACTIVE.value == "active"
        assert SeedStatus.ACCEPTED.value == "accepted"
        assert SeedStatus.EXPIRED.value == "expired"
        assert SeedStatus.RESOLVED_OFFSCREEN.value == "resolved_offscreen"
        assert len(SeedStatus) == 4

    def test_quest_result_enum(self):
        assert QuestResult.SUCCESS.value == "success"
        assert QuestResult.PARTIAL.value == "partial"
        assert QuestResult.FAILURE.value == "failure"
        assert QuestResult.ABANDONED.value == "abandoned"

    def test_objective_status_enum(self):
        assert ObjectiveStatus.ACTIVE.value == "active"
        assert ObjectiveStatus.COMPLETED.value == "completed"
        assert ObjectiveStatus.FAILED.value == "failed"

    def test_seed_type_enum(self):
        assert SeedType.PERSONAL.value == "personal"
        assert SeedType.RUMOR.value == "rumor"
        assert SeedType.REQUEST.value == "request"
        assert SeedType.WARNING.value == "warning"
        assert len(SeedType) == 4

    def test_urgency_enum(self):
        assert Urgency.NORMAL.value == "normal"
        assert Urgency.URGENT.value == "urgent"


class TestProbability:
    """확률 판정 테스트"""

    def test_determine_seed_tier_returns_valid_tiers(self):
        tiers = {determine_seed_tier() for _ in range(100)}
        assert tiers.issubset({1, 2, 3})

    def test_roll_seed_chance_roughly_5_percent(self):
        random.seed(42)
        results = [roll_seed_chance() for _ in range(1000)]
        rate = sum(results) / len(results)
        assert 0.02 <= rate <= 0.08, f"Expected ~5%, got {rate:.1%}"

    def test_roll_chain_chance_tier_difference(self):
        random.seed(42)
        tier1_results = [roll_chain_chance(1) for _ in range(500)]
        tier3_results = [roll_chain_chance(3) for _ in range(500)]
        tier1_rate = sum(tier1_results) / len(tier1_results)
        tier3_rate = sum(tier3_results) / len(tier3_results)
        assert (
            tier1_rate > tier3_rate
        ), f"Tier 1 ({tier1_rate:.1%}) should be higher than Tier 3 ({tier3_rate:.1%})"

    def test_should_finalize_chain_length_1_always_false(self):
        for _ in range(100):
            assert should_finalize_chain(1) is False

    def test_should_finalize_chain_length_6_mostly_true(self):
        random.seed(42)
        results = [should_finalize_chain(6) for _ in range(100)]
        rate = sum(results) / len(results)
        assert rate >= 0.85, f"Expected ~95% for length 6, got {rate:.1%}"

    def test_can_generate_seed_cooldown_not_met(self):
        assert can_generate_seed(10, 12) is False  # 2 < 5

    def test_can_generate_seed_cooldown_met(self):
        assert can_generate_seed(10, 15) is True  # 5 >= 5

    def test_can_generate_seed_none_means_first_time(self):
        assert can_generate_seed(None, 0) is True

    def test_get_default_ttl_known_types(self):
        assert get_default_ttl("personal") == 15
        assert get_default_ttl("rumor") == 30
        assert get_default_ttl("request") == 20
        assert get_default_ttl("warning") == 10

    def test_get_default_ttl_unknown_type(self):
        assert get_default_ttl("unknown") == 20
