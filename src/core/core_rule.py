"""
ITW Core Engine - Module 5: Core Rule System (Protocol T.A.G.)
==============================================================
Protocol T.A.G. v2.0 Resonance 판정 엔진

인간이 읽고(Tag), AI가 해석하며, Python이 실행하는(Dice Pool)
핵심 룰셋 구현체입니다.

[핵심 메커니즘]
1. Process Variables (PV): 4대 스탯 (WRITE, READ, EXEC, SUDO)
2. Resonance Shield: 8대 속성 내구도
3. Axiom Dice Pool: 스탯 + 태그 보너스 - 리스크 = 주사위 개수 (d6)
4. Success Check: 5, 6 = Hit
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from src.core.logging import get_logger

# axiom_system의 Axiom 클래스 타입 힌팅용 (순환 참조 방지)
if TYPE_CHECKING:
    from src.core.axiom_system import Axiom

logger = get_logger(__name__)


class StatType(Enum):
    """4대 프로세스 변수 (Process Variables)"""

    WRITE = "WRITE"  # 물리/출력 (Force, Material) - 힘, 전투, 파괴
    READ = "READ"  # 감각/입력 (Mystery, Mind) - 감지, 조사, 통찰
    EXEC = "EXEC"  # 기술/기능 (Logic, Organic) - 제작, 조작, 민첩
    SUDO = "SUDO"  # 사회/권한 (Social) - 대화, 지휘, 권능


class CheckResultTier(Enum):
    """판정 결과 티어"""

    CRITICAL_FAILURE = "Critical Failure"  # 대실패 (성공 0개 & 1이 존재)
    FAILURE = "Failure"  # 실패 (성공 < 난이도)
    PARTIAL_SUCCESS = "Partial Success"  # 부분 성공 (성공 == 난이도 - 1, 선택적 룰)
    SUCCESS = "Success"  # 성공 (성공 >= 난이도)
    CRITICAL_SUCCESS = "Critical Success"  # 대성공 (성공 >= 난이도 + 2)


@dataclass
class CheckResult:
    """판정 결과 데이터"""

    success: bool
    tier: CheckResultTier
    hits: int  # 성공수 (5, 6의 개수)
    required_hits: int  # 목표 난이도
    rolls: List[int]  # 굴린 주사위 값 목록
    narrative_hint: str  # AI 서술 가이드


@dataclass
class CharacterSheet:
    """캐릭터/NPC 데이터 구조"""

    name: str
    level: int = 1

    # 4대 스탯 (기본값 1)
    stats: Dict[StatType, int] = field(
        default_factory=lambda: {
            StatType.WRITE: 1,
            StatType.READ: 1,
            StatType.EXEC: 1,
            StatType.SUDO: 1,
        }
    )

    # 8대 속성 내구도 (Resonance Shield)
    # None = Null (면역), 0 = Broken (붕괴)
    resonance_shield: Dict[str, Optional[int]] = field(
        default_factory=lambda: {
            "Kinetic": 10,
            "Thermal": 10,
            "Structural": 10,
            "Bio": 10,
            "Psyche": 10,
            "Data": 10,
            "Social": 10,
            "Esoteric": 10,
        }
    )

    # 현재 활성화된 상태 태그 (예: 'Burning', 'Hasted')
    status_tags: List[str] = field(default_factory=list)

    def get_stat(self, stat: Union[StatType, str]) -> int:
        """스탯 값 조회"""
        if isinstance(stat, str):
            stat = StatType(stat)
        return self.stats.get(stat, 1)

    def set_stat(self, stat: Union[StatType, str], value: int):
        """스탯 설정"""
        if isinstance(stat, str):
            stat = StatType(stat)
        self.stats[stat] = max(1, value)

    def damage_resonance(self, resonance_type: str, amount: int) -> str:
        """내구도 피해 적용 및 상태 반환"""
        current = self.resonance_shield.get(resonance_type)

        if current is None:
            return "IMMUNE"  # 면역 (Null)

        new_val = max(0, current - amount)
        self.resonance_shield[resonance_type] = new_val

        if new_val == 0:
            return "BROKEN"  # 붕괴
        return "DAMAGED"


class ResolutionEngine:
    """
    Protocol T.A.G. 판정 엔진
    """

    def __init__(self):
        pass

    def resolve_check(
        self,
        character: CharacterSheet,
        stat_type: Union[StatType, str],
        difficulty: int = 1,
        bonus_dice: int = 0,
        risk_penalty: int = 0,
        relevant_tags: int = 0,  # Axiom/아이템 등에서 오는 보너스 개수
    ) -> CheckResult:
        """
        핵심 판정 로직 실행

        Args:
            character: 주체 캐릭터
            stat_type: 사용할 스탯 (WRITE/READ/EXEC/SUDO)
            difficulty: 목표 성공수 (TN) - T1:1~2, T2:3~4 ...
            bonus_dice: 상황 보너스 주사위 (GM 부여)
            risk_penalty: 상황 페널티 주사위 (GM 부여)
            relevant_tags: 유리한 태그 개수 (개당 +1d6)

        Returns:
            CheckResult 객체
        """
        # 1. Base Dice (스탯)
        base_dice = character.get_stat(stat_type)

        # 2. Total Pool 계산 (최소 1개는 굴림)
        total_dice = base_dice + relevant_tags + bonus_dice - risk_penalty
        total_dice = max(1, total_dice)

        # 3. Roll (d6)
        rolls = [random.randint(1, 6) for _ in range(total_dice)]

        # 4. Count Hits (5, 6 = Success)
        hits = sum(1 for r in rolls if r >= 5)
        ones = sum(1 for r in rolls if r == 1)

        # 5. Determine Outcome
        tier = CheckResultTier.FAILURE
        success = False
        hint = ""

        if hits >= difficulty:
            success = True
            if hits >= difficulty + 2:
                tier = CheckResultTier.CRITICAL_SUCCESS
                hint = "압도적인 성과. 의도한 것 이상의 이득을 얻거나 시간을 단축함."
            else:
                tier = CheckResultTier.SUCCESS
                hint = "목표 달성. 깔끔하게 의도를 실현함."
        else:
            success = False
            # 대실패 판정 (성공 0개이고 1이 있는 경우)
            if hits == 0 and ones > 0:
                tier = CheckResultTier.CRITICAL_FAILURE
                hint = "치명적 실패. 상황이 악화되거나 반동을 입음."
            else:
                tier = CheckResultTier.FAILURE
                hint = "단순 실패. 현상 유지 혹은 기회 소진."

        return CheckResult(
            success=success,
            tier=tier,
            hits=hits,
            required_hits=difficulty,
            rolls=rolls,
            narrative_hint=hint,
        )

    def calculate_resonance_interaction(
        self,
        check_result: CheckResult,
        input_axioms: List["Axiom"],
        target_shield: Dict[str, Optional[int]],
    ) -> Dict[str, Any]:
        """
        전투/상호작용 결과 연산 (Resonance System)

        Args:
            check_result: 앞선 resolve_check의 결과
            input_axioms: 사용한 무기/스킬의 Axiom 리스트 (예: [Ignis, Ferrum])
            target_shield: 대상의 내구도 정보

        Returns:
            데미지 로그 및 결과 딕셔너리
        """
        if not check_result.success:
            return {"total_damage": 0, "log": ["공격이 빗나갔거나 효과가 없었습니다."]}

        damage_log = []
        total_damage = 0

        # 크리티컬 보정 (1.5배)
        multiplier = (
            1.5 if check_result.tier == CheckResultTier.CRITICAL_SUCCESS else 1.0
        )

        for axiom in input_axioms:
            # 1. 공리의 속성 확인 (예: Ignis -> Thermal)
            res_type = axiom.resonance.value

            # 2. 타겟의 해당 속성 내구도 확인
            target_durability = target_shield.get(res_type)

            if target_durability is None:
                # Null Rule: 면역
                damage_log.append(f"[{axiom.name_kr}]({res_type}) -> 면역 (Null)")
                continue

            # 3. 기본 데미지 (태그 티어 * 10 * 멀티플라이어)
            base_dmg = int(axiom.tier * 10 * multiplier)

            # 4. (추가 로직) 상성 계산은 axiom_system의 calculate_interaction 활용 가능
            # 여기서는 단순화된 모델 적용

            damage_log.append(f"[{axiom.name_kr}]({res_type}) -> {base_dmg} 피해")
            total_damage += base_dmg

        return {
            "total_damage": total_damage,
            "log": damage_log,
            "is_critical": check_result.tier == CheckResultTier.CRITICAL_SUCCESS,
        }


if __name__ == "__main__":
    from src.core.logging import setup_logging

    setup_logging("DEBUG")

    logger.info("=== Core Rule System Test ===")

    char = CharacterSheet(name="Test Hero", level=1)
    char.set_stat(StatType.WRITE, 3)
    logger.info(
        "CharacterSheet: %s, WRITE=%d", char.name, char.get_stat(StatType.WRITE)
    )

    engine = ResolutionEngine()
    result = engine.resolve_check(char, StatType.WRITE, difficulty=1)
    logger.info(
        "Check: Rolls=%s, Hits=%d, Result=%s",
        result.rolls,
        result.hits,
        result.tier.value,
    )

    status = char.damage_resonance("Thermal", 5)
    logger.info(
        "Damage Thermal -5: %s, Remaining=%d", status, char.resonance_shield["Thermal"]
    )

    logger.info("=== Test Complete ===")
