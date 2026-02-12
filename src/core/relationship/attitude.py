"""NPC → PC 태도 태그 생성 파이프라인

relationship-system.md 섹션 6 대응.
3단계: 관계 수치 → HEXACO 보정 → 기억 보정
"""

import operator
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.npc.models import HEXACO
from src.core.relationship.models import AttitudeContext, Relationship

# ── 1단계: affinity 구간별 태그 매핑 (섹션 6.2, 5구간) ──────
# (threshold, tag) — 위에서 아래로 평가, 첫 매치 반환
# threshold >= 0 → affinity >= threshold
# threshold < 0  → affinity > threshold
AFFINITY_ATTITUDE_MAP: List[Tuple[float, str]] = [
    (50.0, "warm"),
    (20.0, "friendly"),
    (-20.0, "neutral"),
    (-50.0, "cold"),
]
_AFFINITY_DEFAULT = "hostile"

# ── 1단계: trust 구간별 태그 매핑 (섹션 6.2, 3구간) ─────────
TRUST_ATTITUDE_MAP: List[Tuple[float, str]] = [
    (60.0, "trusting"),
    (30.0, "cautious_trust"),
]
_TRUST_DEFAULT = "distrustful"

# ── 2단계: HEXACO 보정 규칙 8개 (섹션 6.3) ──────────────────
# (factor, threshold, condition_field, condition_op, condition_value, tag)
# factor threshold 규약: <= 0.5 → factor_value <= threshold, > 0.5 → factor_value >= threshold
HEXACO_ATTITUDE_RULES: List[Tuple[str, float, str, str, Any, str]] = [
    ("H", 0.3, "affinity", ">", 0, "calculating"),
    ("E", 0.7, "affinity", "<", 0, "anxious_around_pc"),
    ("X", 0.7, "familiarity", ">=", 5, "chatty"),
    ("X", 0.3, "familiarity", "<", 10, "reserved"),
    ("A", 0.7, "trust", "<", 30, "forgiving_but_wary"),
    ("A", 0.3, "affinity", "<", 0, "confrontational"),
    ("C", 0.7, "memory_tags", "contains", "paid_on_time", "respects_reliability"),
    ("O", 0.7, "familiarity", ">=", 3, "curious_about_pc"),
]

# ── 3단계: 기억 태그 → 태도 태그 (섹션 6.4, 6개 매핑) ──────
MEMORY_ATTITUDE_MAP: Dict[str, str] = {
    "broke_promise": "remembers_betrayal",
    "saved_life": "deeply_grateful",
    "paid_on_time": "reliable_customer",
    "stole_from_me": "watches_belongings",
    "fought_together": "battle_bond",
    "shared_secret": "confidant",
}

# paid_on_time은 반복(2회 이상) 필요
_MEMORY_REPEAT_REQUIRED: Dict[str, int] = {
    "paid_on_time": 2,
}

# ── 비교 연산자 ──────────────────────────────────────────────
_COMPARE_OPS: Dict[str, Callable[..., bool]] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "contains": lambda lst, val: val in (lst or []),
}

# ── 태그 수 제한 ─────────────────────────────────────────────
_MIN_TAGS = 2
_MAX_TAGS = 7


def _match_affinity_tag(affinity: float) -> str:
    """affinity 구간 매칭."""
    for threshold, tag in AFFINITY_ATTITUDE_MAP:
        if threshold >= 0 and affinity >= threshold:
            return tag
        if threshold < 0 and affinity > threshold:
            return tag
    return _AFFINITY_DEFAULT


def _match_trust_tag(trust: float) -> str:
    """trust 구간 매칭."""
    for threshold, tag in TRUST_ATTITUDE_MAP:
        if trust >= threshold:
            return tag
    return _TRUST_DEFAULT


def generate_base_attitude(relationship: Relationship) -> List[str]:
    """1단계: 관계 수치 → 기본 태도 태그 (섹션 6.2)"""
    return [
        _match_affinity_tag(relationship.affinity),
        _match_trust_tag(relationship.trust),
    ]


def apply_hexaco_modifiers(
    tags: List[str],
    hexaco: HEXACO,
    relationship: Relationship,
    memory_tags: Optional[List[str]] = None,
) -> List[str]:
    """2단계: HEXACO 성격 보정 태그 추가 (섹션 6.3)"""
    result = list(tags)
    hexaco_dict = hexaco.to_dict()

    for (
        factor,
        threshold,
        cond_field,
        cond_op,
        cond_value,
        tag,
    ) in HEXACO_ATTITUDE_RULES:
        factor_value = hexaco_dict[factor]

        # factor threshold 비교
        if threshold <= 0.5:
            if factor_value > threshold:
                continue
        else:
            if factor_value < threshold:
                continue

        # condition 비교
        if cond_field == "memory_tags":
            field_value: Any = memory_tags or []
        else:
            field_value = getattr(relationship, cond_field)

        compare_fn = _COMPARE_OPS[cond_op]
        if not compare_fn(field_value, cond_value):
            continue

        result.append(tag)

    return result


def apply_memory_modifiers(
    tags: List[str],
    memory_tags: List[str],
) -> List[str]:
    """3단계: 기억 태그 보정. 중복 태그 제거. (섹션 6.4)"""
    result = list(tags)
    counts = Counter(memory_tags)

    for mem_tag, attitude_tag in MEMORY_ATTITUDE_MAP.items():
        min_count = _MEMORY_REPEAT_REQUIRED.get(mem_tag, 1)
        if counts.get(mem_tag, 0) >= min_count:
            result.append(attitude_tag)

    # 중복 제거 (순서 유지)
    seen: set = set()
    deduped: List[str] = []
    for t in result:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    return deduped


def generate_attitude_tags(
    relationship: Relationship,
    hexaco: HEXACO,
    memory_tags: List[str],
) -> AttitudeContext:
    """전체 파이프라인 실행. 태그 수 2~7 클램프. (섹션 6.1)"""
    # 1단계
    tags = generate_base_attitude(relationship)
    # 2단계
    tags = apply_hexaco_modifiers(tags, hexaco, relationship, memory_tags)
    # 3단계
    tags = apply_memory_modifiers(tags, memory_tags)

    # 클램프 (최대 7개)
    if len(tags) > _MAX_TAGS:
        tags = tags[:_MAX_TAGS]

    return AttitudeContext(
        target_npc_id=relationship.target_id,
        attitude_tags=tags,
        relationship_status=relationship.status.value,
        npc_opinions={},
    )
