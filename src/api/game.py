"""Game API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

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

logger = get_logger(__name__)

router = APIRouter(prefix="/game", tags=["game"])


def get_engine() -> ITWEngine:
    """엔진 인스턴스 반환 (의존성 주입)"""
    from src.main import get_game_engine

    return get_game_engine()


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
    engine: ITWEngine = Depends(get_engine),
) -> ActionResponse:
    """
    게임 액션 실행

    지원 액션:
    - look: 현재 위치 관찰
    - move: 이동 (params: {direction: "n"|"s"|"e"|"w"})
    - rest: 휴식
    - investigate: Echo 조사 (params: {echo_index: 0})
    - harvest: 자원 채취 (params: {resource_id: "...", amount: 1})
    """
    player = engine.get_player(request.player_id)

    if not player:
        raise HTTPException(
            status_code=404, detail=f"Player not found: {request.player_id}"
        )

    action = request.action.lower()
    params = request.params

    try:
        # 액션 실행
        if action == "look":
            result = engine.look(request.player_id)
        elif action == "move":
            direction = params.get("direction", "")
            if not direction:
                raise HTTPException(
                    status_code=400, detail="Missing 'direction' parameter"
                )
            result = engine.move(request.player_id, direction)
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
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. "
                "Valid actions: look, move, rest, investigate, harvest",
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
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Action failed: %s - %s", action, e)
        raise HTTPException(status_code=500, detail=str(e))
