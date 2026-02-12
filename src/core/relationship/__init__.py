"""관계 시스템 Core 패키지 — 공개 API"""

from src.core.relationship.models import (
    AttitudeContext,
    Relationship,
    RelationshipStatus,
)
from src.core.relationship.calculations import (
    apply_affinity_damping,
    apply_familiarity_decay,
    apply_trust_damping,
    clamp_affinity,
    clamp_meta_delta,
    clamp_trust,
)
from src.core.relationship.transitions import (
    TRANSITION_TABLE,
    evaluate_transition,
)
from src.core.relationship.reversals import (
    ReversalType,
    apply_reversal,
)
from src.core.relationship.attitude import (
    generate_attitude_tags,
    generate_base_attitude,
    apply_hexaco_modifiers,
    apply_memory_modifiers,
)
from src.core.relationship.npc_opinions import (
    build_npc_opinions,
    generate_npc_opinion_tags,
)

__all__ = [
    "AttitudeContext",
    "Relationship",
    "RelationshipStatus",
    "apply_affinity_damping",
    "apply_familiarity_decay",
    "apply_trust_damping",
    "clamp_affinity",
    "clamp_meta_delta",
    "clamp_trust",
    "TRANSITION_TABLE",
    "evaluate_transition",
    "ReversalType",
    "apply_reversal",
    "generate_attitude_tags",
    "generate_base_attitude",
    "apply_hexaco_modifiers",
    "apply_memory_modifiers",
    "build_npc_opinions",
    "generate_npc_opinion_tags",
]
