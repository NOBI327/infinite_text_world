"""대화 시스템 도메인 모델 (DB 무관)

dialogue-system.md 섹션 9.1, 9.2 대응.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DialogueTurn:
    """대화 턴 1회"""

    turn_index: int
    pc_input: str
    npc_narrative: str  # LLM 서술 (플레이어에게 보여줌)
    raw_meta: dict  # LLM META 원본
    validated_meta: dict  # Python 검증 후 META


@dataclass
class DialogueSession:
    """대화 세션 단위 (인메모리 상태)"""

    session_id: str  # UUID
    player_id: str
    npc_id: str
    node_id: str

    # 예산
    budget_total: int
    budget_remaining: int
    budget_phase: str  # "open"|"winding"|"closing"|"final"

    # 상태
    status: str = "active"  # "active"|"ended_by_pc"|"ended_by_npc"
    # |"ended_by_budget"|"ended_by_system"
    started_turn: int = 0  # 게임 턴
    dialogue_turn_count: int = 0

    # 시드
    quest_seed: Optional[dict] = None
    seed_delivered: bool = False
    seed_result: Optional[str] = None  # "accepted"|"ignored"|None

    # 동행 (companion-system.md 연동 예비)
    companion_npc_id: Optional[str] = None

    # 누적 (세션 종료 시 일괄 처리)
    accumulated_affinity_delta: float = 0.0
    accumulated_trust_delta: float = 0.0
    accumulated_memory_tags: list[str] = field(default_factory=list)

    # 대화 이력
    history: list[DialogueTurn] = field(default_factory=list)

    # 컨텍스트 (세션 시작 시 조립)
    npc_context: dict = field(default_factory=dict)
    session_context: dict = field(default_factory=dict)


# --- 종료 상태 코드 ---
DIALOGUE_END_STATUSES = {
    "ended_by_pc",
    "ended_by_npc",
    "ended_by_budget",
    "ended_by_system",
}
