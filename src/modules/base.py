"""모듈 기반 인터페이스"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session


@dataclass
class GameContext:
    """모듈에 전달되는 게임 상태 컨텍스트"""

    player_id: str
    current_node_id: str
    current_turn: int
    db_session: Optional[Session] = None

    # 모듈이 추가 데이터를 넣을 수 있는 확장 슬롯
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """모듈이 제공하는 행동"""

    name: str  # 액션 식별자 (예: "talk", "trade")
    display_name: str  # 표시 이름 (예: "대화하기")
    module_name: str  # 제공한 모듈 이름
    description: str = ""  # 설명
    params: Dict[str, Any] = field(default_factory=dict)  # 추가 파라미터


class GameModule(ABC):
    """모든 ITW 모듈의 기반 인터페이스

    docs/30_technical/module-architecture.md 섹션 4.1 참조.

    규칙:
    - 모듈은 다른 모듈을 직접 import하지 않는다
    - 모듈 간 통신은 EventBus를 경유한다 (지시서 #02)
    - Module → Core, Module → DB는 허용
    - Module → Module은 금지
    """

    _enabled: bool

    def __init__(self) -> None:
        self._enabled = False

    @property
    @abstractmethod
    def name(self) -> str:
        """모듈 고유 이름 (예: 'geography', 'npc_core')"""
        ...

    @property
    def dependencies(self) -> List[str]:
        """이 모듈이 의존하는 다른 모듈 이름 목록

        기본값은 빈 리스트 (의존성 없음).
        """
        return []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @abstractmethod
    def on_enable(self) -> None:
        """모듈 활성화 시 초기화 작업"""
        ...

    @abstractmethod
    def on_disable(self) -> None:
        """모듈 비활성화 시 정리 작업"""
        ...

    @abstractmethod
    def on_turn(self, context: GameContext) -> None:
        """매 턴 호출. 모듈별 턴 처리 로직."""
        ...

    @abstractmethod
    def on_node_enter(self, node_id: str, context: GameContext) -> None:
        """플레이어가 노드에 진입할 때 호출."""
        ...

    @abstractmethod
    def get_available_actions(self, context: GameContext) -> List[Action]:
        """현재 상황에서 이 모듈이 제공하는 행동 목록 반환."""
        ...
