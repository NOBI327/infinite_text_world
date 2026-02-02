"""API request/response schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


# === Request Schemas ===


class RegisterRequest(BaseModel):
    """플레이어 등록 요청"""

    player_id: str = Field(..., min_length=1, max_length=50, description="플레이어 ID")


class ActionRequest(BaseModel):
    """게임 액션 요청"""

    player_id: str = Field(..., description="플레이어 ID")
    action: str = Field(
        ..., description="액션 타입: look, move, rest, investigate, harvest"
    )
    params: dict[str, Any] = Field(default_factory=dict, description="액션 파라미터")


# === Response Schemas ===


class LocationInfo(BaseModel):
    """위치 정보"""

    location_id: str
    visual: str
    atmosphere: str
    sound: str
    smell: str
    special_features: list[str] = []
    resources: list[dict[str, Any]] = []
    echoes: list[dict[str, Any]] = []


class DirectionInfo(BaseModel):
    """방향 힌트 정보"""

    direction: str
    visual_hint: str
    atmosphere_hint: str
    danger_level: str
    discovered: bool


class PlayerInfo(BaseModel):
    """플레이어 정보"""

    player_id: str
    x: int
    y: int
    supply: int
    fame: int
    inventory: dict[str, int] = {}
    discovered_count: int = 0


class GameStateResponse(BaseModel):
    """게임 상태 응답"""

    success: bool
    player: PlayerInfo
    location: Optional[LocationInfo] = None
    directions: list[DirectionInfo] = []


class ActionResponse(BaseModel):
    """액션 실행 응답"""

    success: bool
    action: str
    message: str
    data: Optional[dict[str, Any]] = None
    location: Optional[LocationInfo] = None
    narrative: Optional[str] = None


class ErrorResponse(BaseModel):
    """에러 응답"""

    success: bool = False
    error: str
    detail: Optional[str] = None
