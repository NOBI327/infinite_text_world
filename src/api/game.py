"""Game API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.schemas import (
    ActionRequest,
    ActionResponse,
    DirectionInfo,
    ErrorResponse,
    GameStateResponse,
    LocationInfo,
    PlayerInfo,
    RegisterRequest,
)
from src.core.engine import ITWEngine
from src.core.logging import get_logger
from src.services.dialogue_service import DialogueService
from src.services.item_service import ItemService
from src.services.narrative_service import NarrativeService
from src.services.quest_service import QuestService

logger = get_logger(__name__)

router = APIRouter(prefix="/game", tags=["game"])


def get_engine() -> ITWEngine:
    """엔진 인스턴스 반환 (의존성 주입)"""
    from src.main import get_game_engine

    return get_game_engine()


def get_narrative_service(request: Request) -> NarrativeService:
    """NarrativeService 인스턴스 반환 (의존성 주입)"""
    service: NarrativeService = request.app.state.narrative_service
    return service


def get_dialogue_service(request: Request) -> DialogueService:
    """DialogueService 인스턴스 반환 (의존성 주입)"""
    service: DialogueService = request.app.state.dialogue_service
    return service


def get_item_service(request: Request) -> ItemService:
    """ItemService 인스턴스 반환 (의존성 주입)"""
    service: ItemService = request.app.state.item_service
    return service


def get_quest_service(request: Request) -> QuestService:
    """QuestService 인스턴스 반환 (의존성 주입)"""
    service: QuestService = request.app.state.quest_service
    return service


def _build_location_info(location_view) -> LocationInfo:
    """LocationView를 LocationInfo로 변환"""
    return LocationInfo(
        location_id=location_view.coordinate_hash,
        visual=location_view.visual_description,
        atmosphere=location_view.atmosphere,
        sound=location_view.sound,
        smell=location_view.smell,
        special_features=location_view.special_features,
        resources=location_view.available_resources,
        echoes=location_view.echoes_visible,
    )


def _build_direction_info(hint) -> DirectionInfo:
    """DirectionHint를 DirectionInfo로 변환"""
    return DirectionInfo(
        direction=hint.direction.symbol,
        visual_hint=hint.visual_hint,
        atmosphere_hint=hint.atmosphere_hint,
        danger_level=hint.danger_level,
        discovered=hint.discovered,
    )


def _build_player_info(player) -> PlayerInfo:
    """PlayerState를 PlayerInfo로 변환"""
    return PlayerInfo(
        player_id=player.player_id,
        x=player.x,
        y=player.y,
        supply=player.supply,
        fame=player.fame,
        inventory=player.inventory,
        discovered_count=len(player.discovered_nodes),
    )


@router.post("/register", response_model=GameStateResponse)
def register_player(
    request: RegisterRequest,
    engine: ITWEngine = Depends(get_engine),
) -> GameStateResponse:
    """
    플레이어 등록

    새 플레이어를 등록하고 Safe Haven(0,0)에서 시작합니다.
    """
    try:
        player = engine.register_player(request.player_id)

        # 초기 위치 정보 가져오기
        result = engine.look(request.player_id)

        location = None
        directions = []
        if result.location_view:
            location = _build_location_info(result.location_view)
            directions = [
                _build_direction_info(h) for h in result.location_view.direction_hints
            ]

        logger.info("Player registered: %s", request.player_id)

        return GameStateResponse(
            success=True,
            player=_build_player_info(player),
            location=location,
            directions=directions,
        )
    except Exception as e:
        logger.error("Failed to register player: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/state/{player_id}",
    response_model=GameStateResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_game_state(
    player_id: str,
    engine: ITWEngine = Depends(get_engine),
) -> GameStateResponse:
    """
    현재 게임 상태 조회

    플레이어의 현재 위치와 상태 정보를 반환합니다.
    """
    player = engine.get_player(player_id)

    if not player:
        raise HTTPException(status_code=404, detail=f"Player not found: {player_id}")

    try:
        result = engine.look(player_id)

        location = None
        directions = []
        if result.location_view:
            location = _build_location_info(result.location_view)
            directions = [
                _build_direction_info(h) for h in result.location_view.direction_hints
            ]

        return GameStateResponse(
            success=True,
            player=_build_player_info(player),
            location=location,
            directions=directions,
        )
    except Exception as e:
        logger.error("Failed to get game state: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/action",
    response_model=ActionResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def execute_action(
    request: ActionRequest,
    http_request: Request,
    engine: ITWEngine = Depends(get_engine),
) -> ActionResponse:
    """
    게임 액션 실행

    지원 액션:
    - look: 현재 위치 관찰
    - move: 이동 (params: {direction: "n"|"s"|"e"|"w"|"up"|"down"})
    - rest: 휴식
    - investigate: Echo 조사 (params: {echo_index: 0})
    - harvest: 자원 채취 (params: {resource_id: "...", amount: 1})
    - enter: 서브 그리드(Depth) 진입
    - exit: 서브 그리드에서 메인 그리드로 복귀
    - talk: NPC와 대화 시작 (params: {npc_id: "..."})
    - say: 대화 중 발언 (params: {text: "..."})
    - end_talk: 대화 종료
    """
    player = engine.get_player(request.player_id)

    if not player:
        raise HTTPException(
            status_code=404, detail=f"Player not found: {request.player_id}"
        )

    action = request.action.lower()
    params = request.params
    narrative = None

    try:
        # 액션 실행
        if action == "look":
            result = engine.look(request.player_id)
            # Narrative 생성
            narrative_service = get_narrative_service(http_request)
            node_data = {"x": player.x, "y": player.y, "tier": 1}
            player_state = {
                "player_id": player.player_id,
                "supply": player.supply,
                "fame": player.fame,
            }
            narrative = narrative_service.generate_look(node_data, player_state)
        elif action == "move":
            direction = params.get("direction", "")
            if not direction:
                raise HTTPException(
                    status_code=400, detail="Missing 'direction' parameter"
                )
            # 이동 전 노드 정보 저장
            from_node = {"x": player.x, "y": player.y}
            result = engine.move(request.player_id, direction)
            # 이동 성공 시 Narrative 생성
            if result.success:
                updated_player = engine.get_player(request.player_id)
                assert updated_player is not None
                to_node = {"x": updated_player.x, "y": updated_player.y}
                narrative_service = get_narrative_service(http_request)
                narrative = narrative_service.generate_move(
                    from_node, to_node, direction
                )
        elif action == "rest":
            result = engine.rest(request.player_id)
        elif action == "investigate":
            echo_index = params.get("echo_index", 0)
            result = engine.investigate(request.player_id, echo_index)
        elif action == "harvest":
            resource_id = params.get("resource_id", "")
            if not resource_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'resource_id' parameter"
                )
            amount = params.get("amount", 1)
            result = engine.harvest(request.player_id, resource_id, amount)
        elif action == "enter":
            result = engine.enter_depth(request.player_id)
        elif action == "exit":
            result = engine.exit_depth(request.player_id)
        elif action == "talk":
            npc_id = params.get("npc_id", "")
            if not npc_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'npc_id' parameter"
                )
            dialogue_service = get_dialogue_service(http_request)
            session = dialogue_service.start_session(
                player_id=request.player_id,
                npc_id=npc_id,
                node_id=f"{player.x}_{player.y}",
                game_turn=0,
                npc_data=params.get("npc_data", {"name": "NPC", "race": "human"}),
                relationship_data=params.get(
                    "relationship_data", {"status": "stranger", "familiarity": 0}
                ),
                npc_memories=params.get("npc_memories", []),
                pc_constraints=params.get("pc_constraints", {}),
            )
            return ActionResponse(
                success=True,
                action=action,
                message=f"Dialogue started with {npc_id}",
                data={
                    "session_id": session.session_id,
                    "budget_total": session.budget_total,
                    "budget_remaining": session.budget_remaining,
                },
                narrative=None,
            )
        elif action == "say":
            text = params.get("text", "")
            if not text:
                raise HTTPException(status_code=400, detail="Missing 'text' parameter")
            dialogue_service = get_dialogue_service(http_request)
            turn_result = dialogue_service.process_turn(text)
            return ActionResponse(
                success=True,
                action=action,
                message="Dialogue turn processed",
                data={
                    "session_status": turn_result["session_status"],
                    "turn_index": turn_result["turn_index"],
                },
                narrative=turn_result["narrative"],
            )
        elif action == "end_talk":
            dialogue_service = get_dialogue_service(http_request)
            end_result = dialogue_service.end_session("ended_by_pc")
            return ActionResponse(
                success=True,
                action=action,
                message="Dialogue ended",
                data=end_result,
                narrative=None,
            )
        elif action == "inventory":
            item_service = get_item_service(http_request)
            instances = item_service.get_instances_by_owner("player", request.player_id)
            items_data = []
            for inst in instances:
                proto = item_service.get_prototype(inst.prototype_id)
                items_data.append(
                    {
                        "instance_id": inst.instance_id,
                        "prototype_id": inst.prototype_id,
                        "name_kr": proto.name_kr if proto else "",
                        "current_durability": inst.current_durability,
                        "bulk": proto.bulk if proto else 0,
                    }
                )
            return ActionResponse(
                success=True,
                action=action,
                message=f"Inventory: {len(items_data)} items",
                data={"items": items_data},
                narrative=None,
            )
        elif action == "pickup":
            instance_id = params.get("instance_id", "")
            if not instance_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'instance_id' parameter"
                )
            item_service = get_item_service(http_request)
            instance = item_service.get_instance(instance_id)
            if instance is None or instance.owner_type != "node":
                raise HTTPException(status_code=400, detail="Item not found on ground")
            stats = {k.value: v for k, v in player.character.stats.items()}
            if not item_service.can_add_to_inventory(
                "player",
                request.player_id,
                instance.prototype_id,
                stats,
            ):
                raise HTTPException(status_code=400, detail="Inventory full")
            item_service.transfer_item(
                instance_id, "player", request.player_id, reason="pickup"
            )
            return ActionResponse(
                success=True,
                action=action,
                message=f"Picked up {instance.prototype_id}",
                data={"instance_id": instance_id},
                narrative=None,
            )
        elif action == "drop":
            instance_id = params.get("instance_id", "")
            if not instance_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'instance_id' parameter"
                )
            item_service = get_item_service(http_request)
            node_id = f"{player.x}_{player.y}"
            item_service.transfer_item(instance_id, "node", node_id, reason="drop")
            return ActionResponse(
                success=True,
                action=action,
                message=f"Dropped item at {node_id}",
                data={"instance_id": instance_id},
                narrative=None,
            )
        elif action == "use":
            instance_id = params.get("instance_id", "")
            if not instance_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'instance_id' parameter"
                )
            item_service = get_item_service(http_request)
            use_result = item_service.use_item(instance_id)
            return ActionResponse(
                success=True,
                action=action,
                message="Item used" if not use_result["broken"] else "Item broken",
                data=use_result,
                narrative=None,
            )
        elif action == "browse":
            container_id = params.get("container_id", "")
            if not container_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'container_id' parameter"
                )
            item_service = get_item_service(http_request)
            instances = item_service.get_instances_by_owner("container", container_id)
            items_data = []
            for inst in instances:
                proto = item_service.get_prototype(inst.prototype_id)
                items_data.append(
                    {
                        "instance_id": inst.instance_id,
                        "prototype_id": inst.prototype_id,
                        "name_kr": proto.name_kr if proto else "",
                        "base_value": proto.base_value if proto else 0,
                    }
                )
            return ActionResponse(
                success=True,
                action=action,
                message=f"Browse: {len(items_data)} items",
                data={"items": items_data},
                narrative=None,
            )
        elif action == "quest_list":
            quest_service = get_quest_service(http_request)
            active = quest_service.get_active_quests()
            quests_data = [
                {
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "quest_type": q.quest_type,
                    "seed_tier": q.seed_tier,
                    "urgency": q.urgency,
                }
                for q in active
            ]
            return ActionResponse(
                success=True,
                action=action,
                message=f"Active quests: {len(quests_data)}",
                data={"quests": quests_data},
                narrative=None,
            )
        elif action == "quest_detail":
            quest_id = params.get("quest_id", "")
            if not quest_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'quest_id' parameter"
                )
            quest_service = get_quest_service(http_request)
            quest = quest_service.get_quest(quest_id)
            if quest is None:
                raise HTTPException(
                    status_code=404, detail=f"Quest not found: {quest_id}"
                )
            objectives = quest_service.get_quest_objectives(quest_id)
            objs_data = [
                {
                    "objective_id": o.objective_id,
                    "description": o.description,
                    "objective_type": o.objective_type,
                    "status": o.status,
                    "is_replacement": o.is_replacement,
                }
                for o in objectives
            ]
            return ActionResponse(
                success=True,
                action=action,
                message=quest.title,
                data={
                    "quest_id": quest.quest_id,
                    "title": quest.title,
                    "description": quest.description,
                    "quest_type": quest.quest_type,
                    "status": quest.status,
                    "seed_tier": quest.seed_tier,
                    "urgency": quest.urgency,
                    "objectives": objs_data,
                },
                narrative=None,
            )
        elif action == "quest_abandon":
            quest_id = params.get("quest_id", "")
            if not quest_id:
                raise HTTPException(
                    status_code=400, detail="Missing 'quest_id' parameter"
                )
            quest_service = get_quest_service(http_request)
            quest = quest_service.get_quest(quest_id)
            if quest is None:
                raise HTTPException(
                    status_code=404, detail=f"Quest not found: {quest_id}"
                )
            if quest.status != "active":
                raise HTTPException(
                    status_code=400,
                    detail=f"Quest is not active (status: {quest.status})",
                )
            quest_service.abandon_quest(quest_id, current_turn=0)
            return ActionResponse(
                success=True,
                action=action,
                message=f"Quest abandoned: {quest.title}",
                data={"quest_id": quest_id},
                narrative=None,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. "
                "Valid actions: look, move, rest, investigate, harvest, "
                "enter, exit, talk, say, end_talk, "
                "inventory, pickup, drop, use, browse, "
                "quest_list, quest_detail, quest_abandon",
            )

        # 응답 생성
        location = None
        if result.location_view:
            location = _build_location_info(result.location_view)

        logger.debug("Action executed: %s for %s", action, request.player_id)

        return ActionResponse(
            success=result.success,
            action=action,
            message=result.message,
            data=result.data,
            location=location,
            narrative=narrative,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Action failed: %s - %s", action, e)
        raise HTTPException(status_code=500, detail=str(e))
