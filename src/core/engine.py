"""
ITW Core Engine - Main Entry Point
==================================
Infinite Text World 핵심 엔진 통합 모듈

이 모듈은 모든 하위 시스템을 통합하여
게임 세션을 관리합니다.
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

# 엔진 모듈 임포트
from src.core.axiom_system import AxiomLoader, AxiomVector
from src.core.core_rule import CharacterSheet, ResolutionEngine, StatType
from src.core.echo_system import EchoCategory, EchoManager
from src.core.logging import get_logger
from src.core.navigator import Direction, LocationView, Navigator, render_compass
from src.core.sub_grid import SubGridGenerator
from src.core.world_generator import (
    Echo,
    MapNode,
    NodeTier,
    Resource,
    SensoryData,
    WorldGenerator,
)
from src.db.models import EchoModel, MapNodeModel, PlayerModel, ResourceModel

logger = get_logger(__name__)


def _node_to_model(node: MapNode) -> MapNodeModel:
    """MapNode를 MapNodeModel로 변환"""
    return MapNodeModel(
        coordinate=node.coordinate,
        x=node.x,
        y=node.y,
        tier=node.tier.value,
        axiom_vector=node.axiom_vector.to_dict(),
        sensory_data=node.sensory_data.to_dict(),
        required_tags=node.required_tags,
        cluster_id=node.cluster_id,
        development_level=node.development_level,
        discovered_by=node.discovered_by,
        created_at=datetime.fromisoformat(node.created_at)
        if isinstance(node.created_at, str)
        else node.created_at,
    )


def _model_to_node(model: MapNodeModel) -> MapNode:
    """MapNodeModel을 MapNode로 변환"""
    # Resources 변환
    resources = [
        Resource(
            id=res.resource_type,
            max_amount=res.max_amount,
            current_amount=res.current_amount,
            npc_competition=res.npc_competition,
        )
        for res in model.resources
    ]

    # Echoes 변환
    echoes = [
        Echo(
            echo_type=echo.echo_type,
            visibility=echo.visibility,
            base_dc=echo.base_dc,
            timestamp=echo.timestamp,
            flavor_text=echo.flavor_text,
            source_player_id=echo.source_player_id,
        )
        for echo in model.echoes
    ]

    # SensoryData 변환
    sensory_data = SensoryData.from_dict(model.sensory_data)

    # AxiomVector 변환
    axiom_vector = AxiomVector.from_dict(model.axiom_vector)

    return MapNode(
        x=model.x,
        y=model.y,
        tier=NodeTier(model.tier),
        axiom_vector=axiom_vector,
        sensory_data=sensory_data,
        resources=resources,
        echoes=echoes,
        cluster_id=model.cluster_id,
        development_level=model.development_level,
        required_tags=model.required_tags or [],
        discovered_by=model.discovered_by or [],
        created_at=model.created_at.isoformat()
        if model.created_at
        else datetime.utcnow().isoformat(),
    )


def _character_to_dict(character: CharacterSheet) -> dict:
    """CharacterSheet를 dict로 직렬화"""
    return {
        "name": character.name,
        "level": character.level,
        "stats": {stat.value: val for stat, val in character.stats.items()},
        "resonance_shield": character.resonance_shield,
        "status_tags": character.status_tags,
    }


def _dict_to_character(data: dict) -> CharacterSheet:
    """dict에서 CharacterSheet 복원"""
    character = CharacterSheet(name=data["name"])
    character.level = data.get("level", 1)
    character.stats = {StatType(k): v for k, v in data.get("stats", {}).items()}
    character.resonance_shield = data.get(
        "resonance_shield",
        {
            "Kinetic": 10,
            "Thermal": 10,
            "Structural": 10,
            "Bio": 10,
            "Psyche": 10,
            "Data": 10,
            "Social": 10,
            "Esoteric": 10,
        },
    )
    character.status_tags = data.get("status_tags", [])
    return character


def _player_to_model(player: "PlayerState") -> PlayerModel:
    """PlayerState를 PlayerModel로 변환"""
    character = player.character or CharacterSheet(name=player.player_id)
    return PlayerModel(
        player_id=player.player_id,
        x=player.x,
        y=player.y,
        supply=player.supply,
        fame=player.fame,
        character_data=_character_to_dict(character),
        discovered_nodes=player.discovered_nodes,
        inventory=player.inventory,
        equipped_tags=player.equipped_tags,
        active_effects=player.active_effects,
        investigation_penalty=player.investigation_penalty,
        last_action_time=player.last_action_time,
    )


def _model_to_player(model: PlayerModel) -> "PlayerState":
    """PlayerModel을 PlayerState로 변환"""
    character = _dict_to_character(model.character_data)
    return PlayerState(
        player_id=model.player_id,
        x=model.x,
        y=model.y,
        supply=model.supply,
        fame=model.fame,
        discovered_nodes=model.discovered_nodes or [],
        inventory=model.inventory or {},
        active_effects=model.active_effects or [],
        investigation_penalty=model.investigation_penalty,
        last_action_time=model.last_action_time or datetime.utcnow().isoformat(),
        character=character,
        equipped_tags=model.equipped_tags or [],
    )


@dataclass
class PlayerState:
    """플레이어 상태"""

    player_id: str
    x: int = 0
    y: int = 0
    supply: int = 20
    fame: int = 0
    discovered_nodes: list[str] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=dict)
    active_effects: list[dict] = field(default_factory=list)
    investigation_penalty: int = 0
    last_action_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    character: Optional[CharacterSheet] = None
    equipped_tags: list[str] = field(default_factory=list)

    # 서브 그리드 상태
    in_sub_grid: bool = False
    sub_grid_parent: Optional[str] = None  # "x_y" 형식
    sub_x: int = 0
    sub_y: int = 0
    sub_z: int = 0

    def __post_init__(self):
        if self.character is None:
            self.character = CharacterSheet(name=self.player_id)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "position": {"x": self.x, "y": self.y},
            "supply": self.supply,
            "fame": self.fame,
            "discovered_nodes": self.discovered_nodes,
            "inventory": self.inventory,
            "active_effects": self.active_effects,
            "investigation_penalty": self.investigation_penalty,
            "last_action_time": self.last_action_time,
            "in_sub_grid": self.in_sub_grid,
            "sub_grid_parent": self.sub_grid_parent,
            "sub_position": {"sx": self.sub_x, "sy": self.sub_y, "sz": self.sub_z},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerState":
        sub_pos = data.get("sub_position", {})
        return cls(
            player_id=data["player_id"],
            x=data["position"]["x"],
            y=data["position"]["y"],
            supply=data.get("supply", 20),
            fame=data.get("fame", 0),
            discovered_nodes=data.get("discovered_nodes", []),
            inventory=data.get("inventory", {}),
            active_effects=data.get("active_effects", []),
            investigation_penalty=data.get("investigation_penalty", 0),
            last_action_time=data.get(
                "last_action_time", datetime.utcnow().isoformat()
            ),
            in_sub_grid=data.get("in_sub_grid", False),
            sub_grid_parent=data.get("sub_grid_parent"),
            sub_x=sub_pos.get("sx", 0),
            sub_y=sub_pos.get("sy", 0),
            sub_z=sub_pos.get("sz", 0),
        )


@dataclass
class ActionResult:
    """행동 결과"""

    success: bool
    action_type: str
    message: str
    data: Optional[dict] = None
    location_view: Optional[LocationView] = None

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "action": self.action_type,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        if self.location_view:
            result["location"] = self.location_view.to_dict()
        return result


class ITWEngine:
    """
    Infinite Text World 메인 엔진

    모든 게임 시스템을 통합하고 게임 세션을 관리합니다.
    """

    VERSION = "0.1.0-alpha"

    def __init__(
        self,
        axiom_data_path: str = "itw_214_divine_axioms.json",
        world_seed: Optional[int] = None,
    ):
        """
        엔진 초기화

        Args:
            axiom_data_path: Axiom 데이터 JSON 경로
            world_seed: 월드 생성 시드 (재현성)
        """
        logger.info("Initializing v%s...", self.VERSION)

        # 코어 시스템 초기화
        self.axiom_loader = AxiomLoader(axiom_data_path)
        self.world = WorldGenerator(self.axiom_loader, seed=world_seed)
        self.sub_grid_generator = SubGridGenerator(
            self.axiom_loader, seed=world_seed or 0
        )
        self.navigator = Navigator(
            self.world, self.axiom_loader, self.sub_grid_generator
        )
        self.echo_manager = EchoManager(self.axiom_loader)
        self.resolution_engine = ResolutionEngine()

        # 플레이어 세션
        self.players: dict[str, PlayerState] = {}

        # 글로벌 이벤트 로그
        self.global_hooks: list[dict] = []

        logger.info("Ready. %d Axioms loaded.", len(self.axiom_loader.get_all()))

    # === 플레이어 관리 ===

    def register_player(self, player_id: str) -> PlayerState:
        """새 플레이어 등록"""
        if player_id in self.players:
            return self.players[player_id]

        player = PlayerState(player_id=player_id, x=0, y=0, supply=20, fame=0)
        self.players[player_id] = player

        # Safe Haven 발견 마킹
        haven = self.world.get_node(0, 0)
        if haven:
            haven.mark_discovered(player_id)
            player.discovered_nodes.append("0_0")

        logger.info("Player registered: %s", player_id)
        return player

    def get_player(self, player_id: str) -> Optional[PlayerState]:
        """플레이어 상태 조회"""
        return self.players.get(player_id)

    def save_player(self, player_id: str, filepath: str):
        """플레이어 상태 저장"""
        player = self.get_player(player_id)
        if not player:
            raise ValueError(f"Player not found: {player_id}")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(player.to_dict(), f, ensure_ascii=False, indent=2)

    def load_player(self, filepath: str) -> PlayerState:
        """플레이어 상태 로드"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        player = PlayerState.from_dict(data)
        self.players[player.player_id] = player
        return player

    # === 핵심 게임 액션 ===

    def look(self, player_id: str) -> ActionResult:
        """현재 위치 관찰"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "look", "플레이어를 찾을 수 없습니다.")

        view = self.navigator.get_location_view(player.x, player.y, player_id)

        return ActionResult(
            success=True,
            action_type="look",
            message="주변을 둘러본다...",
            location_view=view,
        )

    def move(self, player_id: str, direction: str) -> ActionResult:
        """이동"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "move", "플레이어를 찾을 수 없습니다.")

        if player.in_sub_grid:
            # 서브 그리드 내 이동 (up/down 포함)
            return self._move_in_sub_grid(player, direction)
        else:
            # 메인 그리드 이동
            return self._move_in_main_grid(player, direction)

    def _move_in_main_grid(self, player: PlayerState, direction: str) -> ActionResult:
        """메인 그리드 내 이동"""
        # 방향 파싱 (메인 그리드는 N/S/E/W만)
        direction_map = {
            "n": Direction.NORTH,
            "north": Direction.NORTH,
            "북": Direction.NORTH,
            "s": Direction.SOUTH,
            "south": Direction.SOUTH,
            "남": Direction.SOUTH,
            "e": Direction.EAST,
            "east": Direction.EAST,
            "동": Direction.EAST,
            "w": Direction.WEST,
            "west": Direction.WEST,
            "서": Direction.WEST,
        }

        dir_enum = direction_map.get(direction.lower())
        if not dir_enum:
            return ActionResult(False, "move", f"알 수 없는 방향: {direction}")

        # 이동 실행
        result = self.navigator.travel(
            player.x,
            player.y,
            dir_enum,
            player.player_id,
            player.supply,
            player_inventory=player.equipped_tags,
        )

        if result.success:
            # 플레이어 상태 업데이트
            player.x += dir_enum.dx
            player.y += dir_enum.dy
            player.supply -= result.supply_consumed

            # 발견 노드 기록
            coord = f"{player.x}_{player.y}"
            if coord not in player.discovered_nodes:
                player.discovered_nodes.append(coord)

            player.last_action_time = datetime.utcnow().isoformat()

            # 탐험 Echo 생성
            current_node = self.world.get_node(player.x, player.y)
            if current_node:
                self.echo_manager.create_echo(
                    EchoCategory.EXPLORATION, current_node, player.player_id
                )

            data: dict[str, Any] = {
                "supply_consumed": result.supply_consumed,
                "remaining_supply": player.supply,
            }
            if result.encounter:
                data["encounter"] = result.encounter

            return ActionResult(
                success=True,
                action_type="move",
                message=result.message,
                data=data,
                location_view=result.new_location,
            )
        else:
            return ActionResult(
                success=False, action_type="move", message=result.message
            )

    def _move_in_sub_grid(self, player: PlayerState, direction: str) -> ActionResult:
        """서브 그리드 내 이동 (up/down 포함)"""
        # 방향 파싱 (서브 그리드는 N/S/E/W + UP/DOWN)
        direction_map = {
            "n": Direction.NORTH,
            "north": Direction.NORTH,
            "북": Direction.NORTH,
            "s": Direction.SOUTH,
            "south": Direction.SOUTH,
            "남": Direction.SOUTH,
            "e": Direction.EAST,
            "east": Direction.EAST,
            "동": Direction.EAST,
            "w": Direction.WEST,
            "west": Direction.WEST,
            "서": Direction.WEST,
            "up": Direction.UP,
            "u": Direction.UP,
            "위": Direction.UP,
            "down": Direction.DOWN,
            "d": Direction.DOWN,
            "아래": Direction.DOWN,
        }

        dir_enum = direction_map.get(direction.lower())
        if not dir_enum:
            return ActionResult(False, "move", f"알 수 없는 방향: {direction}")

        # 부모 좌표 파싱
        parent_coords = (
            player.sub_grid_parent.split("_") if player.sub_grid_parent else ["0", "0"]
        )
        parent_x = int(parent_coords[0])
        parent_y = int(parent_coords[1])

        # 부모 노드에서 depth_tier 가져오기
        parent_node = self.world.get_node(parent_x, parent_y)
        depth_tier = parent_node.tier.value if parent_node else 1

        # 서브 그리드 이동 실행
        result = self.navigator.travel_sub_grid(
            parent_x=parent_x,
            parent_y=parent_y,
            sx=player.sub_x,
            sy=player.sub_y,
            sz=player.sub_z,
            direction=dir_enum,
            depth_tier=depth_tier,
            current_supply=player.supply,
            player_inventory=player.equipped_tags,
        )

        if result.success:
            # 플레이어 상태 업데이트
            player.sub_x += dir_enum.dx
            player.sub_y += dir_enum.dy
            player.sub_z += dir_enum.dz
            player.supply -= result.supply_consumed
            player.last_action_time = datetime.utcnow().isoformat()

            data: dict[str, Any] = {
                "supply_consumed": result.supply_consumed,
                "remaining_supply": player.supply,
                "sub_position": {
                    "sx": player.sub_x,
                    "sy": player.sub_y,
                    "sz": player.sub_z,
                },
            }

            return ActionResult(
                success=True,
                action_type="move",
                message=result.message,
                data=data,
                location_view=result.new_location,
            )
        else:
            return ActionResult(
                success=False, action_type="move", message=result.message
            )

    def investigate(self, player_id: str, echo_index: int = 0) -> ActionResult:
        """Echo 조사"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "investigate", "플레이어를 찾을 수 없습니다.")

        node = self.world.get_node(player.x, player.y)
        if not node:
            return ActionResult(False, "investigate", "현재 위치를 찾을 수 없습니다.")

        # 숨겨진 Echo 목록
        hidden_echoes = self.echo_manager.get_hidden_echoes(node)
        if not hidden_echoes:
            return ActionResult(
                success=False,
                action_type="investigate",
                message="조사할 숨겨진 흔적이 없습니다.",
            )

        if echo_index >= len(hidden_echoes):
            return ActionResult(
                success=False,
                action_type="investigate",
                message=f"유효하지 않은 흔적 번호: {echo_index}",
            )

        echo = hidden_echoes[echo_index]

        # 1d20 + 조사 보너스 (간략화)
        roll = random.randint(1, 20) + (player.fame // 20)

        # 페널티 적용
        roll -= player.investigation_penalty

        result = self.echo_manager.investigate(
            echo, roll=roll, investigator_fame=player.fame, bonus_modifiers=0
        )

        # 페널티 처리
        if result.get("penalty"):
            player.investigation_penalty = 2
        else:
            player.investigation_penalty = max(0, player.investigation_penalty - 1)

        player.last_action_time = datetime.utcnow().isoformat()

        return ActionResult(
            success=result["success"],
            action_type="investigate",
            message="흔적을 조사한다..." if result["success"] else "조사에 실패했다...",
            data=result,
        )

    def harvest(
        self, player_id: str, resource_id: str, amount: int = 1
    ) -> ActionResult:
        """자원 채취"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "harvest", "플레이어를 찾을 수 없습니다.")

        node = self.world.get_node(player.x, player.y)
        if not node:
            return ActionResult(False, "harvest", "현재 위치를 찾을 수 없습니다.")

        # 자원 찾기
        resource = None
        for res in node.resources:
            if res.id == resource_id:
                resource = res
                break

        if not resource:
            return ActionResult(
                success=False,
                action_type="harvest",
                message=f"해당 자원을 찾을 수 없습니다: {resource_id}",
            )

        if resource.current_amount <= 0:
            return ActionResult(
                success=False, action_type="harvest", message="자원이 고갈되었습니다."
            )

        # 채취
        harvested = resource.harvest(amount)

        # 인벤토리에 추가
        player.inventory[resource_id] = player.inventory.get(resource_id, 0) + harvested

        # 채취 Echo 생성
        self.echo_manager.create_echo(EchoCategory.CRAFTING, node, player_id)

        player.last_action_time = datetime.utcnow().isoformat()

        return ActionResult(
            success=True,
            action_type="harvest",
            message=f"{resource_id} {harvested}개를 채취했습니다.",
            data={
                "resource": resource_id,
                "harvested": harvested,
                "remaining": resource.current_amount,
                "inventory": player.inventory.get(resource_id, 0),
            },
        )

    def rest(self, player_id: str) -> ActionResult:
        """휴식 (Supply 회복)"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "rest", "플레이어를 찾을 수 없습니다.")

        node = self.world.get_node(player.x, player.y)
        if not node:
            return ActionResult(False, "rest", "현재 위치를 찾을 수 없습니다.")

        old_supply = player.supply

        # Safe Haven에서만 완전 회복
        if node.is_safe_haven:
            player.supply = 20
            recovery = player.supply - old_supply
            message = f"안전 지대에서 완전히 회복했습니다. (+{recovery} Supply)"
        else:
            # 일반 지역에서는 부분 회복
            player.supply = min(player.supply + 5, 20)
            recovery = player.supply - old_supply
            message = f"휴식을 취했습니다. (+{recovery} Supply)"

        # 페널티 해제
        player.investigation_penalty = 0
        player.last_action_time = datetime.utcnow().isoformat()

        return ActionResult(
            success=True,
            action_type="rest",
            message=message,
            data={"recovery": recovery, "current_supply": player.supply},
        )

    def get_compass(self, player_id: str) -> str:
        """ASCII 나침반 반환"""
        player = self.get_player(player_id)
        if not player:
            return "플레이어를 찾을 수 없습니다."

        view = self.navigator.get_location_view(player.x, player.y, player_id)
        return render_compass(view)

    # === 서브 그리드 진입/탈출 ===

    def enter_depth(self, player_id: str) -> ActionResult:
        """서브 그리드(Depth)로 진입"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "enter", "플레이어를 찾을 수 없습니다.")

        if player.in_sub_grid:
            return ActionResult(False, "enter", "이미 서브 그리드 안에 있습니다.")

        # 현재 노드 확인
        node = self.world.get_node(player.x, player.y)
        if not node:
            return ActionResult(False, "enter", "현재 위치를 찾을 수 없습니다.")

        # Depth 존재 여부 확인 (MapNodeModel의 L3 필드)
        # 현재는 간단히 노드의 tier가 Rare 이상이면 depth가 있다고 가정
        # TODO: 실제 depth_name 필드 확인으로 교체
        has_depth = node.tier in [NodeTier.UNCOMMON, NodeTier.RARE]

        if not has_depth:
            return ActionResult(
                success=False,
                action_type="enter",
                message="이 지역에는 진입할 수 있는 깊은 곳이 없습니다.",
            )

        # 서브 그리드 입구 생성
        depth_tier = node.tier.value  # 기본 난이도 = 노드 티어
        entrance = self.sub_grid_generator.generate_entrance(
            player.x, player.y, depth_tier
        )

        # 플레이어 상태 업데이트
        player.in_sub_grid = True
        player.sub_grid_parent = f"{player.x}_{player.y}"
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = 0
        player.last_action_time = datetime.utcnow().isoformat()

        # 위치 뷰 생성
        sensory = entrance.sensory_data
        location_view = LocationView(
            coordinate_hash=f"sub_{entrance.id[:8]}",
            visual_description=sensory.get("visual_near", "어두운 입구"),
            atmosphere=sensory.get("atmosphere", "알 수 없음"),
            sound=sensory.get("sound_hint", "적막"),
            smell=sensory.get("smell_hint", "습한 냄새"),
            direction_hints=[],
            available_resources=[],
            echoes_visible=[],
            special_features=["🚪 입구", "⬇️ 아래로 내려갈 수 있다"],
        )

        return ActionResult(
            success=True,
            action_type="enter",
            message="깊은 곳으로 진입합니다...",
            data={
                "depth_tier": depth_tier,
                "position": {"sx": 0, "sy": 0, "sz": 0},
            },
            location_view=location_view,
        )

    def exit_depth(self, player_id: str) -> ActionResult:
        """서브 그리드에서 메인 그리드로 복귀"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "exit", "플레이어를 찾을 수 없습니다.")

        if not player.in_sub_grid:
            return ActionResult(False, "exit", "서브 그리드 안에 있지 않습니다.")

        # 입구(sz=0)에서만 탈출 가능
        if player.sub_z != 0:
            return ActionResult(
                success=False,
                action_type="exit",
                message=f"입구까지 올라가야 합니다. (현재: 층 {player.sub_z})",
            )

        # 입구 위치(sx=0, sy=0)에서만 탈출 가능
        if player.sub_x != 0 or player.sub_y != 0:
            return ActionResult(
                success=False,
                action_type="exit",
                message="입구 위치로 이동해야 합니다. (현재 위치에서 벗어남)",
            )

        # 플레이어 상태 업데이트
        player.in_sub_grid = False
        player.sub_grid_parent = None
        player.sub_x = 0
        player.sub_y = 0
        player.sub_z = 0
        player.last_action_time = datetime.utcnow().isoformat()

        # 메인 그리드 위치 뷰
        view = self.navigator.get_location_view(player.x, player.y, player_id)

        return ActionResult(
            success=True,
            action_type="exit",
            message="밖으로 나왔습니다. 햇빛이 눈부시다.",
            location_view=view,
        )

    # === 글로벌 이벤트 ===

    def trigger_global_event(self, player_id: str, event_type: str, description: str):
        """글로벌 이벤트 트리거"""
        player = self.get_player(player_id)
        if not player:
            return

        node = self.world.get_node(player.x, player.y)
        location_hint = node.sensory_data.atmosphere if node else "알 수 없는 장소"

        hook = self.echo_manager.create_global_hook(
            event_type=event_type, location_hint=location_hint, description=description
        )

        self.global_hooks.append(hook)

        # 보스 처치 시 특수 Echo 생성
        if event_type == "boss_kill" and node:
            self.echo_manager.create_echo(
                EchoCategory.BOSS, node, player_id, custom_flavor=description
            )

            # Fame 증가
            player.fame += 100

        logger.info("Global Event: %s - %s", event_type, description)

    def get_active_hooks(self) -> list[dict]:
        """활성 글로벌 훅 목록"""
        now = datetime.utcnow()
        active = []

        for hook in self.global_hooks:
            created = datetime.fromisoformat(hook["timestamp"])
            hours_passed = (now - created).total_seconds() / 3600

            if hours_passed < hook.get("expires_in_hours", 24):
                active.append(hook)

        return active

    # === 월드 관리 ===

    def save_world_to_db(self, session: Session) -> int:
        """
        월드 노드를 DB에 저장 (upsert)

        Args:
            session: SQLAlchemy 세션

        Returns:
            저장된 노드 수
        """
        saved_count = 0
        for coord, node in self.world.nodes.items():
            model = _node_to_model(node)

            # Upsert: 기존 노드 확인
            existing = session.get(MapNodeModel, coord)
            if existing:
                # 업데이트
                existing.x = model.x
                existing.y = model.y
                existing.tier = model.tier
                existing.axiom_vector = model.axiom_vector
                existing.sensory_data = model.sensory_data
                existing.required_tags = model.required_tags
                existing.cluster_id = model.cluster_id
                existing.development_level = model.development_level
                existing.discovered_by = model.discovered_by
                existing.created_at = model.created_at

                # 기존 resources/echoes 삭제 후 재생성
                for old_res in existing.resources:
                    session.delete(old_res)
                for old_echo in existing.echoes:
                    session.delete(old_echo)
                session.flush()

                # 새 resources/echoes 추가
                for res in node.resources:
                    new_res_model = ResourceModel(
                        node_coordinate=coord,
                        resource_type=res.id,
                        max_amount=res.max_amount,
                        current_amount=res.current_amount,
                        npc_competition=res.npc_competition,
                    )
                    session.add(new_res_model)

                for echo in node.echoes:
                    new_echo_model = EchoModel(
                        node_coordinate=coord,
                        echo_type=echo.echo_type,
                        visibility=echo.visibility,
                        base_dc=echo.base_dc,
                        timestamp=echo.timestamp,
                        flavor_text=echo.flavor_text,
                        source_player_id=echo.source_player_id,
                    )
                    session.add(new_echo_model)
            else:
                # 새로 삽입
                session.add(model)

                for res in node.resources:
                    new_res = ResourceModel(
                        node_coordinate=coord,
                        resource_type=res.id,
                        max_amount=res.max_amount,
                        current_amount=res.current_amount,
                        npc_competition=res.npc_competition,
                    )
                    session.add(new_res)

                for echo in node.echoes:
                    new_echo = EchoModel(
                        node_coordinate=coord,
                        echo_type=echo.echo_type,
                        visibility=echo.visibility,
                        base_dc=echo.base_dc,
                        timestamp=echo.timestamp,
                        flavor_text=echo.flavor_text,
                        source_player_id=echo.source_player_id,
                    )
                    session.add(new_echo)

            saved_count += 1

        session.commit()
        return saved_count

    def load_world_from_db(self, session: Session) -> int:
        """
        DB에서 월드 노드 로드

        Args:
            session: SQLAlchemy 세션

        Returns:
            로드된 노드 수
        """
        models = session.query(MapNodeModel).all()
        loaded_count = 0

        for model in models:
            node = _model_to_node(model)
            self.world.nodes[node.coordinate] = node
            loaded_count += 1

        return loaded_count

    def save_players_to_db(self, session: Session) -> int:
        """
        플레이어를 DB에 저장 (upsert)

        Args:
            session: SQLAlchemy 세션

        Returns:
            저장된 플레이어 수
        """
        saved_count = 0
        for player_id, player in self.players.items():
            model = _player_to_model(player)

            # Upsert: 기존 플레이어 확인
            existing = session.get(PlayerModel, player_id)
            if existing:
                # 업데이트
                existing.x = model.x
                existing.y = model.y
                existing.supply = model.supply
                existing.fame = model.fame
                existing.character_data = model.character_data
                existing.discovered_nodes = model.discovered_nodes
                existing.inventory = model.inventory
                existing.equipped_tags = model.equipped_tags
                existing.active_effects = model.active_effects
                existing.investigation_penalty = model.investigation_penalty
                existing.last_action_time = model.last_action_time
            else:
                # 새로 삽입
                session.add(model)

            saved_count += 1

        session.commit()
        return saved_count

    def load_players_from_db(self, session: Session) -> int:
        """
        DB에서 플레이어 로드

        Args:
            session: SQLAlchemy 세션

        Returns:
            로드된 플레이어 수
        """
        models = session.query(PlayerModel).all()
        loaded_count = 0

        for model in models:
            player = _model_to_player(model)
            self.players[player.player_id] = player
            loaded_count += 1

        return loaded_count

    def daily_tick(self):
        """일일 월드 업데이트"""
        logger.info("Daily tick processing...")

        # 모든 노드의 자원 갱신 및 Echo 정리
        for coord, node in self.world.nodes.items():
            # 자원 일일 변동
            for resource in node.resources:
                resource.daily_decay()
                resource.regenerate(rate=0.05)

            # Echo 시간 경과 처리
            removed = self.echo_manager.decay_echoes(node)
            if removed > 0:
                logger.debug("[%s] %d echoes decayed", coord, removed)

        logger.info("Daily tick complete")

    def get_world_stats(self) -> dict[str, Any]:
        """월드 통계"""
        world_stats = self.world.get_stats()
        axiom_stats = self.axiom_loader.get_stats()

        return {
            "engine_version": self.VERSION,
            "world": world_stats,
            "axioms": axiom_stats,
            "active_players": len(self.players),
            "global_hooks": len(self.get_active_hooks()),
        }

    # === 디버그 / 개발용 ===

    def debug_teleport(self, player_id: str, x: int, y: int) -> ActionResult:
        """[DEBUG] 텔레포트"""
        player = self.get_player(player_id)
        if not player:
            return ActionResult(False, "debug_teleport", "플레이어를 찾을 수 없습니다.")

        # 목적지 노드 생성
        self.world.get_or_generate(x, y)

        player.x = x
        player.y = y

        view = self.navigator.get_location_view(x, y, player_id)

        return ActionResult(
            success=True,
            action_type="debug_teleport",
            message=f"[DEBUG] 텔레포트 완료: ({x}, {y})",
            location_view=view,
        )

    def debug_generate_area(self, center_x: int, center_y: int, radius: int = 3):
        """[DEBUG] 영역 생성"""
        nodes = self.world.generate_area(center_x, center_y, radius)
        logger.debug(
            "Generated %d nodes around (%d, %d)", len(nodes), center_x, center_y
        )
        return nodes


# === CLI 인터페이스 ===


def run_cli():
    """간단한 CLI 게임 루프"""
    print("\n" + "=" * 50)
    print("  INFINITE TEXT WORLD - CLI Demo")
    print("=" * 50)

    # 엔진 초기화
    engine = ITWEngine(axiom_data_path="itw_214_divine_axioms.json", world_seed=42)

    # 테스트 플레이어 등록
    player_id = "demo_player"
    engine.register_player(player_id)

    # 초기 영역 생성
    engine.debug_generate_area(0, 0, radius=5)

    print(
        "\n명령어: look, move <방향>, investigate, harvest <자원>, rest, compass, stats, quit"
    )
    print("방향: n/s/e/w 또는 north/south/east/west 또는 북/남/동/서\n")

    # 초기 위치 표시
    result = engine.look(player_id)
    if result.location_view:
        print(f"\n{result.location_view.visual_description}")
        print(f"분위기: {result.location_view.atmosphere}")

    while True:
        try:
            player = engine.get_player(player_id)
            prompt = f"\n[Supply: {player.supply} | Fame: {player.fame}] > "
            cmd = input(prompt).strip().lower()

            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0]

            if action == "quit" or action == "q":
                print("게임을 종료합니다...")
                break

            elif action == "look" or action == "l":
                result = engine.look(player_id)
                if result.location_view:
                    view = result.location_view
                    print(f"\n{view.visual_description}")
                    print(f"분위기: {view.atmosphere}")
                    print(f"소리: {view.sound}")
                    print(f"냄새: {view.smell}")
                    if view.special_features:
                        print(f"특징: {', '.join(view.special_features)}")
                    if view.available_resources:
                        print(f"자원: {view.available_resources}")

            elif action == "move" or action == "m":
                if len(parts) < 2:
                    print("방향을 지정하세요. (예: move n)")
                    continue
                direction = parts[1]
                result = engine.move(player_id, direction)
                print(f"\n{result.message}")
                if result.success and result.location_view:
                    print(f"\n{result.location_view.visual_description}")
                if result.data and result.data.get("encounter"):
                    print(f"\n⚠️ {result.data['encounter']['hint']}")

            elif action == "compass" or action == "c":
                print(engine.get_compass(player_id))

            elif action == "investigate" or action == "i":
                result = engine.investigate(player_id)
                print(f"\n{result.message}")
                if result.data:
                    if result.success and result.data.get("discovered_info"):
                        info = result.data["discovered_info"]
                        print(f"  → {info['flavor']}")
                        print(f"  시간: {info['age']}")
                    elif not result.success:
                        print(f"  (DC: {result.data.get('dc', '?')})")

            elif action == "harvest" or action == "h":
                if len(parts) < 2:
                    print("자원 ID를 지정하세요. (예: harvest res_ore)")
                    continue
                resource_id = parts[1]
                amount = int(parts[2]) if len(parts) > 2 else 1
                result = engine.harvest(player_id, resource_id, amount)
                print(f"\n{result.message}")

            elif action == "rest" or action == "r":
                result = engine.rest(player_id)
                print(f"\n{result.message}")

            elif action == "stats":
                stats = engine.get_world_stats()
                print("\n=== 월드 통계 ===")
                print(f"엔진 버전: {stats['engine_version']}")
                print(f"총 노드: {stats['world']['total_nodes']}")
                print(f"티어 분포: {stats['world']['tier_distribution']}")
                print(f"클러스터 수: {stats['world']['unique_clusters']}")

            elif action == "inventory" or action == "inv":
                player = engine.get_player(player_id)
                if player.inventory:
                    print("\n=== 인벤토리 ===")
                    for item, count in player.inventory.items():
                        print(f"  {item}: {count}")
                else:
                    print("\n인벤토리가 비어있습니다.")

            elif action == "help":
                print("\n명령어:")
                print("  look (l)        - 현재 위치 관찰")
                print("  move <방향> (m) - 이동 (n/s/e/w)")
                print("  compass (c)     - 나침반 표시")
                print("  investigate (i) - 흔적 조사")
                print("  harvest <id>    - 자원 채취")
                print("  rest (r)        - 휴식")
                print("  inventory (inv) - 인벤토리")
                print("  stats           - 월드 통계")
                print("  quit (q)        - 종료")

            else:
                print(f"알 수 없는 명령: {action} (help로 도움말 확인)")

        except KeyboardInterrupt:
            print("\n\n게임을 종료합니다...")
            break
        except Exception as e:
            print(f"\n오류 발생: {e}")


# === 메인 실행 ===

if __name__ == "__main__":
    run_cli()
