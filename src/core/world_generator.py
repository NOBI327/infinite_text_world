"""
ITW Core Engine - Module 2: World Generation
=============================================
무한 좌표 기반 맵 노드 및 절차적 생성 시스템

맵은 (x, y) 좌표 기반의 무한 그리드이지만,
플레이어에게는 추상적인 위치 목록으로 렌더링됩니다.
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.axiom_system import Axiom, AxiomLoader, AxiomVector, DomainType
from src.core.logging import get_logger

logger = get_logger(__name__)


class NodeTier(Enum):
    """노드 희귀도"""

    COMMON = 1  # 94%
    UNCOMMON = 2  # 5%
    RARE = 3  # 1%


@dataclass
class Resource:
    """노드 내 자원 정의"""

    id: str
    max_amount: int
    current_amount: int
    npc_competition: float = 0.2  # NPC에 의한 일일 소모 확률

    def harvest(self, amount: int) -> int:
        """자원 채취"""
        harvested = min(amount, self.current_amount)
        self.current_amount -= harvested
        return harvested

    def daily_decay(self) -> int:
        """NPC 경쟁에 의한 일일 소모"""
        if random.random() < self.npc_competition:
            decay = int(self.max_amount * random.uniform(0.05, 0.15))
            self.current_amount = max(0, self.current_amount - decay)
            return decay
        return 0

    def regenerate(self, rate: float = 0.1):
        """자연 재생"""
        regen = int(self.max_amount * rate)
        self.current_amount = min(self.max_amount, self.current_amount + regen)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "max": self.max_amount,
            "current": self.current_amount,
            "npc_competition": self.npc_competition,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Resource":
        return cls(
            id=data["id"],
            max_amount=data["max"],
            current_amount=data["current"],
            npc_competition=data.get("npc_competition", 0.2),
        )


@dataclass
class SensoryData:
    """
    노드의 감각 정보 (Fog of War 시스템용)

    플레이어는 좌표가 아닌 감각 힌트를 통해 탐색합니다.
    """

    visual_far: str  # 인접 노드에서 보이는 원거리 묘사
    visual_near: str  # 노드 진입 시 근거리 묘사
    atmosphere: str  # 지배적 Axiom 분위기
    sound_hint: str  # 소리 힌트
    smell_hint: str  # 냄새 힌트

    def to_dict(self) -> Dict:
        return {
            "visual_far": self.visual_far,
            "visual_near": self.visual_near,
            "atmosphere": self.atmosphere,
            "sound_hint": self.sound_hint,
            "smell_hint": self.smell_hint,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SensoryData":
        return cls(
            visual_far=data["visual_far"],
            visual_near=data["visual_near"],
            atmosphere=data["atmosphere"],
            sound_hint=data["sound_hint"],
            smell_hint=data["smell_hint"],
        )


@dataclass
class Echo:
    """
    메모리 이벤트 (Module 3에서 상세 구현)

    노드는 과거 이벤트의 기억을 보존합니다.
    """

    echo_type: str  # "Short" | "Long"
    visibility: str  # "Public" | "Hidden"
    base_difficulty: int  # d6 Dice Pool 기본 난이도 (1-5)
    timestamp: str  # ISO 날짜
    flavor_text: str
    source_player_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "type": self.echo_type,
            "visibility": self.visibility,
            "base_difficulty": self.base_difficulty,
            "timestamp": self.timestamp,
            "flavor_text": self.flavor_text,
            "source_player_id": self.source_player_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Echo":
        return cls(
            echo_type=data["type"],
            visibility=data["visibility"],
            base_difficulty=data["base_difficulty"],
            timestamp=data["timestamp"],
            flavor_text=data["flavor_text"],
            source_player_id=data.get("source_player_id"),
        )


@dataclass
class MapNode:
    """
    단일 맵 노드

    무한 그리드의 한 셀을 나타내며,
    Axiom 벡터로 지형/분위기가 결정됩니다.
    """

    x: int
    y: int
    tier: NodeTier
    axiom_vector: AxiomVector
    sensory_data: SensoryData
    resources: List[Resource] = field(default_factory=list)
    echoes: List[Echo] = field(default_factory=list)
    cluster_id: Optional[str] = None
    development_level: int = 0  # Safe Haven(0,0) 전용
    required_tags: List[str] = field(default_factory=list)

    # 메타데이터
    discovered_by: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def coordinate(self) -> str:
        """좌표 문자열 (x_y 형식)"""
        return f"{self.x}_{self.y}"

    @property
    def is_safe_haven(self) -> bool:
        """안전 지대 여부"""
        return self.x == 0 and self.y == 0

    def get_dominant_axiom(self) -> Optional[str]:
        """지배적 Axiom 코드 반환"""
        return self.axiom_vector.get_dominant()

    def add_echo(self, echo: Echo):
        """Echo 추가"""
        self.echoes.append(echo)

    def get_public_echoes(self) -> List[Echo]:
        """공개 Echo만 반환"""
        return [e for e in self.echoes if e.visibility == "Public"]

    def mark_discovered(self, player_id: str):
        """플레이어 발견 기록"""
        if player_id not in self.discovered_by:
            self.discovered_by.append(player_id)

    def to_dict(self) -> Dict:
        """JSON 직렬화"""
        return {
            "coordinate": self.coordinate,
            "tier": self.tier.value,
            "axiom_vector": self.axiom_vector.to_dict(),
            "sensory_data": self.sensory_data.to_dict(),
            "resources": [r.to_dict() for r in self.resources],
            "echoes": [e.to_dict() for e in self.echoes],
            "cluster_id": self.cluster_id,
            "development_level": self.development_level,
            "discovered_by": self.discovered_by,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MapNode":
        """JSON에서 복원"""
        coords = data["coordinate"].split("_")
        return cls(
            x=int(coords[0]),
            y=int(coords[1]),
            tier=NodeTier(data["tier"]),
            axiom_vector=AxiomVector.from_dict(data["axiom_vector"]),
            sensory_data=SensoryData.from_dict(data["sensory_data"]),
            resources=[Resource.from_dict(r) for r in data.get("resources", [])],
            echoes=[Echo.from_dict(e) for e in data.get("echoes", [])],
            cluster_id=data.get("cluster_id"),
            development_level=data.get("development_level", 0),
            discovered_by=data.get("discovered_by", []),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def to_json(self) -> str:
        """JSON 문자열로 직렬화"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class WorldGenerator:
    """
    절차적 월드 생성기

    주요 기능:
    1. 희귀도 분포 (94% / 5% / 1%)
    2. 클러스터 상속 (인접 노드의 Axiom 상속)
    3. Safe Haven (0,0) 특수 생성
    """

    # Safe Haven 좌표 목록
    SAFE_HAVEN_COORDS = [(0, 0)]

    # 희귀도 분포
    RARITY_WEIGHTS = {NodeTier.COMMON: 94, NodeTier.UNCOMMON: 5, NodeTier.RARE: 1}

    # 클러스터 상속 확률
    CLUSTER_INHERITANCE_CHANCE = 0.4

    # 도메인별 감각 템플릿
    SENSORY_TEMPLATES = {
        DomainType.PRIMORDIAL: {
            "atmosphere": ["원초적 에너지가 느껴진다", "원소의 힘이 소용돌이친다"],
            "sound": ["지직거리는 소리", "으르렁거리는 울림"],
            "smell": ["타는 냄새", "오존 냄새"],
        },
        DomainType.MATERIAL: {
            "atmosphere": ["단단한 물질의 기운", "견고함이 느껴진다"],
            "sound": ["부딪히는 소리", "삐걱거리는 소리"],
            "smell": ["금속 냄새", "흙 냄새"],
        },
        DomainType.FORCE: {
            "atmosphere": ["역동적인 힘의 흐름", "운동 에너지가 감지된다"],
            "sound": ["휘파람 소리", "웅웅거리는 진동"],
            "smell": ["바람 냄새", "마찰 냄새"],
        },
        DomainType.ORGANIC: {
            "atmosphere": ["생명의 기운", "유기적 존재감"],
            "sound": ["숨소리", "심장 박동"],
            "smell": ["풀 냄새", "부패 냄새"],
        },
        DomainType.MIND: {
            "atmosphere": ["정신적 압박", "감정의 파동"],
            "sound": ["속삭임", "멀리서 들리는 웃음"],
            "smell": ["향긋한 냄새", "쓴 냄새"],
        },
        DomainType.LOGIC: {
            "atmosphere": ["기계적 질서", "논리적 패턴"],
            "sound": ["딸깍거리는 소리", "기계음"],
            "smell": ["기름 냄새", "무취"],
        },
        DomainType.SOCIAL: {
            "atmosphere": ["사회적 긴장감", "관계의 그물"],
            "sound": ["웅성거림", "발자국 소리"],
            "smell": ["인간의 냄새", "향수 냄새"],
        },
        DomainType.MYSTERY: {
            "atmosphere": ["초월적 기운", "시공간의 왜곡"],
            "sound": ["알 수 없는 울림", "침묵"],
            "smell": ["형언할 수 없는 향기", "무"],
        },
    }

    def __init__(self, axiom_loader: AxiomLoader, seed: Optional[int] = None):
        self.axiom_loader = axiom_loader
        self.nodes: Dict[str, MapNode] = {}
        self.seed = seed

        if seed:
            random.seed(seed)

        # Safe Haven 자동 생성
        self._generate_safe_haven()

    def _get_coord_seed(self, x: int, y: int) -> int:
        """좌표 기반 결정론적 시드 생성"""
        return hash((self.seed, x, y)) & 0xFFFFFFFF

    def _generate_safe_haven(self):
        """시작 지점 (0, 0) - Safe Haven 생성"""
        vector = AxiomVector()

        # Safe Haven의 Axiom 구성: 질서 + 생명 + 빛
        vector.add("axiom_ordo", 0.8)  # 질서
        vector.add("axiom_vita", 0.6)  # 생명력
        vector.add("axiom_lux", 0.5)  # 빛
        vector.add("axiom_pax", 0.4)  # 평화 (Social에 추가 필요)
        vector.add("axiom_fides", 0.3)  # 신뢰

        sensory = SensoryData(
            visual_far="따스한 빛이 새어나오는 안식처",
            visual_near="정돈된 광장과 환영의 표지판이 보인다. 이곳은 모든 모험의 시작점이다.",
            atmosphere="평화롭고 안전한 기운",
            sound_hint="활기찬 웅성거림과 대장장이의 망치 소리",
            smell_hint="구운 빵과 허브의 향기",
        )

        # 기본 자원 (Safe Haven용)
        resources = [
            Resource(
                id="res_basic_supply",
                max_amount=1000,
                current_amount=1000,
                npc_competition=0,
            ),
            Resource(
                id="res_healing_herb",
                max_amount=50,
                current_amount=50,
                npc_competition=0.05,
            ),
        ]

        node = MapNode(
            x=0,
            y=0,
            tier=NodeTier.COMMON,
            axiom_vector=vector,
            sensory_data=sensory,
            resources=resources,
            cluster_id="cls_safe_haven",
            development_level=1,
        )

        self.nodes["0_0"] = node
        logger.info("Safe Haven (0,0) generated")

    def _roll_rarity(self) -> NodeTier:
        """희귀도 롤 (94/5/1 분포)"""
        roll = random.randint(1, 100)
        if roll <= 94:
            return NodeTier.COMMON
        elif roll <= 99:
            return NodeTier.UNCOMMON
        else:
            return NodeTier.RARE

    def _get_neighbors(self, x: int, y: int) -> List[Optional[MapNode]]:
        """인접 4방향 노드 조회"""
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # N, S, E, W
        neighbors = []
        for dx, dy in directions:
            coord = f"{x + dx}_{y + dy}"
            neighbors.append(self.nodes.get(coord))
        return neighbors

    def _select_axioms_by_tier(self, tier: NodeTier, count: int = 3) -> List[Axiom]:
        """티어에 따른 Axiom 선택"""
        if tier == NodeTier.RARE:
            # Rare: Mystery 도메인 포함 가능
            pool = (
                self.axiom_loader.get_by_tier(3)  # Tier 3
                + self.axiom_loader.get_by_domain(DomainType.MYSTERY)
            )
        elif tier == NodeTier.UNCOMMON:
            # Uncommon: Tier 2 중심
            pool = self.axiom_loader.get_by_tier(2) + random.sample(
                self.axiom_loader.get_by_tier(1),
                min(10, len(self.axiom_loader.get_by_tier(1))),
            )
        else:
            # Common: Tier 1 중심
            pool = self.axiom_loader.get_by_tier(1)

        # 중복 제거 후 샘플링
        pool = list({a.id: a for a in pool}.values())
        return random.sample(pool, min(count, len(pool)))

    def _generate_vector(
        self, tier: NodeTier, inherited_vector: Optional[AxiomVector] = None
    ) -> AxiomVector:
        """
        Axiom 벡터 생성

        클러스터 상속 시 기존 벡터와 병합됩니다.
        """
        vector = AxiomVector()

        # 1~4개의 Axiom 선택
        axiom_count = random.randint(1, 4)
        selected = self._select_axioms_by_tier(tier, axiom_count)

        # 가중치 할당
        for i, axiom in enumerate(selected):
            # 첫 번째 Axiom이 가장 강함
            weight = 0.8 - (i * 0.15)
            weight = max(0.2, weight + random.uniform(-0.1, 0.1))
            vector.add(axiom.code, weight)

        # 클러스터 상속 병합
        if inherited_vector:
            vector = vector.merge_with(inherited_vector, ratio=0.6)

        return vector

    def _generate_sensory(self, vector: AxiomVector, tier: NodeTier) -> SensoryData:
        """감각 데이터 생성"""
        # 지배적 Axiom 기반 도메인 결정
        dominant_code = vector.get_dominant()
        dominant_axiom = (
            self.axiom_loader.get_by_code(dominant_code) if dominant_code else None
        )

        domain = dominant_axiom.domain if dominant_axiom else DomainType.PRIMORDIAL
        templates = self.SENSORY_TEMPLATES.get(
            domain, self.SENSORY_TEMPLATES[DomainType.PRIMORDIAL]
        )

        # 티어에 따른 묘사 강도
        tier_prefix = {
            NodeTier.COMMON: "",
            NodeTier.UNCOMMON: "특이한 ",
            NodeTier.RARE: "경이로운 ",
        }

        atmosphere = random.choice(templates["atmosphere"])
        sound = random.choice(templates["sound"])
        smell = random.choice(templates["smell"])

        axiom_name = dominant_axiom.name_kr if dominant_axiom else "알 수 없는"

        return SensoryData(
            visual_far=f"{tier_prefix[tier]}{axiom_name}의 기운이 느껴지는 지역",
            visual_near=f"{axiom_name}의 영향이 지배하는 공간. {atmosphere}",
            atmosphere=axiom_name,
            sound_hint=sound,
            smell_hint=smell,
        )

    def _generate_resources(
        self, vector: AxiomVector, tier: NodeTier
    ) -> List[Resource]:
        """노드 자원 생성"""
        resources: List[Resource] = []

        # 지배 Axiom에 따른 자원 결정
        dominant_code = vector.get_dominant()
        dominant_axiom = (
            self.axiom_loader.get_by_code(dominant_code) if dominant_code else None
        )

        if not dominant_axiom:
            return resources

        # 도메인별 기본 자원
        domain_resources = {
            DomainType.PRIMORDIAL: ["res_elemental_essence", "res_mana_crystal"],
            DomainType.MATERIAL: ["res_ore", "res_stone", "res_wood"],
            DomainType.FORCE: ["res_kinetic_core", "res_momentum_shard"],
            DomainType.ORGANIC: ["res_herb", "res_hide", "res_meat"],
            DomainType.MIND: ["res_psychic_residue", "res_memory_fragment"],
            DomainType.LOGIC: ["res_circuit", "res_gear", "res_crystal_chip"],
            DomainType.SOCIAL: ["res_coin", "res_contract", "res_reputation_token"],
            DomainType.MYSTERY: ["res_void_essence", "res_temporal_shard"],
        }

        # 자원 생성 (티어에 따라 양 결정)
        base_resources = domain_resources.get(dominant_axiom.domain, [])
        tier_multiplier = {NodeTier.COMMON: 1, NodeTier.UNCOMMON: 2, NodeTier.RARE: 5}

        for res_id in base_resources[: random.randint(1, 2)]:
            base_amount = random.randint(20, 50) * tier_multiplier[tier]
            resources.append(
                Resource(
                    id=res_id,
                    max_amount=base_amount,
                    current_amount=base_amount,
                    npc_competition=0.1 + (0.1 * (3 - tier.value)),  # Rare는 경쟁 낮음
                )
            )

        return resources

    def generate_node(self, x: int, y: int, force: bool = False) -> MapNode:
        """
        특정 좌표에 노드 생성

        Args:
            x, y: 좌표
            force: True면 기존 노드 덮어씀

        Returns:
            생성된 MapNode
        """
        coord = f"{x}_{y}"

        # 이미 존재하면 반환
        if coord in self.nodes and not force:
            return self.nodes[coord]

        # Safe Haven 특수 처리
        if x == 0 and y == 0:
            return self.nodes["0_0"]

        # 좌표 기반 결정론적 시드 설정
        random.seed(self._get_coord_seed(x, y))

        # 인접 노드 확인 (클러스터 상속)
        neighbors = [n for n in self._get_neighbors(x, y) if n is not None]

        inherited_vector = None
        inherited_tier = None
        cluster_id = None

        if neighbors and random.random() < self.CLUSTER_INHERITANCE_CHANCE:
            # 클러스터 상속
            parent = random.choice(neighbors)
            inherited_vector = parent.axiom_vector
            inherited_tier = parent.tier
            cluster_id = parent.cluster_id

        # 희귀도 결정
        tier = inherited_tier if inherited_tier else self._roll_rarity()

        # Axiom 벡터 생성
        vector = self._generate_vector(tier, inherited_vector)

        # 클러스터 ID 생성 (새로운 클러스터)
        if not cluster_id:
            dominant = vector.get_dominant()
            cluster_id = (
                f"cls_{dominant}_{x}_{y}" if dominant else f"cls_unknown_{x}_{y}"
            )

        # 감각 데이터 생성
        sensory = self._generate_sensory(vector, tier)

        # 자원 생성
        resources = self._generate_resources(vector, tier)

        # 노드 생성
        node = MapNode(
            x=x,
            y=y,
            tier=tier,
            axiom_vector=vector,
            sensory_data=sensory,
            resources=resources,
            cluster_id=cluster_id,
        )

        self.nodes[coord] = node
        return node

    def generate_area(
        self, center_x: int, center_y: int, radius: int = 2
    ) -> List[MapNode]:
        """
        특정 중심점 주변 영역 생성

        탐색 시 주변 노드 미리 생성용
        """
        generated = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                node = self.generate_node(center_x + dx, center_y + dy)
                generated.append(node)
        return generated

    def get_node(self, x: int, y: int) -> Optional[MapNode]:
        """노드 조회 (없으면 None)"""
        return self.nodes.get(f"{x}_{y}")

    def get_or_generate(self, x: int, y: int) -> MapNode:
        """노드 조회, 없으면 생성"""
        return self.generate_node(x, y)

    def get_stats(self) -> Dict[str, Any]:
        """월드 통계"""
        if not self.nodes:
            return {"total": 0}

        tier_counts = {t.name: 0 for t in NodeTier}
        for node in self.nodes.values():
            tier_counts[node.tier.name] += 1

        return {
            "total_nodes": len(self.nodes),
            "tier_distribution": tier_counts,
            "unique_clusters": len(
                set(n.cluster_id for n in self.nodes.values() if n.cluster_id)
            ),
        }


