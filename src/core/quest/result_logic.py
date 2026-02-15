"""퀘스트 결과 판정 + 보상 계산"""

import logging
from collections import Counter

from .models import Objective, Quest, QuestRewards, RelationshipDelta

logger = logging.getLogger(__name__)

# === 관계 변동 범위 (결과별) ===
REWARD_DELTAS: dict[str, dict[str, tuple[int, int]]] = {
    "success": {"affinity": (5, 15), "trust": (10, 20)},
    "partial": {"affinity": (2, 5), "trust": (0, 0)},
    "failure": {"affinity": (0, 0), "trust": (-10, -5)},
    "abandoned": {"affinity": (-5, -3), "trust": (-15, -10)},
}

# === style_map for PC tendency ===
STYLE_MAP: dict[str, str] = {
    "direct_combat": "brawler",
    "stealth": "infiltrator",
    "negotiation": "diplomat",
    "axiom_exploit": "axiom_researcher",
    "environment_exploit": "tactician",
    "hired_help": "commander",
    "unconventional": "wildcard",
}


def evaluate_quest_result(
    quest: Quest,
    objectives: list[Objective],
    current_turn: int,
) -> str | None:
    """퀘스트 결과 판정.

    Returns:
        "success" | "partial" | "failure" | None(진행 중)
    """
    if not objectives:
        return None

    original = [o for o in objectives if not o.is_replacement]
    replacements = [o for o in objectives if o.is_replacement]

    # 활성 목표가 남아 있으면 진행 중
    all_objectives = original + replacements
    active = [o for o in all_objectives if o.status == "active"]

    # urgent 시간 초과 체크
    if quest.urgency == "urgent" and quest.time_limit is not None:
        if current_turn > quest.activated_turn + quest.time_limit:
            # 시간 초과: 일부 달성이면 partial, 전부 미달이면 failure
            completed_any = any(o.status == "completed" for o in all_objectives)
            return "partial" if completed_any else "failure"

    if active:
        return None

    # 원본 목표 전부 달성 → success
    original_all_completed = all(o.status == "completed" for o in original)
    if original_all_completed:
        return "success"

    # 원본 일부 실패 + 대체 달성 → partial
    original_some_failed = any(o.status == "failed" for o in original)
    replacement_completed = any(o.status == "completed" for o in replacements)
    if original_some_failed and replacement_completed:
        return "partial"

    # 전부 실패
    all_failed = all(o.status == "failed" for o in all_objectives)
    if all_failed:
        return "failure"

    # 원본 실패 + 대체도 실패
    if original_some_failed:
        return "failure"

    return None


def calculate_rewards(
    quest: Quest,
    result: str,
) -> QuestRewards:
    """결과에 따른 보상 계산.

    의뢰 NPC에 대한 관계 변동을 seed_tier에 비례하여 스케일링.
    Tier 1: 범위 상단, Tier 3: 범위 하단.
    """
    deltas = REWARD_DELTAS.get(result, REWARD_DELTAS["failure"])

    # 티어 스케일: 1→1.0(상단), 2→0.6(중간), 3→0.2(하단)
    tier_scale = {1: 1.0, 2: 0.6, 3: 0.2}.get(quest.seed_tier, 0.2)

    aff_range = deltas["affinity"]
    trust_range = deltas["trust"]

    affinity_val = int(aff_range[0] + (aff_range[1] - aff_range[0]) * tier_scale)
    trust_val = int(trust_range[0] + (trust_range[1] - trust_range[0]) * tier_scale)

    relationship_deltas: dict[str, RelationshipDelta] = {}
    if quest.origin_npc_id:
        relationship_deltas[quest.origin_npc_id] = RelationshipDelta(
            affinity=affinity_val,
            trust=trust_val,
            reason=f"quest_{result}",
        )

    # 티어별 경험치
    exp_map = {"success": {1: 100, 2: 50, 3: 20}, "partial": {1: 50, 2: 25, 3: 10}}
    experience = exp_map.get(result, {}).get(quest.seed_tier, 0)

    return QuestRewards(
        relationship_deltas=relationship_deltas,
        experience=experience,
    )


def calculate_pc_tendency(
    completed_quests: list[Quest],
    max_recent: int = 5,
) -> dict:
    """최근 완료 퀘스트에서 PC 경향 산출.

    Returns:
        {
            "recent_methods": [...],
            "dominant_style": "...",
            "impression_tags": [...]
        }
    """
    recent = sorted(
        completed_quests,
        key=lambda q: q.completed_turn or 0,
        reverse=True,
    )[:max_recent]

    methods: list[str] = []
    impression_tags: list[str] = []

    for q in recent:
        if q.resolution_method_tag:
            methods.append(q.resolution_method_tag)
        if q.resolution_impression_tag:
            impression_tags.append(q.resolution_impression_tag)

    # dominant style
    if methods:
        counter = Counter(methods)
        most_common = counter.most_common(1)[0][0]
        dominant_style = STYLE_MAP.get(most_common, "unknown")
    else:
        dominant_style = "unknown"

    return {
        "recent_methods": methods,
        "dominant_style": dominant_style,
        "impression_tags": impression_tags,
    }
