"""
ITW Core Engine - Module 3: Navigation & Fog of War
====================================================
추상적 탐색 시스템

플레이어는 좌표가 아닌 감각 힌트를 통해 탐색합니다.
이동에는 Supply 아이템이 소모되며, 거리 제한이 있습니다.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from src.core.axiom_system import AxiomLoader
from src.core.logging import get_logger
from src.core.sub_grid import SubGridGenerator, SubGridNode
from src.core.world_generator import MapNode, NodeTier, WorldGenerator

logger = get_logger(__name__)


class Direction(Enum):
    """이동 방향"""

    NORTH = ("N", 0, 1, 0)
    SOUTH = ("S", 0, -1, 0)
    EAST = ("E", 1, 0, 0)
    WEST = ("W", -1, 0, 0)
    UP = ("UP", 0, 0, 1)
    DOWN = ("DOWN", 0, 0, -1)

    def __init__(self, symbol: str, dx: int, dy: int, dz: int = 0):
        self.symbol = symbol
        self.dx = dx
        self.dy = dy
        self.dz = dz


@dataclass
class DirectionHint:
    """방향별 감각 힌트"""

    direction: Direction
    visual_hint: str  # 원거리 시각 힌트
    atmosphere_hint: str  # 분위기 힌트
    danger_level: str  # 위험도 추정 (Safe/Caution/Danger/Unknown)
    distance_hint: str  # 거리감 힌트
    discovered: bool  # 이미 발견한 노드인지

    def to_dict(self) -> Dict:
        return {
            "direction": self.direction.symbol,
            "visual": self.visual_hint,
            "atmosphere": self.atmosphere_hint,
            "danger": self.danger_level,
            "distance": self.distance_hint,
            "discovered": self.discovered,
        }


@dataclass
class LocationView:
    """
    현재 위치 뷰

    플레이어가 보는 현재 위치의 완전한 정보
    """

    coordinate_hash: str  # 노출용 해시 (실제 좌표 아님)
    visual_description: str
    atmosphere: str
    sound: str
    smell: str
    direction_hints: List[DirectionHint]
    available_resources: List[Dict]
    echoes_visible: List[Dict]
    special_features: List[str]

    def to_dict(self) -> Dict:
        return {
            "location_id": self.coordinate_hash,
            "description": {
                "visual": self.visual_description,
                "atmosphere": self.atmosphere,
                "sound": self.sound,
                "smell": self.smell,
            },
            "directions": [h.to_dict() for h in self.direction_hints],
            "resources": self.available_resources,
            "echoes": self.echoes_visible,
            "special": self.special_features,
        }


@dataclass
class TravelResult:
    """이동 결과"""

    success: bool
    new_location: Optional[LocationView]
    supply_consumed: int
    message: str
    encounter: Optional[Dict] = None  # 이동 중 조우 이벤트


class Navigator:
    """
    탐색 시스템

    플레이어의 이동과 Fog of War를 관리합니다.
    좌표는 내부적으로만 사용되며, 플레이어에게는
    감각 기반 힌트만 제공됩니다.
    """

    # 이동당 Supply 소모량
    BASE_SUPPLY_COST = 1

    # 티어별 추가 Supply 소모
    TIER_SUPPLY_MODIFIER = {NodeTier.COMMON: 0, NodeTier.UNCOMMON: 1, NodeTier.RARE: 2}

    # 휴식 시 Supply 회복량
    REST_SUPPLY_RECOVERY = 5

    # 최대 Supply
    MAX_SUPPLY = 20

    # 위험도 판정 Axiom
    DANGER_AXIOMS = [
        "axiom_toxicum",  # 독
        "axiom_necros",  # 사기
        "axiom_morbus",  # 질병
        "axiom_insania",  # 광기
        "axiom_hostilitas",  # 적대
        "axiom_chaos",  # 혼돈
        "axiom_maledictum",  # 저주
    ]

    def __init__(
        self,
        world: WorldGenerator,
        axiom_loader: AxiomLoader,
        sub_grid_generator: Optional[SubGridGenerator] = None,
    ):
        self.world = world
        self.axiom_loader = axiom_loader
        self.sub_grid_generator = sub_grid_generator

    def _hash_coordinate(self, x: int, y: int) -> str:
        """
        좌표를 불투명 해시로 변환

        플레이어에게 실제 좌표를 숨기기 위함
        """
        import hashlib

        raw = f"{x}_{y}_itw_salt"
        return hashlib.md5(raw.encode()).hexdigest()[:8]

    def _estimate_danger(self, node: MapNode) -> str:
        """노드 위험도 추정"""
        if node.is_safe_haven:
            return "Safe"

        # 위험 Axiom 가중치 합산
        danger_score: float = 0.0
        for axiom_code in self.DANGER_AXIOMS:
            danger_score += node.axiom_vector.get(axiom_code)

        # 티어도 위험도에 영향
        danger_score += (node.tier.value - 1) * 0.2

        if danger_score >= 0.6:
            return "Danger"
        elif danger_score >= 0.3:
            return "Caution"
        elif danger_score > 0:
            return "Mild"
        return "Safe"

    def _get_distance_hint(self, from_node: MapNode, to_node: MapNode) -> str:
        """거리감 힌트 생성"""
        # 같은 클러스터면 "가까운"
        if from_node.cluster_id == to_node.cluster_id:
            return "가까운 곳에서"

        # 티어 차이로 "먼" 느낌
        tier_diff = abs(from_node.tier.value - to_node.tier.value)
        if tier_diff >= 2:
            return "아득히 먼 곳에서"
        elif tier_diff == 1:
            return "저 너머에서"
        return "인근에서"

    def _generate_direction_hint(
        self, direction: Direction, current_node: MapNode, player_id: str
    ) -> DirectionHint:
        """방향별 힌트 생성"""
        target_x = current_node.x + direction.dx
        target_y = current_node.y + direction.dy

        # 타겟 노드 가져오기 (없으면 생성)
        target_node = self.world.get_or_generate(target_x, target_y)

        # 발견 여부
        discovered = player_id in target_node.discovered_by

        # 발견한 노드면 더 자세한 힌트
        if discovered:
            visual = target_node.sensory_data.visual_far
            atmosphere = f"{target_node.sensory_data.atmosphere}의 기운"
        else:
            # 미발견 노드는 모호한 힌트
            dominant = target_node.get_dominant_axiom()
            axiom = self.axiom_loader.get_by_code(dominant) if dominant else None

            if axiom:
                visual = f"무언가 {axiom.name_kr}과 관련된 기운이 느껴진다"
                atmosphere = "정체를 알 수 없는 분위기"
            else:
                visual = "알 수 없는 영역"
                atmosphere = "불분명한 기운"

        danger = self._estimate_danger(target_node)
        distance = self._get_distance_hint(current_node, target_node)

        return DirectionHint(
            direction=direction,
            visual_hint=visual,
            atmosphere_hint=atmosphere,
            danger_level=danger,
            distance_hint=distance,
            discovered=discovered,
        )

    def get_location_view(self, x: int, y: int, player_id: str) -> LocationView:
        """
        현재 위치의 전체 뷰 생성

        Args:
            x, y: 현재 좌표 (내부용)
            player_id: 플레이어 ID

        Returns:
            LocationView: 플레이어에게 보여줄 위치 정보
        """
        node = self.world.get_or_generate(x, y)

        # 발견 마킹
        node.mark_discovered(player_id)

        # 방향 힌트 생성
        direction_hints = []
        for direction in Direction:
            hint = self._generate_direction_hint(direction, node, player_id)
            direction_hints.append(hint)

        # 자원 정보 (간략화)
        resources = []
        for res in node.resources:
            if res.current_amount > 0:
                abundance = (
                    "풍부"
                    if res.current_amount > res.max_amount * 0.7
                    else "보통"
                    if res.current_amount > res.max_amount * 0.3
                    else "희소"
                )
                resources.append({"type": res.id, "abundance": abundance})

        # 공개 Echo
        echoes = []
        for echo in node.get_public_echoes():
            echoes.append(
                {
                    "hint": echo.flavor_text[:50] + "..."
                    if len(echo.flavor_text) > 50
                    else echo.flavor_text,
                    "age": "recent" if "T" in echo.timestamp else "old",  # 간략 판정
                }
            )

        # 특수 특징
        special = []
        if node.is_safe_haven:
            special.append("🏠 안전 지대")
            special.append(f"개발 레벨: {node.development_level}")
        if node.tier == NodeTier.RARE:
            special.append("✨ 희귀 지역")
        elif node.tier == NodeTier.UNCOMMON:
            special.append("🔹 특이한 지역")

        return LocationView(
            coordinate_hash=self._hash_coordinate(x, y),
            visual_description=node.sensory_data.visual_near,
            atmosphere=node.sensory_data.atmosphere,
            sound=node.sensory_data.sound_hint,
            smell=node.sensory_data.smell_hint,
            direction_hints=direction_hints,
            available_resources=resources,
            echoes_visible=echoes,
            special_features=special,
        )

    def calculate_travel_cost(self, from_node: MapNode, to_node: MapNode) -> int:
        """이동 비용 계산"""
        base = self.BASE_SUPPLY_COST
        tier_mod = self.TIER_SUPPLY_MODIFIER.get(to_node.tier, 0)

        # 같은 클러스터면 할인
        cluster_discount = 0 if from_node.cluster_id != to_node.cluster_id else -0.5

        return max(1, int(base + tier_mod + cluster_discount))

    def travel(
        self,
        current_x: int,
        current_y: int,
        direction: Direction,
        player_id: str,
        current_supply: int,
        player_inventory: Optional[List[str]] = None,
    ) -> TravelResult:
        """
        특정 방향으로 이동

        Args:
            current_x, current_y: 현재 좌표
            direction: 이동 방향
            player_id: 플레이어 ID
            current_supply: 현재 보유 Supply
            player_inventory: 플레이어 인벤토리 태그 목록

        Returns:
            TravelResult: 이동 결과
        """
        current_node = self.world.get_node(current_x, current_y)
        if not current_node:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message="현재 위치를 찾을 수 없습니다.",
            )

        # 목적지 계산
        new_x = current_x + direction.dx
        new_y = current_y + direction.dy

        # 목적지 노드 생성/조회
        target_node = self.world.get_or_generate(new_x, new_y)

        # 필수 장비 체크
        if player_inventory is None:
            player_inventory = []
        if target_node.required_tags:
            missing = [
                t for t in target_node.required_tags if t not in player_inventory
            ]
            if missing:
                return TravelResult(
                    success=False,
                    new_location=None,
                    supply_consumed=0,
                    message=f"필요한 장비가 없습니다: {', '.join(missing)}",
                )

        # 비용 계산
        cost = self.calculate_travel_cost(current_node, target_node)

        # Supply 체크
        if current_supply < cost:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message=f"Supply가 부족합니다. 필요: {cost}, 보유: {current_supply}",
            )

        # 이동 성공
        new_view = self.get_location_view(new_x, new_y, player_id)

        # 이동 중 조우 체크 (간략 구현)
        encounter = None
        danger = self._estimate_danger(target_node)
        if danger in ["Danger", "Caution"]:
            import random

            if random.random() < 0.2:  # 20% 확률
                encounter = {
                    "type": "random_encounter",
                    "danger_level": danger,
                    "hint": "무언가의 기척이 느껴진다...",
                }

        direction_name = {
            Direction.NORTH: "북쪽",
            Direction.SOUTH: "남쪽",
            Direction.EAST: "동쪽",
            Direction.WEST: "서쪽",
        }

        return TravelResult(
            success=True,
            new_location=new_view,
            supply_consumed=cost,
            message=f"{direction_name[direction]}으로 이동했습니다. Supply -{cost}",
            encounter=encounter,
        )

    def get_nearby_discovered(
        self, x: int, y: int, player_id: str, radius: int = 2
    ) -> List[Dict]:
        """
        주변 발견된 노드 목록

        플레이어가 기억하는 주변 지역 정보
        """
        discovered = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue

                node = self.world.get_node(x + dx, y + dy)
                if node and player_id in node.discovered_by:
                    discovered.append(
                        {
                            "relative_position": f"({dx:+d}, {dy:+d})",
                            "atmosphere": node.sensory_data.atmosphere,
                            "danger": self._estimate_danger(node),
                            "has_resources": len(node.resources) > 0,
                        }
                    )

        return discovered

    def travel_sub_grid(
        self,
        parent_x: int,
        parent_y: int,
        sx: int,
        sy: int,
        sz: int,
        direction: Direction,
        depth_tier: int,
        current_supply: int,
        player_inventory: Optional[List[str]] = None,
    ) -> TravelResult:
        """
        서브 그리드 내 이동

        Args:
            parent_x, parent_y: 부모 메인 노드 좌표
            sx, sy, sz: 현재 서브 그리드 내 좌표
            direction: 이동 방향 (N/S/E/W/UP/DOWN)
            depth_tier: 서브 그리드 기본 난이도
            current_supply: 현재 보유 Supply
            player_inventory: 플레이어 인벤토리 태그 목록

        Returns:
            TravelResult: 이동 결과
        """
        if self.sub_grid_generator is None:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message="서브 그리드 생성기가 초기화되지 않았습니다.",
            )

        # 현재 노드 조회
        current_node = self.sub_grid_generator.get_node(parent_x, parent_y, sx, sy, sz)
        if not current_node:
            current_node = self.sub_grid_generator.generate_node(
                parent_x, parent_y, sx, sy, sz, depth_tier
            )

        # 목적지 좌표 계산
        new_sx = sx + direction.dx
        new_sy = sy + direction.dy
        new_sz = sz + direction.dz

        # 입구에서 exit 시도 체크 (sz=0에서 up)
        if sz == 0 and direction == Direction.UP:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message="입구입니다. 'exit' 명령으로 메인 그리드로 복귀하세요.",
            )

        # 수평 이동 시 범위 체크 (서브 그리드 크기 제한)
        SUB_GRID_SIZE = 5  # -2 ~ +2
        if abs(new_sx) > SUB_GRID_SIZE or abs(new_sy) > SUB_GRID_SIZE:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message="더 이상 갈 수 없습니다. 벽에 막혀 있습니다.",
            )

        # 목적지 노드 생성
        target_node = self.sub_grid_generator.get_or_generate(
            parent_x, parent_y, new_sx, new_sy, new_sz, depth_tier
        )

        # 필수 장비 체크
        if player_inventory is None:
            player_inventory = []
        if target_node.required_tags:
            missing = [
                t for t in target_node.required_tags if t not in player_inventory
            ]
            if missing:
                return TravelResult(
                    success=False,
                    new_location=None,
                    supply_consumed=0,
                    message=f"필요한 장비가 없습니다: {', '.join(missing)}",
                )

        # 이동 비용 계산 (서브 그리드는 기본 비용)
        cost = self.BASE_SUPPLY_COST

        # Supply 체크
        if current_supply < cost:
            return TravelResult(
                success=False,
                new_location=None,
                supply_consumed=0,
                message=f"Supply가 부족합니다. 필요: {cost}, 보유: {current_supply}",
            )

        # 이동 성공 - 간략한 LocationView 생성
        sensory = target_node.sensory_data
        location_view = LocationView(
            coordinate_hash=f"sub_{target_node.id[:8]}",
            visual_description=sensory.get("visual_near", "어두운 통로"),
            atmosphere=sensory.get("atmosphere", "알 수 없음"),
            sound=sensory.get("sound_hint", "적막"),
            smell=sensory.get("smell_hint", "습한 냄새"),
            direction_hints=[],  # 서브 그리드는 힌트 생략
            available_resources=[],
            echoes_visible=[],
            special_features=self._get_sub_grid_features(target_node),
        )

        # 방향 이름
        direction_names = {
            Direction.NORTH: "북쪽",
            Direction.SOUTH: "남쪽",
            Direction.EAST: "동쪽",
            Direction.WEST: "서쪽",
            Direction.UP: "위",
            Direction.DOWN: "아래",
        }

        return TravelResult(
            success=True,
            new_location=location_view,
            supply_consumed=cost,
            message=f"{direction_names[direction]}로 이동했습니다. Supply -{cost}",
        )

    def _get_sub_grid_features(self, node: SubGridNode) -> List[str]:
        """서브 그리드 노드의 특수 특징"""
        features = []

        if node.is_entrance:
            features.append("🚪 입구")
        if node.is_exit:
            features.append("🚪 출구")

        if node.sz < 0:
            features.append(f"⬇️ 지하 {abs(node.sz)}층")
        elif node.sz > 0:
            features.append(f"⬆️ 상층 {node.sz}층")
        else:
            features.append("🏠 지상층")

        tier_icons = {
            "Common": "",
            "Uncommon": "🔹",
            "Rare": "✨",
            "Epic": "💎",
            "Legendary": "🌟",
        }
        icon = tier_icons.get(node.tier, "")
        if icon:
            features.append(f"{icon} {node.tier}")

        return features


# === Compass 표시 유틸리티 ===


def render_compass(location_view: LocationView) -> str:
    """
    ASCII 나침반 렌더링

    플레이어에게 보여줄 방향 힌트를 시각화합니다.
    """
    hints = {h.direction.symbol: h for h in location_view.direction_hints}

    danger_icons = {"Safe": "○", "Mild": "△", "Caution": "◇", "Danger": "☠"}

    n = hints.get("N")
    s = hints.get("S")
    e = hints.get("E")
    w = hints.get("W")

    n_icon = danger_icons.get(n.danger_level, "?") if n else "?"
    s_icon = danger_icons.get(s.danger_level, "?") if s else "?"
    e_icon = danger_icons.get(e.danger_level, "?") if e else "?"
    w_icon = danger_icons.get(w.danger_level, "?") if w else "?"

    compass = f"""
        [{n_icon}] 북
         |
  [{w_icon}]──●──[{e_icon}]
   서   |   동
        [{s_icon}] 남
    """

    details = []
    for d, hint in hints.items():
        discovered_mark = "✓" if hint.discovered else "?"
        details.append(f"  {d} [{discovered_mark}]: {hint.visual_hint}")

    return compass + "\n".join(details)


# === 테스트 코드 ===

if __name__ == "__main__":
    from src.core.logging import setup_logging

    setup_logging("DEBUG")

    # 초기화
    loader = AxiomLoader("itw_214_divine_axioms.json")
    world = WorldGenerator(loader, seed=42)
    navigator = Navigator(world, loader)

    # 주변 영역 생성
    world.generate_area(0, 0, radius=3)

    player_id = "test_player_001"

    # Safe Haven에서 시작
    logger.info("=== Starting at Safe Haven ===")
    view = navigator.get_location_view(0, 0, player_id)
    logger.info("Location: %s", view.coordinate_hash)
    logger.info("Description: %s", view.visual_description)
    logger.info("Special: %s", view.special_features)

    # 나침반 표시
    logger.info("=== Compass ===")
    logger.info(render_compass(view))

    # 북쪽으로 이동
    logger.info("=== Travel North ===")
    result = navigator.travel(0, 0, Direction.NORTH, player_id, current_supply=10)
    logger.info("Success: %s", result.success)
    logger.info("Message: %s", result.message)
    if result.new_location:
        logger.info("New Location: %s", result.new_location.visual_description)
        logger.info("Atmosphere: %s", result.new_location.atmosphere)
    if result.encounter:
        logger.info("Encounter: %s", result.encounter)

    # 주변 발견 노드
    logger.info("=== Nearby Discovered Nodes ===")
    nearby = navigator.get_nearby_discovered(0, 1, player_id)
    for n in nearby[:3]:
        logger.info(
            "  %s: %s [%s]", n["relative_position"], n["atmosphere"], n["danger"]
        )
