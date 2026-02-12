"""3축 수치 변동 계산

relationship-system.md 섹션 4 대응.
전부 순수 함수 — 외부 의존 없음.
"""


def apply_affinity_damping(current: float, raw_change: float) -> float:
    """affinity 감쇠 적용 (섹션 4.3).

    양방향 대칭, 지수 1.2. 최소 10% 보장.
    """
    damping: float = 1.0 - (abs(current) / 100) ** 1.2
    return raw_change * max(damping, 0.1)


def apply_trust_damping(current: float, raw_change: float) -> float:
    """trust 감쇠 적용 (섹션 4.3).

    비대칭: 상승은 감쇠 적용, 하락은 감쇠 없음.
    """
    if raw_change >= 0:
        damping: float = 1.0 - (current / 100) ** 1.2
        return raw_change * max(damping, 0.1)
    else:
        return raw_change


def apply_familiarity_decay(current: int, days_since_last: int) -> int:
    """familiarity 시간 감쇠 (섹션 4.3).

    30일마다 -1, 최소 0.
    """
    decay = days_since_last // 30
    return max(0, current - decay)


def clamp_affinity(value: float) -> float:
    """-100 ~ +100 클램프."""
    return max(-100.0, min(100.0, value))


def clamp_trust(value: float) -> float:
    """0 ~ 100 클램프."""
    return max(0.0, min(100.0, value))


def clamp_meta_delta(value: float) -> float:
    """LLM META 제안 범위 -5 ~ +5 클램프."""
    return max(-5.0, min(5.0, value))
