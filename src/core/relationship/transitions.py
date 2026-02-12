"""관계 상태 전이 판정

relationship-system.md 섹션 3, 9.4 대응.
"""

from typing import Optional

from src.core.relationship.models import Relationship, RelationshipStatus

TRANSITION_TABLE = {
    RelationshipStatus.STRANGER: {
        "promote": lambda r: r.familiarity >= 3,
        "promote_to": RelationshipStatus.ACQUAINTANCE,
    },
    RelationshipStatus.ACQUAINTANCE: {
        "promote": lambda r: r.affinity >= 30 and r.trust >= 25,
        "promote_to": RelationshipStatus.FRIEND,
        "demote": lambda r: abs(r.affinity) < 10 and r.familiarity < 3,
        "demote_to": RelationshipStatus.STRANGER,
        "rival": lambda r: r.affinity <= -25 and r.familiarity >= 5,
        "rival_to": RelationshipStatus.RIVAL,
    },
    RelationshipStatus.FRIEND: {
        "promote": lambda r: r.affinity >= 65 and r.trust >= 60 and r.familiarity >= 20,
        "promote_to": RelationshipStatus.BONDED,
        "demote": lambda r: r.affinity < 15 or r.trust < 10,
        "demote_to": RelationshipStatus.ACQUAINTANCE,
    },
    RelationshipStatus.BONDED: {
        "demote": lambda r: r.affinity < 40 or r.trust < 30,
        "demote_to": RelationshipStatus.FRIEND,
    },
    RelationshipStatus.RIVAL: {
        "demote": lambda r: r.affinity > -10,
        "demote_to": RelationshipStatus.ACQUAINTANCE,
        "promote": lambda r: r.affinity <= -55 and r.trust <= 15,
        "promote_to": RelationshipStatus.NEMESIS,
    },
    RelationshipStatus.NEMESIS: {
        "demote": lambda r: r.affinity > -30 or r.trust > 30,
        "demote_to": RelationshipStatus.RIVAL,
    },
}


def evaluate_transition(
    relationship: Relationship,
) -> Optional[RelationshipStatus]:
    """현재 상태에서 전이 가능 여부 확인.

    판정 우선순위: demote → rival → promote.
    여러 조건 충족 시 하락이 우선.
    변경이 필요하면 새 상태 반환, 아니면 None.
    """
    entry = TRANSITION_TABLE.get(relationship.status)
    if entry is None:
        return None

    # demote 우선
    demote_fn = entry.get("demote")
    if demote_fn is not None and demote_fn(relationship):
        return entry["demote_to"]

    # rival
    rival_fn = entry.get("rival")
    if rival_fn is not None and rival_fn(relationship):
        return entry["rival_to"]

    # promote
    promote_fn = entry.get("promote")
    if promote_fn is not None and promote_fn(relationship):
        return entry["promote_to"]

    return None
