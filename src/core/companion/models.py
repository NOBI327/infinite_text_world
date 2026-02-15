"""동행 도메인 모델 (DB 무관)

companion-system.md 섹션 3.2 대응.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CompanionState:
    """동행 상태 관리"""

    companion_id: str
    player_id: str
    npc_id: str

    # 유형
    companion_type: str = "voluntary"  # "quest" | "voluntary"
    quest_id: Optional[str] = None

    # 상태
    status: str = "active"  # "active" | "disbanded"
    started_turn: int = 0
    ended_turn: Optional[int] = None
    disband_reason: Optional[str] = None
    # "pc_dismiss"|"quest_complete"|"quest_failed"
    # |"npc_dead"|"condition_expired"|"npc_request"

    # 조건
    condition_type: Optional[str] = None
    # "payment"|"time_limit"|"destination_only"
    # |"safety_guarantee"|"item_request"
    condition_data: Optional[dict[str, Any]] = None
    condition_met: bool = False

    # 원래 위치
    origin_node_id: str = ""

    # 메타
    created_at: str = ""
