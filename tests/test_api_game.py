"""Tests for game API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.game import get_engine
from src.core.engine import ITWEngine
from src.main import app
from src.services.ai.mock import MockProvider
from src.services.narrative_service import NarrativeService


@pytest.fixture()
def engine() -> ITWEngine:
    """Create a fresh ITWEngine instance for testing."""
    return ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )


@pytest.fixture()
def client(engine: ITWEngine) -> TestClient:
    """Create a TestClient with engine dependency override."""
    app.dependency_overrides[get_engine] = lambda: engine
    # NarrativeService 설정
    app.state.narrative_service = NarrativeService(MockProvider())
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRegisterPlayer:
    """Tests for POST /game/register endpoint."""

    def test_register_player(self, client: TestClient):
        """Test successful player registration."""
        response = client.post(
            "/game/register",
            json={"player_id": "test_player"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["player"]["player_id"] == "test_player"
        assert data["player"]["x"] == 0
        assert data["player"]["y"] == 0
        assert data["player"]["supply"] == 20
        assert data["player"]["fame"] == 0
        assert data["location"] is not None
        assert data["location"]["location_id"] is not None
        assert len(data["directions"]) == 4

    def test_register_duplicate(self, client: TestClient):
        """Test duplicate player registration returns existing player."""
        # First registration
        response1 = client.post(
            "/game/register",
            json={"player_id": "duplicate_player"},
        )
        assert response1.status_code == 200

        # Second registration - should return same player
        response2 = client.post(
            "/game/register",
            json={"player_id": "duplicate_player"},
        )
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["player"]["player_id"] == data2["player"]["player_id"]
        assert data1["player"]["x"] == data2["player"]["x"]
        assert data1["player"]["y"] == data2["player"]["y"]


class TestGetState:
    """Tests for GET /game/state/{player_id} endpoint."""

    def test_get_state(self, client: TestClient):
        """Test getting game state for registered player."""
        # Register player first
        client.post("/game/register", json={"player_id": "state_player"})

        # Get state
        response = client.get("/game/state/state_player")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["player"]["player_id"] == "state_player"
        assert data["location"] is not None
        assert "visual" in data["location"]
        assert "atmosphere" in data["location"]

    def test_get_state_not_found(self, client: TestClient):
        """Test 404 for non-existent player."""
        response = client.get("/game/state/nonexistent_player")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestActionEndpoint:
    """Tests for POST /game/action endpoint."""

    @pytest.fixture(autouse=True)
    def setup_player(self, client: TestClient):
        """Register a player before each test."""
        client.post("/game/register", json={"player_id": "action_player"})

    def test_action_look(self, client: TestClient):
        """Test look action."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "look",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["action"] == "look"
        assert data["location"] is not None

    def test_action_move(self, client: TestClient):
        """Test successful move action."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "move",
                "params": {"direction": "n"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["action"] == "move"
        assert "이동" in data["message"]
        assert data["location"] is not None

    def test_action_move_invalid_direction(self, client: TestClient):
        """Test move with invalid direction."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "move",
                "params": {"direction": "invalid"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Engine returns success=False for invalid direction
        assert data["success"] is False
        assert data["action"] == "move"

    def test_action_move_missing_direction(self, client: TestClient):
        """Test move without direction parameter."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "move",
                "params": {},
            },
        )

        assert response.status_code == 400
        assert "direction" in response.json()["detail"].lower()

    def test_action_rest(self, client: TestClient):
        """Test rest action."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "rest",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["action"] == "rest"
        assert "회복" in data["message"] or "휴식" in data["message"]

    def test_action_unknown(self, client: TestClient):
        """Test unknown action returns 400."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "invalid_action",
            },
        )

        assert response.status_code == 400
        assert "unknown action" in response.json()["detail"].lower()

    def test_action_player_not_found(self, client: TestClient):
        """Test action for non-existent player returns 404."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "nonexistent_player",
                "action": "look",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_action_investigate(self, client: TestClient):
        """Test investigate action."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "investigate",
                "params": {"echo_index": 0},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["action"] == "investigate"
        # May succeed or fail depending on echoes present

    def test_action_harvest_missing_resource(self, client: TestClient):
        """Test harvest without resource_id parameter."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "harvest",
                "params": {},
            },
        )

        assert response.status_code == 400
        assert "resource_id" in response.json()["detail"].lower()

    def test_look_returns_narrative(self, client: TestClient):
        """Test look action returns narrative field."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "look",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "narrative" in data
        assert data["narrative"] is not None
        assert isinstance(data["narrative"], str)
        assert len(data["narrative"]) > 0

    def test_move_returns_narrative(self, client: TestClient):
        """Test move action returns narrative field on success."""
        response = client.post(
            "/game/action",
            json={
                "player_id": "action_player",
                "action": "move",
                "params": {"direction": "n"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "narrative" in data
        assert data["narrative"] is not None
        assert isinstance(data["narrative"], str)
        assert len(data["narrative"]) > 0
