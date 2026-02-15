"""시드 생성 + TTL 처리 로직"""

import logging
import random
import uuid

from .models import QuestSeed
from .probability import (
    can_generate_seed,
    determine_seed_tier,
    get_default_ttl,
    roll_chain_chance,
    roll_seed_chance,
)

logger = logging.getLogger(__name__)

_SEED_TYPES = ["personal", "rumor", "request", "warning"]


def try_generate_seed(
    npc_id: str,
    current_turn: int,
    last_seed_conversation_count: int | None,
    current_conversation_count: int,
    eligible_quests: list | None = None,
) -> QuestSeed | None:
    """시드 발생 시도. 실패 시 None.

    1. 쿨다운 확인
    2. 5% 확률 판정
    3. 티어 결정
    4. eligible_quests가 있으면 체이닝 확률 판정
    5. QuestSeed 생성
    """
    if not can_generate_seed(last_seed_conversation_count, current_conversation_count):
        logger.debug("Seed generation blocked by cooldown for npc=%s", npc_id)
        return None

    if not roll_seed_chance():
        logger.debug("Seed generation failed 5%% roll for npc=%s", npc_id)
        return None

    seed_tier = determine_seed_tier()
    seed_type = select_seed_type()
    ttl = get_default_ttl(seed_type)

    chain_id: str | None = None
    if eligible_quests and roll_chain_chance(seed_tier):
        chain_id = f"chain_{uuid.uuid4().hex[:8]}"
        logger.info(
            "Chain seed generated: npc=%s, chain_id=%s, tier=%d",
            npc_id,
            chain_id,
            seed_tier,
        )

    seed = QuestSeed(
        seed_id=f"seed_{uuid.uuid4().hex[:12]}",
        npc_id=npc_id,
        seed_type=seed_type,
        seed_tier=seed_tier,
        created_turn=current_turn,
        ttl_turns=ttl,
        chain_id=chain_id,
    )

    logger.info(
        "Seed generated: seed_id=%s, npc=%s, type=%s, tier=%d",
        seed.seed_id,
        npc_id,
        seed_type,
        seed_tier,
    )
    return seed


def process_seed_ttl(seed: QuestSeed, current_turn: int) -> bool:
    """시드 TTL 체크. 만료되면 True + seed.status 변경."""
    if seed.status != "active":
        return False

    if current_turn >= seed.created_turn + seed.ttl_turns:
        seed.status = "expired"
        logger.info("Seed expired: seed_id=%s, turn=%d", seed.seed_id, current_turn)
        return True

    return False


def select_seed_type() -> str:
    """시드 유형 랜덤 선택. 균등 분포 (각 25%)."""
    return random.choice(_SEED_TYPES)