# === 테스트 코드 ===

if __name__ == "__main__":
    from src.core.logging import setup_logging

    setup_logging("DEBUG")

    # Axiom 로더 초기화
    loader = AxiomLoader("itw_214_divine_axioms.json")

    # 월드 생성기 초기화
    world = WorldGenerator(loader, seed=42)

    # Safe Haven 확인
    haven = world.get_node(0, 0)
    logger.info("=== Safe Haven (0,0) ===")
    if haven:
        logger.info("Tier: %s", haven.tier.name)
        logger.info("Dominant Axiom: %s", haven.get_dominant_axiom())
        logger.info("Sensory - Near: %s", haven.sensory_data.visual_near)

    # 주변 영역 생성
    logger.info("=== Generating Area (radius=3) ===")
    world.generate_area(0, 0, radius=3)

    # 통계
    stats = world.get_stats()
    logger.info("World Stats:")
    logger.info("  Total Nodes: %d", stats["total_nodes"])
    logger.info("  Tier Distribution: %s", stats["tier_distribution"])
    logger.info("  Unique Clusters: %d", stats["unique_clusters"])

    # 샘플 노드 출력
    logger.info("=== Sample Nodes ===")
    for coord, node in list(world.nodes.items())[:5]:
        logger.info("[%s] Tier %s", coord, node.tier.name)
        logger.info("  Dominant: %s", node.get_dominant_axiom())
        logger.info("  Far View: %s", node.sensory_data.visual_far)
        logger.info("  Resources: %d", len(node.resources))
