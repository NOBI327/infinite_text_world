"""퀘스트 확률 판정 — 순수 Python, 외부 의존 없음"""

import logging
import random

logger = logging.getLogger(__name__)

# === 시드 발생 확률 ===
SEED_CHANCE = 0.05  # 5%

# === 시드 유형별 기본 TTL ===
SEED_TTL_DEFAULT: dict[str, int] = {
    "personal": 15,
    "rumor": 30,
    "request": 20,
    "warning": 10,
}

# === 티어 분포 ===
SEED_TIER_WEIGHTS: dict[int, float] = {
    3: 0.60,  # 소: 60%
    2: 0.30,  # 중: 30%
    1: 0.10,  # 대: 10%
}

# === 체이닝 확률 ===
CHAIN_PROBABILITY_BY_TIER: dict[int, float] = {
    3: 0.10,
    2: 0.50,
    1: 0.80,
}

# === 완결 확률 ===
FINALIZE_CHANCES: dict[int, float] = {
    1: 0.0,
    2: 0.20,
    3: 0.40,
    4: 0.60,
    5: 0.80,
}
FINALIZE_DEFAULT = 0.95  # 6개 이상

# === NPC 쿨다운 ===
NPC_QUEST_COOLDOWN = 5  # 같은 NPC에게서 최소 5회 대화 후 재발생

# === 실패 보고 시드 확률 ===
FAILURE_REPORT_SEED_CHANCE = 0.50


def roll_seed_chance() -> bool:
    """5% 확률로 시드 발생 판정."""
    return random.random() < SEED_CHANCE


def determine_seed_tier() -> int:
    """시드 티어 확률 판정. 반환: 1, 2, 3."""
    roll = random.random()
    if roll < SEED_TIER_WEIGHTS[3]:
        return 3
    elif roll < SEED_TIER_WEIGHTS[3] + SEED_TIER_WEIGHTS[2]:
        return 2
    else:
        return 1


def roll_chain_chance(seed_tier: int) -> bool:
    """체이닝 확률 판정."""
    prob = CHAIN_PROBABILITY_BY_TIER.get(seed_tier, 0.10)
    return random.random() < prob


def should_finalize_chain(chain_length: int) -> bool:
    """체인 완결 여부 판정."""
    chance = FINALIZE_CHANCES.get(chain_length, FINALIZE_DEFAULT)
    return random.random() < chance


def can_generate_seed(
    last_seed_conversation_count: int | None,
    current_conversation_count: int,
) -> bool:
    """NPC 쿨다운 확인. last_seed_conversation_count가 None이면 시드 없음 → 가능."""
    if last_seed_conversation_count is None:
        return True
    return (
        current_conversation_count - last_seed_conversation_count
    ) >= NPC_QUEST_COOLDOWN


def roll_failure_report_seed() -> bool:
    """의뢰주 보고 시 후속 시드 발생 확률 (50%)."""
    return random.random() < FAILURE_REPORT_SEED_CHANCE


def get_default_ttl(seed_type: str) -> int:
    """시드 유형별 기본 TTL."""
    return SEED_TTL_DEFAULT.get(seed_type, 20)
