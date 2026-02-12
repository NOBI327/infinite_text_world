"""반전 이벤트 처리

relationship-system.md 섹션 5 대응.
"""

import copy
from enum import Enum

from src.core.relationship.calculations import clamp_affinity, clamp_trust
from src.core.relationship.models import Relationship
from src.core.relationship.transitions import evaluate_transition


class ReversalType(str, Enum):
    """반전 유형 (섹션 5.1)"""

    BETRAYAL = "betrayal"
    REDEMPTION = "redemption"
    TRUST_COLLAPSE = "trust_collapse"


def apply_reversal(
    relationship: Relationship, reversal_type: ReversalType
) -> Relationship:
    """반전 공식 적용 (섹션 5.1).

    새 Relationship 반환 (원본 불변).
    반전 후 상태도 재계산 (evaluate_transition 호출).
    """
    result = copy.deepcopy(relationship)

    if reversal_type == ReversalType.BETRAYAL:
        result.affinity = clamp_affinity(-result.affinity)
        result.trust = clamp_trust(result.trust * 0.3)
    elif reversal_type == ReversalType.REDEMPTION:
        result.affinity = clamp_affinity(-result.affinity * 0.7)
        result.trust = clamp_trust(result.trust + 30)
    elif reversal_type == ReversalType.TRUST_COLLAPSE:
        result.trust = clamp_trust(result.trust * 0.2)

    new_status = evaluate_transition(result)
    if new_status is not None:
        result.status = new_status

    return result
