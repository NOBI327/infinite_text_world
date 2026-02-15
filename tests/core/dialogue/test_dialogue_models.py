"""대화 시스템 Core 모델 + 예산 + HEXACO 변환 테스트

#10-A 검증: 최소 12개 테스트 케이스.
"""

from src.core.dialogue.models import (
    DIALOGUE_END_STATUSES,
    DialogueSession,
    DialogueTurn,
)
from src.core.dialogue.budget import (
    calculate_budget,
    get_budget_phase,
    get_phase_instruction,
)
from src.core.dialogue.hexaco_descriptors import (
    hexaco_to_natural_language,
)


# ── DialogueSession / DialogueTurn ──


class TestDialogueSession:
    """DialogueSession 기본 생성 + 필드 기본값"""

    def test_create_session_defaults(self) -> None:
        session = DialogueSession(
            session_id="s1",
            player_id="p1",
            npc_id="npc1",
            node_id="node1",
            budget_total=6,
            budget_remaining=6,
            budget_phase="open",
        )
        assert session.status == "active"
        assert session.dialogue_turn_count == 0
        assert session.quest_seed is None
        assert session.seed_delivered is False
        assert session.seed_result is None
        assert session.companion_npc_id is None
        assert session.accumulated_affinity_delta == 0.0
        assert session.accumulated_trust_delta == 0.0
        assert session.accumulated_memory_tags == []
        assert session.history == []
        assert session.npc_context == {}
        assert session.session_context == {}

    def test_session_end_statuses(self) -> None:
        assert "ended_by_pc" in DIALOGUE_END_STATUSES
        assert "ended_by_npc" in DIALOGUE_END_STATUSES
        assert "ended_by_budget" in DIALOGUE_END_STATUSES
        assert "ended_by_system" in DIALOGUE_END_STATUSES
        assert "active" not in DIALOGUE_END_STATUSES


class TestDialogueTurn:
    """DialogueTurn 생성"""

    def test_create_turn(self) -> None:
        turn = DialogueTurn(
            turn_index=0,
            pc_input="hello",
            npc_narrative="NPC says hi",
            raw_meta={"dialogue_state": {"wants_to_continue": True}},
            validated_meta={"dialogue_state": {"wants_to_continue": True}},
        )
        assert turn.turn_index == 0
        assert turn.pc_input == "hello"
        assert turn.npc_narrative == "NPC says hi"
        assert turn.raw_meta["dialogue_state"]["wants_to_continue"] is True


# ── calculate_budget ──


class TestCalculateBudget:
    """예산 계산 테스트"""

    def test_base_budget_by_status(self) -> None:
        """관계별 기본값"""
        assert calculate_budget("stranger", 0.5, False) == 3
        assert calculate_budget("acquaintance", 0.5, False) == 4
        assert calculate_budget("friend", 0.5, False) == 6
        assert calculate_budget("bonded", 0.5, False) == 8
        assert calculate_budget("rival", 0.5, False) == 4
        assert calculate_budget("nemesis", 0.5, False) == 6

    def test_unknown_status_defaults_to_3(self) -> None:
        assert calculate_budget("unknown", 0.5, False) == 3

    def test_hexaco_x_high_bonus(self) -> None:
        """HEXACO X >= 0.7 → +1"""
        assert calculate_budget("friend", 0.8, False) == 7

    def test_hexaco_x_low_penalty(self) -> None:
        """HEXACO X <= 0.3 → -1"""
        assert calculate_budget("friend", 0.2, False) == 5

    def test_hexaco_x_boundary_0_7(self) -> None:
        """X == 0.7 → +1"""
        assert calculate_budget("stranger", 0.7, False) == 4

    def test_hexaco_x_boundary_0_3(self) -> None:
        """X == 0.3 → -1"""
        assert calculate_budget("stranger", 0.3, False) == 2

    def test_quest_seed_bonus(self) -> None:
        """시드 있으면 +2"""
        assert calculate_budget("friend", 0.5, True) == 8

    def test_minimum_2_turns(self) -> None:
        """최소 2턴 보장"""
        # stranger(3) + X<=0.3(-1) = 2
        assert calculate_budget("stranger", 0.1, False) == 2

    def test_combined_bonuses(self) -> None:
        """HEXACO + 시드 복합"""
        # bonded(8) + X>=0.7(+1) + seed(+2) = 11
        assert calculate_budget("bonded", 0.9, True) == 11

    def test_companion_bonus(self) -> None:
        """동행 보정 +2 (#13-C)"""
        # friend(6) + companion(+2) = 8
        assert calculate_budget("friend", 0.5, False, is_companion=True) == 8

    def test_companion_false_no_bonus(self) -> None:
        """is_companion=False → 보정 없음 (기존 호환)"""
        assert calculate_budget("friend", 0.5, False, is_companion=False) == 6


# ── get_budget_phase ──


