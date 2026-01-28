"""
ITW Core Engine - Module 4: Echo System (Memory & Investigation)
================================================================
노드 메모리 및 조사 시스템

노드는 과거 이벤트의 기억(Echo)을 보존합니다.
플레이어는 이를 조사하여 정보를 얻을 수 있습니다.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from src.core.axiom_system import AxiomLoader
from src.core.world_generator import MapNode, Echo


class EchoType(Enum):
    """Echo 유형"""
    SHORT = "Short"   # 임시 - 시간이 지나면 사라짐
    LONG = "Long"     # 영구 - 로어/중요 이벤트


class EchoVisibility(Enum):
    """Echo 가시성"""
    PUBLIC = "Public"   # 모든 플레이어에게 보임
    HIDDEN = "Hidden"   # 조사해야 보임


class EchoCategory(Enum):
    """Echo 카테고리"""
    COMBAT = "combat"           # 전투 흔적
    EXPLORATION = "exploration" # 탐험 흔적
    CRAFTING = "crafting"       # 제작 흔적
    SOCIAL = "social"           # 사회적 상호작용
    DEATH = "death"             # 죽음/패배
    DISCOVERY = "discovery"     # 발견
    BOSS = "boss"               # 보스 처치
    MYSTERY = "mystery"         # 미스터리 이벤트


@dataclass
class EchoTemplate:
    """Echo 생성 템플릿"""
    category: EchoCategory
    echo_type: EchoType
    base_dc: int
    visibility: EchoVisibility
    flavor_templates: List[str]
    decay_days: Optional[int] = None  # Short Echo의 수명 (일)


class EchoManager:
    """
    Echo 관리 시스템

    Echo 생성, 조사, 소멸을 관리합니다.
    """

    # 기본 Echo 템플릿
    TEMPLATES = {
        EchoCategory.COMBAT: EchoTemplate(
            category=EchoCategory.COMBAT,
            echo_type=EchoType.SHORT,
            base_dc=10,
            visibility=EchoVisibility.PUBLIC,
            flavor_templates=[
                "피가 튄 흔적이 남아있다...",
                "무기가 부딪힌 자국이 선명하다...",
                "격렬한 싸움의 기운이 서려있다...",
                "누군가 이곳에서 싸웠다..."
            ],
            decay_days=7
        ),
        EchoCategory.DEATH: EchoTemplate(
            category=EchoCategory.DEATH,
            echo_type=EchoType.SHORT,
            base_dc=8,
            visibility=EchoVisibility.PUBLIC,
            flavor_templates=[
                "죽음의 기운이 서려있다...",
                "비극의 흔적이 느껴진다...",
                "누군가 이곳에서 쓰러졌다...",
                "서늘한 공기가 감돈다..."
            ],
            decay_days=14
        ),
        EchoCategory.EXPLORATION: EchoTemplate(
            category=EchoCategory.EXPLORATION,
            echo_type=EchoType.SHORT,
            base_dc=12,
            visibility=EchoVisibility.HIDDEN,
            flavor_templates=[
                "발자국이 희미하게 남아있다...",
                "누군가 이곳을 지나간 흔적이 있다...",
                "최근에 탐험된 흔적이 보인다...",
                "표식이 새겨져 있다..."
            ],
            decay_days=3
        ),
        EchoCategory.CRAFTING: EchoTemplate(
            category=EchoCategory.CRAFTING,
            echo_type=EchoType.SHORT,
            base_dc=14,
            visibility=EchoVisibility.HIDDEN,
            flavor_templates=[
                "제작 도구의 흔적이 남아있다...",
                "가공된 재료의 부스러기가 보인다...",
                "장인의 손길이 느껴진다...",
                "작업 흔적이 선명하다..."
            ],
            decay_days=5
        ),
        EchoCategory.BOSS: EchoTemplate(
            category=EchoCategory.BOSS,
            echo_type=EchoType.LONG,
            base_dc=5,
            visibility=EchoVisibility.PUBLIC,
            flavor_templates=[
                "위대한 승리의 기운이 서려있다!",
                "강대한 존재가 쓰러진 자리다...",
                "영웅적인 전투의 흔적이 남아있다!",
                "전설이 태어난 장소..."
            ],
            decay_days=None  # 영구
        ),
        EchoCategory.DISCOVERY: EchoTemplate(
            category=EchoCategory.DISCOVERY,
            echo_type=EchoType.LONG,
            base_dc=15,
            visibility=EchoVisibility.HIDDEN,
            flavor_templates=[
                "무언가 중요한 것이 발견된 장소...",
                "비밀이 밝혀진 흔적이 있다...",
                "지식의 기운이 서려있다...",
                "발견의 순간이 새겨져 있다..."
            ],
            decay_days=None
        ),
        EchoCategory.SOCIAL: EchoTemplate(
            category=EchoCategory.SOCIAL,
            echo_type=EchoType.SHORT,
            base_dc=10,
            visibility=EchoVisibility.PUBLIC,
            flavor_templates=[
                "대화의 여운이 남아있다...",
                "거래가 이루어진 흔적이 있다...",
                "만남의 기운이 느껴진다...",
                "누군가 이곳에서 약속을 나눴다..."
            ],
            decay_days=2
        ),
        EchoCategory.MYSTERY: EchoTemplate(
            category=EchoCategory.MYSTERY,
            echo_type=EchoType.LONG,
            base_dc=20,
            visibility=EchoVisibility.HIDDEN,
            flavor_templates=[
                "설명할 수 없는 현상의 흔적...",
                "초자연적인 기운이 맴돈다...",
                "이해할 수 없는 문양이 새겨져 있다...",
                "시공간이 뒤틀린 느낌이 든다..."
            ],
            decay_days=None
        )
    }

    # 시간 경과에 따른 DC 증가 (일당)
    TIME_DECAY_PER_DAY = 1

    # 최대 시간 감쇠
    MAX_TIME_DECAY = 10

    # 카테고리별 Fame 보상
    FAME_REWARDS = {
        EchoCategory.COMBAT: 5,
        EchoCategory.DEATH: 0,
        EchoCategory.EXPLORATION: 2,
        EchoCategory.CRAFTING: 3,
        EchoCategory.BOSS: 100,
        EchoCategory.DISCOVERY: 10,
        EchoCategory.SOCIAL: 3,
        EchoCategory.MYSTERY: 15
    }

    def __init__(self, axiom_loader: AxiomLoader):
        self.axiom_loader = axiom_loader

    def get_fame_reward(self, category: EchoCategory) -> int:
        """카테고리별 Fame 보상 반환"""
        return self.FAME_REWARDS.get(category, 0)

    def create_echo(
        self,
        category: EchoCategory,
        node: MapNode,
        source_player_id: Optional[str] = None,
        custom_flavor: Optional[str] = None,
        dc_modifier: int = 0
    ) -> Echo:
        """
        새 Echo 생성

        Args:
            category: Echo 카테고리
            node: Echo가 생성될 노드
            source_player_id: 생성자 플레이어 ID
            custom_flavor: 커스텀 플레이버 텍스트
            dc_modifier: DC 수정치

        Returns:
            생성된 Echo
        """
        template = self.TEMPLATES.get(category, self.TEMPLATES[EchoCategory.EXPLORATION])

        # 플레이버 텍스트
        if custom_flavor:
            flavor = custom_flavor
        else:
            flavor = random.choice(template.flavor_templates)

        # 노드의 지배 Axiom으로 플레이버 강화
        dominant = node.get_dominant_axiom()
        if dominant:
            axiom = self.axiom_loader.get_by_code(dominant)
            if axiom:
                flavor = f"{flavor} ({axiom.name_kr}의 기운과 함께)"

        # DC 계산
        base_dc = template.base_dc + dc_modifier

        echo = Echo(
            echo_type=template.echo_type.value,
            visibility=template.visibility.value,
            base_dc=base_dc,
            timestamp=datetime.utcnow().isoformat(),
            flavor_text=flavor,
            source_player_id=source_player_id
        )

        # 노드에 추가
        node.add_echo(echo)

        return echo

    def calculate_investigation_dc(
        self,
        echo: Echo,
        investigator_fame: int = 0,
        bonus_modifiers: int = 0
    ) -> Dict[str, Any]:
        """
        조사 DC 계산

        Formula: Final_DC = (Base_DC + Time_Decay) - Fame_Factor + Modifiers

        Args:
            echo: 조사할 Echo
            investigator_fame: 조사자의 명성 수치
            bonus_modifiers: 추가 수정치 (아이템, 스킬 등)

        Returns:
            {
                "base_dc": 10,
                "time_decay": 3,
                "fame_bonus": -2,
                "modifiers": -1,
                "final_dc": 10
            }
        """
        # 시간 경과 계산
        created = datetime.fromisoformat(echo.timestamp.replace('Z', '+00:00').replace('+00:00', ''))
        now = datetime.utcnow()
        days_passed = (now - created).days

        time_decay = min(days_passed * self.TIME_DECAY_PER_DAY, self.MAX_TIME_DECAY)

        # Fame 보너스 (높은 명성 = 정보 얻기 쉬움)
        fame_bonus = investigator_fame // 10  # 10 Fame당 -1 DC

        # 최종 DC
        final_dc = echo.base_dc + time_decay - fame_bonus - bonus_modifiers
        final_dc = max(5, final_dc)  # 최소 DC 5

        return {
            "base_dc": echo.base_dc,
            "time_decay": time_decay,
            "days_passed": days_passed,
            "fame_bonus": fame_bonus,
            "modifiers": bonus_modifiers,
            "final_dc": final_dc
        }

    def investigate(
        self,
        echo: Echo,
        roll: int,
        investigator_fame: int = 0,
        bonus_modifiers: int = 0
    ) -> Dict[str, Any]:
        """
        Echo 조사 시도

        Args:
            echo: 조사할 Echo
            roll: 주사위 굴림 결과 (1d20 + 능력치)
            investigator_fame: 조사자 명성
            bonus_modifiers: 추가 수정치

        Returns:
            조사 결과 (성공/실패, 발견 정보 등)
        """
        dc_info = self.calculate_investigation_dc(echo, investigator_fame, bonus_modifiers)
        final_dc = dc_info["final_dc"]

        success = roll >= final_dc
        margin = roll - final_dc

        result = {
            "success": success,
            "roll": roll,
            "dc": final_dc,
            "dc_breakdown": dc_info,
            "margin": margin
        }

        if success:
            # 성공 시 정보 제공
            result["discovered_info"] = {
                "flavor": echo.flavor_text,
                "type": echo.echo_type,
                "age": f"{dc_info['days_passed']}일 전",
                "source_hint": self._get_source_hint(echo, margin)
            }

            # 대성공 (margin >= 5) 시 추가 정보
            if margin >= 5:
                result["bonus_info"] = "흔적을 남긴 자의 대략적인 특징이 느껴진다..."
                if echo.source_player_id:
                    result["source_player_hint"] = echo.source_player_id[:4] + "****"
        else:
            # 실패
            result["message"] = "흔적을 해석하는 데 실패했다..."

            # 대실패 (margin <= -5) 시 페널티
            if margin <= -5:
                result["penalty"] = "잘못된 해석으로 혼란에 빠졌다. 다음 조사에 -2 페널티."

        return result

    def _get_source_hint(self, echo: Echo, margin: int) -> str:
        """성공 마진에 따른 소스 힌트 생성"""
        if margin >= 10:
            return "매우 명확한 흔적. 세부사항까지 알 수 있다."
        elif margin >= 5:
            return "선명한 흔적. 대략적인 상황을 파악할 수 있다."
        elif margin >= 0:
            return "희미한 흔적. 기본적인 정보만 알 수 있다."
        return "거의 사라진 흔적."

    def decay_echoes(self, node: MapNode) -> int:
        """
        노드의 Short Echo 시간 경과 처리

        Returns:
            삭제된 Echo 수
        """
        now = datetime.utcnow()
        remaining = []
        removed = 0

        for echo in node.echoes:
            if echo.echo_type == EchoType.LONG.value:
                # Long Echo는 영구 보존
                remaining.append(echo)
                continue

            # Short Echo 수명 체크
            template = None
            for t in self.TEMPLATES.values():
                if t.echo_type.value == echo.echo_type:
                    template = t
                    break

            if template and template.decay_days:
                created = datetime.fromisoformat(echo.timestamp.replace('Z', '+00:00').replace('+00:00', ''))
                age = (now - created).days

                if age > template.decay_days:
                    removed += 1
                    continue

            remaining.append(echo)

        node.echoes = remaining
        return removed

    def get_visible_echoes(self, node: MapNode) -> List[Echo]:
        """공개 Echo 목록 반환"""
        return [e for e in node.echoes if e.visibility == EchoVisibility.PUBLIC.value]

    def get_hidden_echoes(self, node: MapNode) -> List[Echo]:
        """숨겨진 Echo 목록 반환 (조사 필요)"""
        return [e for e in node.echoes if e.visibility == EchoVisibility.HIDDEN.value]

    def create_global_hook(
        self,
        event_type: str,
        location_hint: str,
        description: str
    ) -> Dict[str, Any]:
        """
        글로벌 훅 생성 (보스 킬, 대발견 등)

        모든 플레이어에게 알림되는 월드 이벤트
        """
        return {
            "type": "global_hook",
            "event": event_type,
            "location_hint": location_hint,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "expires_in_hours": 24
        }


@dataclass
class InvestigationResult:
    """조사 결과 상세"""
    success: bool
    echo: Echo
    roll: int
    dc: int
    margin: int
    discovered_info: Optional[Dict] = None
    bonus_info: Optional[str] = None
    penalty: Optional[str] = None

    def to_narrative(self) -> str:
        """서사적 결과 텍스트 생성"""
        if self.success:
            narrative = f"조사에 성공했다! (굴림: {self.roll} vs DC: {self.dc})\n"
            if self.discovered_info:
                narrative += f"\n{self.discovered_info['flavor']}\n"
                narrative += f"약 {self.discovered_info['age']} 전의 흔적이다.\n"
                narrative += f"{self.discovered_info['source_hint']}"
            if self.bonus_info:
                narrative += f"\n\n[추가 정보] {self.bonus_info}"
        else:
            narrative = f"조사에 실패했다... (굴림: {self.roll} vs DC: {self.dc})\n"
            narrative += "흔적을 해석하는 데 실패했다."
            if self.penalty:
                narrative += f"\n\n[페널티] {self.penalty}"

        return narrative


# === 테스트 코드 ===

if __name__ == "__main__":
    from src.core.world_generator import WorldGenerator

    # 초기화
    loader = AxiomLoader("itw_214_divine_axioms.json")
    world = WorldGenerator(loader, seed=42)
    echo_manager = EchoManager(loader)

    # 테스트 노드 생성
    test_node = world.generate_node(1, 1)

    # Echo 생성 테스트
    print("=== Creating Echoes ===")

    combat_echo = echo_manager.create_echo(
        EchoCategory.COMBAT,
        test_node,
        source_player_id="player_001"
    )
    print(f"Combat Echo: {combat_echo.flavor_text}")

    boss_echo = echo_manager.create_echo(
        EchoCategory.BOSS,
        test_node,
        custom_flavor="위대한 용이 쓰러진 자리. 영웅 '용살자'의 전설이 시작된 곳."
    )
    print(f"Boss Echo: {boss_echo.flavor_text}")

    mystery_echo = echo_manager.create_echo(
        EchoCategory.MYSTERY,
        test_node,
        dc_modifier=5  # 더 어렵게
    )
    print(f"Mystery Echo: {mystery_echo.flavor_text}")

    # DC 계산 테스트
    print("\n=== Investigation DC Calculation ===")
    dc_info = echo_manager.calculate_investigation_dc(
        mystery_echo,
        investigator_fame=50,
        bonus_modifiers=2
    )
    print(f"Base DC: {dc_info['base_dc']}")
    print(f"Time Decay: +{dc_info['time_decay']} ({dc_info['days_passed']} days)")
    print(f"Fame Bonus: -{dc_info['fame_bonus']}")
    print(f"Modifiers: -{dc_info['modifiers']}")
    print(f"Final DC: {dc_info['final_dc']}")

    # 조사 테스트
    print("\n=== Investigation Attempts ===")

    # 성공 케이스
    result = echo_manager.investigate(mystery_echo, roll=25, investigator_fame=50)
    print(f"\nRoll 25 - Success: {result['success']}")
    if result['success']:
        print(f"  Discovered: {result['discovered_info']['flavor'][:50]}...")

    # 실패 케이스
    result = echo_manager.investigate(mystery_echo, roll=8, investigator_fame=0)
    print(f"\nRoll 8 - Success: {result['success']}")
    print(f"  Message: {result.get('message', 'N/A')}")
    if result.get('penalty'):
        print(f"  Penalty: {result['penalty']}")

    # Echo 목록
    print("\n=== Node Echoes ===")
    print(f"Total: {len(test_node.echoes)}")
    print(f"Public: {len(echo_manager.get_visible_echoes(test_node))}")
    print(f"Hidden: {len(echo_manager.get_hidden_echoes(test_node))}")

    # Fame 보상 테스트
    print("\n=== Fame Rewards ===")
    print(f"COMBAT: {echo_manager.get_fame_reward(EchoCategory.COMBAT)}")
    print(f"BOSS: {echo_manager.get_fame_reward(EchoCategory.BOSS)}")
    print(f"MYSTERY: {echo_manager.get_fame_reward(EchoCategory.MYSTERY)}")

    # 글로벌 훅 테스트
    print("\n=== Global Hook ===")
    hook = echo_manager.create_global_hook(
        event_type="boss_kill",
        location_hint="화염에 휩싸인 북쪽 산맥 어딘가",
        description="누군가 고대의 화염룡 '이그니스'를 처치했다!"
    )
    print(f"Event: {hook['event']}")
    print(f"Description: {hook['description']}")
