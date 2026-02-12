"""NPC간 관계를 대화용 태그로 변환

relationship-system.md 섹션 7.3 대응.
"""

from typing import Dict, List

from src.core.relationship.models import Relationship


def generate_npc_opinion_tags(relationship: Relationship) -> List[str]:
    """affinity/trust 기반 간단 태그 생성.

    NPC A → NPC B 관계를 대화에서 언급할 때 사용하는 태그.
    "speaks_fondly", "distrustful", "avoids" 등.
    """
    tags: List[str] = []

    # affinity 기반
    if relationship.affinity > 30:
        tags.append("speaks_fondly")
    elif relationship.affinity < -30:
        tags.append("speaks_poorly")

    # trust 기반
    if relationship.trust >= 60:
        tags.append("trusts_deeply")
    elif relationship.trust < 20:
        tags.append("distrustful")

    # 회피/친밀 태그
    if relationship.affinity < -50:
        tags.append("avoids")
    if relationship.familiarity >= 15 and relationship.affinity > 0:
        tags.append("old_friend")

    return tags


def build_npc_opinions(
    source_npc_id: str,
    relationships: List[Relationship],
) -> Dict[str, List[str]]:
    """특정 NPC의 타 NPC에 대한 의견 딕셔너리.

    Args:
        source_npc_id: 의견의 주체 NPC ID
        relationships: source_npc_id → 타 NPC 관계 목록

    Returns:
        {target_npc_id: [opinion_tags]} 딕셔너리. 태그가 없는 관계는 제외.
    """
    opinions: Dict[str, List[str]] = {}

    for rel in relationships:
        if rel.source_id != source_npc_id:
            continue
        tags = generate_npc_opinion_tags(rel)
        if tags:
            opinions[rel.target_id] = tags

    return opinions
