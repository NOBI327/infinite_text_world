"""
ITW Core Engine - Sub Grid System
==================================
메인 그리드 노드 내부로 진입하는 확장 공간 시스템

설계 참조: docs/20_design/sub-grid.md
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.core.axiom_system import AxiomLoader, AxiomVector, DomainType
from src.core.logging import get_logger

logger = get_logger(__name__)


class SubGridType(Enum):
    """서브 그리드 유형"""

    DUNGEON = "dungeon"  # 하강형: sz 0 ~ -N (지하묘지, 폐광)
    TOWER = "tower"  # 상승형: sz 0 ~ +N (마법사 탑)
    FOREST = "forest"  # 수평형: sz 0 고정 (깊은 숲, 미로)
    CAVE = "cave"  # 복합형: sz -N ~ +M (자연 동굴)


@dataclass
class DepthPoint:
    """메인 노드의 서브 그리드 진입점 정보 (L3 Depth)"""

    depth_name: str
    depth_tier: int
    entry_condition: str | None = None
    discovered: bool = False
    grid_type: SubGridType = SubGridType.DUNGEON

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth_name": self.depth_name,
            "depth_tier": self.depth_tier,
            "entry_condition": self.entry_condition,
            "discovered": self.discovered,
            "grid_type": self.grid_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DepthPoint":
        return cls(
            depth_name=data["depth_name"],
            depth_tier=data["depth_tier"],
            entry_condition=data.get("entry_condition"),
            discovered=data.get("discovered", False),
            grid_type=SubGridType(data.get("grid_type", "dungeon")),
        )


@dataclass
class SubGridNode:
    """서브 그리드 노드 (DB 의존성 없음)"""

    # 좌표 정보
    parent_coordinate: str  # "x_y" 형식 (FK to map_nodes)
    sx: int  # 서브 그리드 내 x 위치
    sy: int  # 서브 그리드 내 y 위치
    sz: int  # 서브 그리드 내 z 위치 (0=입구)

    # 노드 속성
    tier: str  # 노드 등급
    axiom_vector: dict[str, float] = field(default_factory=dict)
    sensory_data: dict[str, Any] = field(default_factory=dict)
    required_tags: list[str] = field(default_factory=list)

    # 서브 그리드 전용
    is_entrance: bool = False  # sz=0이고 입구인지
    is_exit: bool = False  # 다른 출구로 연결되는지

    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def id(self) -> str:
        """복합 기본키: parent_x_y_sx_sy_sz 형식"""
        return f"{self.parent_coordinate}_{self.sx}_{self.sy}_{self.sz}"

    @property
    def coordinate(self) -> tuple[str, int, int, int]:
        """좌표 튜플 (parent_coordinate, sx, sy, sz)"""
        return (self.parent_coordinate, self.sx, self.sy, self.sz)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_coordinate": self.parent_coordinate,
            "sx": self.sx,
            "sy": self.sy,
            "sz": self.sz,
            "tier": self.tier,
            "axiom_vector": self.axiom_vector,
            "sensory_data": self.sensory_data,
            "required_tags": self.required_tags,
            "is_entrance": self.is_entrance,
            "is_exit": self.is_exit,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubGridNode":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        return cls(
            parent_coordinate=data["parent_coordinate"],
            sx=data["sx"],
            sy=data["sy"],
            sz=data["sz"],
            tier=data["tier"],
            axiom_vector=data.get("axiom_vector", {}),
            sensory_data=data.get("sensory_data", {}),
            required_tags=data.get("required_tags", []),
            is_entrance=data.get("is_entrance", False),
            is_exit=data.get("is_exit", False),
            created_at=created_at,
        )


class SubGridGenerator:
    """
    서브 그리드 절차적 생성기

    메인 WorldGenerator 패턴을 따르되, 서브 그리드 특성 반영:
    - 시드: hash(self.seed, parent_x, parent_y, sx, sy, sz)
    - 난이도: depth_tier + abs(sz)
    """

    # 티어별 문자열
    TIER_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}

    # 도메인별 감각 템플릿 (서브 그리드용)
    SENSORY_TEMPLATES = {
        DomainType.PRIMORDIAL: {
            "atmosphere": ["원초적 에너지가 맥동한다", "태고의 힘이 스며있다"],
            "sound": ["깊은 울림", "용암 끓는 소리"],
            "smell": ["유황 냄새", "화산재 냄새"],
        },
        DomainType.MATERIAL: {
            "atmosphere": ["단단한 암석의 압박감", "광물의 반짝임"],
            "sound": ["물 떨어지는 소리", "돌 부서지는 소리"],
            "smell": ["습한 흙 냄새", "금속 냄새"],
        },
        DomainType.FORCE: {
            "atmosphere": ["중력의 변화가 느껴진다", "공기가 진동한다"],
            "sound": ["바람 소용돌이", "압력 변화음"],
            "smell": ["오존 냄새", "전기 냄새"],
        },
        DomainType.ORGANIC: {
            "atmosphere": ["생명체의 기척", "유기적 성장의 흔적"],
            "sound": ["생물의 숨소리", "무언가 기어다니는 소리"],
            "smell": ["부패 냄새", "곰팡이 냄새"],
        },
        DomainType.MIND: {
            "atmosphere": ["정신적 압박감", "환각의 조짐"],
            "sound": ["속삭이는 목소리", "울림 없는 메아리"],
            "smell": ["향 냄새", "기억의 잔향"],
        },
        DomainType.LOGIC: {
            "atmosphere": ["기계적 질서", "패턴의 반복"],
            "sound": ["기계음", "규칙적인 틱톡"],
            "smell": ["기름 냄새", "먼지 냄새"],
        },
        DomainType.SOCIAL: {
            "atmosphere": ["과거 문명의 흔적", "폐허의 적막"],
            "sound": ["먼 곳의 발자국", "웅성거림의 메아리"],
            "smell": ["오래된 책 냄새", "먼지 냄새"],
        },
        DomainType.MYSTERY: {
            "atmosphere": ["시공간의 왜곡", "이질적 존재감"],
            "sound": ["형언할 수 없는 소리", "완벽한 침묵"],
            "smell": ["무", "이세계의 향기"],
        },
    }

    def __init__(self, axiom_loader: AxiomLoader, seed: int):
        self.axiom_loader = axiom_loader
        self.seed = seed
        self.nodes: dict[str, SubGridNode] = {}

    def _get_coord_seed(
        self, parent_x: int, parent_y: int, sx: int, sy: int, sz: int
    ) -> int:
        """좌표 기반 결정론적 시드 생성"""
        return hash((self.seed, parent_x, parent_y, sx, sy, sz)) & 0xFFFFFFFF

    def _calculate_effective_tier(self, depth_tier: int, sz: int) -> int:
        """유효 난이도 계산: depth_tier + abs(sz)"""
        return min(depth_tier + abs(sz), 5)  # 최대 5 (Legendary)

    def _get_tier_name(self, effective_tier: int) -> str:
        """티어 숫자를 문자열로 변환"""
        return self.TIER_NAMES.get(effective_tier, "Common")

    def _select_axioms_by_tier(self, effective_tier: int, count: int = 3) -> list:
        """티어에 따른 Axiom 선택"""
        if effective_tier >= 4:
            # Epic/Legendary: Mystery 도메인 포함
            pool = self.axiom_loader.get_by_tier(3) + self.axiom_loader.get_by_domain(
                DomainType.MYSTERY
            )
        elif effective_tier >= 3:
            # Rare: Tier 2~3
            pool = self.axiom_loader.get_by_tier(2) + self.axiom_loader.get_by_tier(3)
        elif effective_tier >= 2:
            # Uncommon: Tier 1~2
            pool = self.axiom_loader.get_by_tier(1) + self.axiom_loader.get_by_tier(2)
        else:
            # Common: Tier 1
            pool = self.axiom_loader.get_by_tier(1)

        pool = list({a.id: a for a in pool}.values())
        return random.sample(pool, min(count, len(pool)))

    def _generate_vector(self, effective_tier: int) -> AxiomVector:
        """Axiom 벡터 생성"""
        vector = AxiomVector()

        axiom_count = random.randint(1, min(4, effective_tier + 1))
        selected = self._select_axioms_by_tier(effective_tier, axiom_count)

        for i, axiom in enumerate(selected):
            weight = 0.8 - (i * 0.15)
            weight = max(0.2, weight + random.uniform(-0.1, 0.1))
            vector.add(axiom.code, weight)

        return vector

    def _generate_sensory(
        self, vector: AxiomVector, effective_tier: int, sz: int
    ) -> dict[str, Any]:
        """감각 데이터 생성"""
        dominant_code = vector.get_dominant()
        dominant_axiom = (
            self.axiom_loader.get_by_code(dominant_code) if dominant_code else None
        )

        domain = dominant_axiom.domain if dominant_axiom else DomainType.PRIMORDIAL
        templates = self.SENSORY_TEMPLATES.get(
            domain, self.SENSORY_TEMPLATES[DomainType.PRIMORDIAL]
        )

        tier_prefix = {
            1: "",
            2: "특이한 ",
            3: "위험한 ",
            4: "경이로운 ",
            5: "전설적인 ",
        }

        depth_desc = ""
        if sz < 0:
            depth_desc = f"지하 {abs(sz)}층. "
        elif sz > 0:
            depth_desc = f"상층 {sz}층. "

        atmosphere = random.choice(templates["atmosphere"])
        sound = random.choice(templates["sound"])
        smell = random.choice(templates["smell"])

        axiom_name = dominant_axiom.name_kr if dominant_axiom else "알 수 없는"

        return {
            "visual_far": f"{tier_prefix.get(effective_tier, '')}{axiom_name}의 기운이 느껴지는 통로",
            "visual_near": f"{depth_desc}{axiom_name}의 영향이 지배하는 공간. {atmosphere}",
            "atmosphere": axiom_name,
            "sound_hint": sound,
            "smell_hint": smell,
        }

    def _generate_required_tags(self, effective_tier: int, sz: int) -> list[str]:
        """진입 필수 태그 생성"""
        tags: list[str] = []

        # 깊은 층일수록 필수 태그 증가
        if abs(sz) >= 3:
            tags.append("tag_light_source")
        if abs(sz) >= 5:
            tags.append("tag_climbing_gear")
        if effective_tier >= 4:
            tags.append("tag_magic_resistance")

        return tags

    def generate_node(
        self,
        parent_x: int,
        parent_y: int,
        sx: int,
        sy: int,
        sz: int,
        depth_tier: int,
    ) -> SubGridNode:
        """
        서브 그리드 노드 생성

        Args:
            parent_x, parent_y: 부모 메인 노드 좌표
            sx, sy, sz: 서브 그리드 내 좌표
            depth_tier: 기본 난이도 (DepthPoint.depth_tier)

        Returns:
            생성된 SubGridNode
        """
        parent_coordinate = f"{parent_x}_{parent_y}"
        node_id = f"{parent_coordinate}_{sx}_{sy}_{sz}"

        # 이미 존재하면 반환
        if node_id in self.nodes:
            return self.nodes[node_id]

        # 좌표 기반 결정론적 시드 설정
        random.seed(self._get_coord_seed(parent_x, parent_y, sx, sy, sz))

        # 유효 난이도 계산
        effective_tier = self._calculate_effective_tier(depth_tier, sz)
        tier_name = self._get_tier_name(effective_tier)

        # Axiom 벡터 생성
        vector = self._generate_vector(effective_tier)

        # 감각 데이터 생성
        sensory = self._generate_sensory(vector, effective_tier, sz)

        # 필수 태그 생성
        required_tags = self._generate_required_tags(effective_tier, sz)

        # 입구/출구 판정
        is_entrance = sz == 0 and sx == 0 and sy == 0
        is_exit = False  # 출구는 별도 로직으로 설정

        # 노드 생성
        node = SubGridNode(
            parent_coordinate=parent_coordinate,
            sx=sx,
            sy=sy,
            sz=sz,
            tier=tier_name,
            axiom_vector=vector.to_dict(),
            sensory_data=sensory,
            required_tags=required_tags,
            is_entrance=is_entrance,
            is_exit=is_exit,
        )

        self.nodes[node_id] = node
        logger.debug("Generated SubGridNode: %s (tier=%s)", node_id, tier_name)

        return node

    def generate_entrance(
        self, parent_x: int, parent_y: int, depth_tier: int
    ) -> SubGridNode:
        """입구 노드 생성 (sz=0, sx=0, sy=0)"""
        return self.generate_node(parent_x, parent_y, 0, 0, 0, depth_tier)

    def get_node(
        self, parent_x: int, parent_y: int, sx: int, sy: int, sz: int
    ) -> SubGridNode | None:
        """노드 조회 (없으면 None)"""
        node_id = f"{parent_x}_{parent_y}_{sx}_{sy}_{sz}"
        return self.nodes.get(node_id)

    def get_or_generate(
        self,
        parent_x: int,
        parent_y: int,
        sx: int,
        sy: int,
        sz: int,
        depth_tier: int,
    ) -> SubGridNode:
        """노드 조회, 없으면 생성"""
        return self.generate_node(parent_x, parent_y, sx, sy, sz, depth_tier)
