"""관계 상태 전이 판정

relationship-system.md 섹션 3, 9.4 대응.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from src.core.relationship.models import Relationship, RelationshipStatus

TransitionCheck = Callable[[Relationship], bool]


@dataclass
class TransitionEntry:
    """상태별 전이 조건."""

    promote: Optional[TransitionCheck] = None
    promote_to: Optional[RelationshipStatus] = None
    demote: Optional[TransitionCheck] = None
    demote_to: Optional[RelationshipStatus] = None
    rival: Optional[TransitionCheck] = None
    rival_to: Optional[RelationshipStatus] = None


TRANSITION_TABLE: Dict[RelationshipStatus, TransitionEntry] = {
    RelationshipStatus.STRANGER: TransitionEntry(
        promote=lambda r: r.familiarity >= 3,
        promote_to=RelationshipStatus.ACQUAINTANCE,
    ),
    RelationshipStatus.ACQUAINTANCE: TransitionEntry(
        promote=lambda r: r.affinity >= 30 and r.trust >= 25,
        promote_to=RelationshipStatus.FRIEND,
        demote=lambda r: abs(r.affinity) < 10 and r.familiarity < 3,
        demote_to=RelationshipStatus.STRANGER,
        rival=lambda r: r.affinity <= -25 and r.familiarity >= 5,
        rival_to=RelationshipStatus.RIVAL,
    ),
    RelationshipStatus.FRIEND: TransitionEntry(
        promote=lambda r: r.affinity >= 65 and r.trust >= 60 and r.familiarity >= 20,
        promote_to=RelationshipStatus.BONDED,
        demote=lambda r: r.affinity < 15 or r.trust < 10,
        demote_to=RelationshipStatus.ACQUAINTANCE,
    ),
    RelationshipStatus.BONDED: TransitionEntry(
        demote=lambda r: r.affinity < 40 or r.trust < 30,
        demote_to=RelationshipStatus.FRIEND,
    ),
    RelationshipStatus.RIVAL: TransitionEntry(
        demote=lambda r: r.affinity > -10,
        demote_to=RelationshipStatus.ACQUAINTANCE,
        promote=lambda r: r.affinity <= -55 and r.trust <= 15,
        promote_to=RelationshipStatus.NEMESIS,
    ),
    RelationshipStatus.NEMESIS: TransitionEntry(
        demote=lambda r: r.affinity > -30 or r.trust > 30,
        demote_to=RelationshipStatus.RIVAL,
    ),
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
    if entry.demote is not None and entry.demote(relationship):
        return entry.demote_to

    # rival
    if entry.rival is not None and entry.rival(relationship):
        return entry.rival_to

    # promote
    if entry.promote is not None and entry.promote(relationship):
        return entry.promote_to

    return None
