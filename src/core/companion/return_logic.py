"""해산 후 NPC 귀환 목적지 결정

companion-system.md 섹션 6.2 대응.
"""

import logging

logger = logging.getLogger(__name__)


def determine_return_destination(
    npc_home_node: str | None,
    disband_reason: str,
    quest_type: str | None,
    client_npc_node: str | None,
) -> str | None:
    """해산 후 NPC 귀환 목적지. None이면 현재 위치 잔류.

    - quest_complete + escort → None (목표지 잔류)
    - quest_complete/failed + client 존재 → client 위치
    - home_node 존재 → home_node (정주형)
    - 없으면 → None (방랑형, 잔류)
    """
    # escort 완료 → 목표지(현재 위치)에 잔류
    if disband_reason == "quest_complete" and quest_type == "escort":
        logger.debug("Escort complete: NPC stays at destination")
        return None

    # 구출/퀘스트 관련 → 의뢰인 위치로
    if disband_reason in ("quest_complete", "quest_failed") and client_npc_node:
        logger.debug("Quest end: NPC returns to client at %s", client_npc_node)
        return client_npc_node

    # 정주형 → 원래 위치
    if npc_home_node:
        logger.debug("Resident NPC returns to home: %s", npc_home_node)
        return npc_home_node

    # 방랑형 → 잔류
    logger.debug("Wanderer NPC stays at current location")
    return None
