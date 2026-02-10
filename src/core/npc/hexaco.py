"""HEXACO 성격 생성 및 행동 매핑

npc-system.md 섹션 8 대응.
"""

import random
from typing import Any, Dict, Optional

from src.core.npc.models import HEXACO

# ── 역할별 HEXACO 기본값 (섹션 8.3) ─────────────────────────

ROLE_HEXACO_TEMPLATES: Dict[str, Dict[str, float]] = {
    "blacksmith": {"H": 0.6, "E": 0.4, "X": 0.4, "A": 0.5, "C": 0.7, "O": 0.4},
    "merchant": {"H": 0.4, "E": 0.5, "X": 0.7, "A": 0.5, "C": 0.6, "O": 0.5},
    "guard": {"H": 0.6, "E": 0.3, "X": 0.5, "A": 0.4, "C": 0.7, "O": 0.3},
    "innkeeper": {"H": 0.5, "E": 0.5, "X": 0.8, "A": 0.7, "C": 0.5, "O": 0.5},
    "scholar": {"H": 0.7, "E": 0.6, "X": 0.3, "A": 0.5, "C": 0.7, "O": 0.9},
    "bandit": {"H": 0.2, "E": 0.4, "X": 0.5, "A": 0.3, "C": 0.4, "O": 0.4},
    "goblin": {"H": 0.2, "E": 0.6, "X": 0.5, "A": 0.2, "C": 0.3, "O": 0.3},
}

_NEUTRAL_TEMPLATE: Dict[str, float] = {
    "H": 0.5,
    "E": 0.5,
    "X": 0.5,
    "A": 0.5,
    "C": 0.5,
    "O": 0.5,
}

_VARIANCE = 0.15  # ±0.15 랜덤 보정


def generate_hexaco(role: str, seed: Optional[int] = None) -> HEXACO:
    """역할 기반 HEXACO 생성 (섹션 8.3)

    Args:
        role: NPC 역할 (e.g. "innkeeper", "guard")
        seed: 재현성을 위한 RNG 시드. None이면 비결정적.

    Returns:
        HEXACO dataclass 인스턴스. 모든 값 0.0~1.0 클램프.
    """
    rng = random.Random(seed)
    template = ROLE_HEXACO_TEMPLATES.get(role, _NEUTRAL_TEMPLATE)

    values: Dict[str, float] = {}
    for factor, base_value in template.items():
        variance = rng.uniform(-_VARIANCE, _VARIANCE)
        values[factor] = max(0.0, min(1.0, base_value + variance))

    return HEXACO(**values)


# ── 행동 매핑 테이블 (섹션 8.4) ──────────────────────────────

HEXACO_BEHAVIOR_MAP: Dict[str, Dict[str, Dict[str, Any]]] = {
    "H": {  # Honesty-Humility
        "high": {"trade_price_mod": -0.1, "lie_chance": 0.05, "betray_chance": 0.02},
        "low": {"trade_price_mod": +0.2, "lie_chance": 0.40, "betray_chance": 0.25},
    },
    "E": {  # Emotionality
        "high": {"flee_threshold": 0.5, "panic_chance": 0.3, "empathy_bonus": +20},
        "low": {"flee_threshold": 0.2, "panic_chance": 0.05, "empathy_bonus": -10},
    },
    "X": {  # eXtraversion
        "high": {"talk_initiative": 0.8, "group_seek": True, "info_share": 0.7},
        "low": {"talk_initiative": 0.2, "group_seek": False, "info_share": 0.3},
    },
    "A": {  # Agreeableness
        "high": {"forgive_chance": 0.7, "conflict_avoid": True, "favor_threshold": 20},
        "low": {"forgive_chance": 0.2, "conflict_avoid": False, "favor_threshold": 50},
    },
    "C": {  # Conscientiousness
        "high": {"quest_complete_bonus": 1.2, "promise_keep": 0.95, "punctual": True},
        "low": {"quest_complete_bonus": 0.8, "promise_keep": 0.5, "punctual": False},
    },
    "O": {  # Openness
        "high": {
            "unusual_accept": 0.8,
            "new_idea_bonus": +15,
            "tradition_respect": 0.3,
        },
        "low": {"unusual_accept": 0.2, "new_idea_bonus": -5, "tradition_respect": 0.9},
    },
}


def get_behavior_modifier(hexaco: HEXACO, factor: str, modifier: str) -> Any:
    """HEXACO 값에 따른 행동 수정자 조회 (섹션 8.4)

    Args:
        hexaco: HEXACO dataclass 인스턴스
        factor: HEXACO 요인 ("H", "E", "X", "A", "C", "O")
        modifier: 수정자 이름 (e.g. "lie_chance", "talk_initiative")

    Returns:
        high/low/중간값 보간 결과.
        - 수치: high > 0.7, low < 0.3, 중간은 두 극단 평균
        - bool: high 기준 반환
    """
    value = getattr(hexaco, factor, 0.5)

    if factor not in HEXACO_BEHAVIOR_MAP:
        return None

    if value > 0.7:
        return HEXACO_BEHAVIOR_MAP[factor]["high"].get(modifier)
    elif value < 0.3:
        return HEXACO_BEHAVIOR_MAP[factor]["low"].get(modifier)
    else:
        # 중간값: 수치면 평균, bool 등은 high 기준
        high_val = HEXACO_BEHAVIOR_MAP[factor]["high"].get(modifier)
        low_val = HEXACO_BEHAVIOR_MAP[factor]["low"].get(modifier)
        if isinstance(high_val, (int, float)) and isinstance(low_val, (int, float)):
            return (high_val + low_val) / 2
        return high_val