class TestGetBudgetPhase:
    """예산 위상 판정 테스트"""

    def test_open_phase(self) -> None:
        """잔여 > 60%"""
        assert get_budget_phase(7, 10) == "open"

    def test_winding_phase(self) -> None:
        """잔여 30~60%"""
        assert get_budget_phase(5, 10) == "winding"
        assert get_budget_phase(4, 10) == "winding"

    def test_closing_phase(self) -> None:
        """잔여 1~30%"""
        assert get_budget_phase(2, 10) == "closing"
        assert get_budget_phase(1, 10) == "closing"

    def test_final_phase(self) -> None:
        """잔여 0"""
        assert get_budget_phase(0, 10) == "final"

    def test_boundary_0_6(self) -> None:
        """정확히 60% → winding"""
        assert get_budget_phase(6, 10) == "winding"

    def test_boundary_0_3(self) -> None:
        """정확히 30% → closing"""
        assert get_budget_phase(3, 10) == "closing"

    def test_total_zero(self) -> None:
        """total 0 → final"""
        assert get_budget_phase(0, 0) == "final"


# ── get_phase_instruction ──


class TestGetPhaseInstruction:
    """위상별 LLM 지시문 테스트"""

    def test_open_no_instruction(self) -> None:
        assert get_phase_instruction("open", False, False) == ""

    def test_winding_basic(self) -> None:
        result = get_phase_instruction("winding", True, True)
        assert "他の用事" in result

    def test_closing_instruction(self) -> None:
        result = get_phase_instruction("closing", False, False)
        assert "切り上げ" in result

    def test_final_instruction(self) -> None:
        result = get_phase_instruction("final", False, False)
        assert "最後の発言" in result

    def test_winding_seed_not_delivered_forces_seed(self) -> None:
        """winding에서 시드 미전달 시 강제 지시"""
        result = get_phase_instruction("winding", False, True)
        assert "シードを今すぐ伝えろ" in result

    def test_winding_seed_already_delivered(self) -> None:
        """winding에서 시드 이미 전달 → 강제 지시 없음"""
        result = get_phase_instruction("winding", True, True)
        assert "シードを今すぐ伝えろ" not in result

    def test_winding_no_seed(self) -> None:
        """시드 자체가 없으면 강제 지시 없음"""
        result = get_phase_instruction("winding", False, False)
        assert "シードを今すぐ伝えろ" not in result


# ── hexaco_to_natural_language ──


class TestHexacoToNaturalLanguage:
    """HEXACO 자연어 변환 테스트"""

    def test_all_high_values(self) -> None:
        values = {"H": 0.8, "E": 0.8, "X": 0.8, "A": 0.8, "C": 0.8, "O": 0.8}
        result = hexaco_to_natural_language(values)
        assert "このNPCは" in result
        assert "(H)" in result
        assert "(O)" in result
        assert "正直で謙虚" in result

    def test_all_low_values(self) -> None:
        values = {"H": 0.1, "E": 0.1, "X": 0.1, "A": 0.1, "C": 0.1, "O": 0.1}
        result = hexaco_to_natural_language(values)
        assert "利益に敏感" in result
        assert "寡黙で一人を好む" in result

    def test_boundary_0_0(self) -> None:
        """값 0.0 → 첫 번째 구간 (0.0~0.3)"""
        values = {"H": 0.0, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}
        result = hexaco_to_natural_language(values)
        assert "利益に敏感" in result

    def test_boundary_0_3(self) -> None:
        """값 0.3 → 두 번째 구간 (0.3~0.7)"""
        values = {"H": 0.3, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}
        result = hexaco_to_natural_language(values)
        assert "普通レベルの誠実さ" in result

    def test_boundary_0_7(self) -> None:
        """값 0.7 → 세 번째 구간 (0.7~1.0)"""
        values = {"H": 0.7, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}
        result = hexaco_to_natural_language(values)
        assert "正直で謙虚" in result

    def test_boundary_1_0(self) -> None:
        """값 1.0 → 세 번째 구간 (high == 1.0 특별 조건)"""
        values = {"H": 1.0, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}
        result = hexaco_to_natural_language(values)
        assert "正直で謙虚" in result

    def test_missing_factor_defaults_to_0_5(self) -> None:
        """누락된 factor → 0.5 기본값 → 중간 구간"""
        values = {"H": 0.8}  # E~O 누락
        result = hexaco_to_natural_language(values)
        assert "普通レベルの感受性(E)" in result
        assert "普通レベルの社交性(X)" in result

    def test_all_six_factors_present(self) -> None:
        """6개 factor 모두 결과에 포함"""
        values = {"H": 0.5, "E": 0.5, "X": 0.5, "A": 0.5, "C": 0.5, "O": 0.5}
        result = hexaco_to_natural_language(values)
        for factor in ("H", "E", "X", "A", "C", "O"):
            assert f"({factor})" in result
