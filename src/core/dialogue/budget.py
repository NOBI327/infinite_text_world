"""대화 턴 예산 계산 및 위상 관리

dialogue-system.md 섹션 2.3 대응.
"""

BASE_BUDGET: dict[str, int] = {
    "stranger": 3,
    "acquaintance": 4,
    "friend": 6,
    "bonded": 8,
    "rival": 4,
    "nemesis": 6,
}


def calculate_budget(
    relationship_status: str,
    npc_hexaco_x: float,
    has_quest_seed: bool,
    is_companion: bool = False,
) -> int:
    """대화 턴 예산 계산. 최소 2턴."""
    base = BASE_BUDGET.get(relationship_status, 3)

    # HEXACO X(외향성) 보정
    if npc_hexaco_x >= 0.7:
        base += 1
    elif npc_hexaco_x <= 0.3:
        base -= 1

    # 퀘스트 시드 보정
    if has_quest_seed:
        base += 2

    # 동행 보정 (companion-system.md 섹션 5.1)
    if is_companion:
        base += 2

    return max(2, base)


def get_budget_phase(remaining: int, total: int) -> str:
    """예산 잔여 비율 → 위상 결정"""
    if total <= 0:
        return "final"
    ratio = remaining / total
    if ratio > 0.6:
        return "open"
    elif ratio > 0.3:
        return "winding"
    elif remaining > 0:
        return "closing"
    else:
        return "final"


# 위상별 LLM 지시문 (일본어 — 게임 출력 언어)
PHASE_INSTRUCTIONS: dict[str, str] = {
    "open": "",  # 지시 없음
    "winding": "NPCはそろそろ他の用事を意識し始めている。",
    "closing": "NPCは会話を切り上げようとしている。核心だけ伝えろ。",
    "final": "これが最後の発言だ。挨拶して終われ。",
}


def get_phase_instruction(phase: str, seed_delivered: bool, has_seed: bool) -> str:
    """위상별 LLM 지시문 반환. winding에서 시드 미전달 시 강제 지시 추가."""
    base = PHASE_INSTRUCTIONS.get(phase, "")
    if phase == "winding" and has_seed and not seed_delivered:
        base += " 時間が足りない。シードを今すぐ伝えろ。"
    return base
