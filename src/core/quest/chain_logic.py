"""체이닝 관련 로직"""

import logging

from .models import ChainEligibleNPC, Quest

logger = logging.getLogger(__name__)


def match_unborn_npc(
    eligible: ChainEligibleNPC,
    npc_tags: list[str],
    npc_current_node: str,
) -> bool:
    """새로 승격된 NPC가 미생성 연작 NPC와 매칭되는지 판정.

    eligible.ref_type == "unborn"일 때만 의미 있음.
    npc_ref를 role 태그로 해석, npc_tags에 포함 여부 확인.
    node_hint가 있으면 위치도 확인.
    """
    if eligible.ref_type != "unborn":
        return False

    # npc_ref가 NPC의 태그에 포함되어야 함
    if eligible.npc_ref not in npc_tags:
        return False

    # node_hint가 있으면 위치 확인
    if eligible.node_hint and eligible.node_hint != npc_current_node:
        return False

    return True


def build_chain_eligible_npcs(
    quest: Quest,
    seed_tier: int,
) -> list[ChainEligibleNPC]:
    """퀘스트 완료 시 chain_eligible_npcs 자동 생성.

    Tier 3: 의뢰주만 (또는 비어있음)
    Tier 2: 의뢰주 + 관련 NPC 1~2명
    Tier 1: 의뢰주 + 관련 NPC + unborn 태그 1~2개
    """
    result: list[ChainEligibleNPC] = []

    # 의뢰주
    if quest.origin_npc_id:
        result.append(
            ChainEligibleNPC(
                npc_ref=quest.origin_npc_id,
                ref_type="existing",
                reason="quest_giver",
            )
        )

    if seed_tier <= 2:
        # 관련 NPC 추가 (의뢰주 제외)
        related = [
            npc_id for npc_id in quest.related_npc_ids if npc_id != quest.origin_npc_id
        ]
        for npc_id in related[:2]:
            result.append(
                ChainEligibleNPC(
                    npc_ref=npc_id,
                    ref_type="existing",
                    reason="witness",
                )
            )

    if seed_tier <= 1:
        # unborn 태그 추가 (퀘스트 태그 기반)
        for tag in quest.tags[:2]:
            result.append(
                ChainEligibleNPC(
                    npc_ref=tag,
                    ref_type="unborn",
                    reason="foreshadowed",
                )
            )

    return result


def build_chain_context(
    chain_id: str,
    previous_quests: list[Quest],
    unresolved_threads: list[str],
    pc_tendency: dict,
    is_finale: bool,
    seed_tier: int,
) -> dict:
    """LLM에 전달할 체이닝 컨텍스트 빌드."""
    previous_summaries = []
    for q in previous_quests:
        previous_summaries.append(
            {
                "quest_id": q.quest_id,
                "title": q.title,
                "result": q.result,
                "resolution_method": q.resolution_method_tag,
            }
        )

    return {
        "chain_context": {
            "chain_id": chain_id,
            "chain_length": len(previous_quests),
            "previous_quests": previous_summaries,
            "unresolved_threads": unresolved_threads,
            "pc_tendency": pc_tendency,
            "is_finale": is_finale,
            "seed_tier": seed_tier,
        }
    }
