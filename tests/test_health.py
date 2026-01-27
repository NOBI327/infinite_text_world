"""Tests for the /health endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """GET /health should return 200 with status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_db_status(client: TestClient) -> None:
    """GET /health response must contain a 'database' field."""
    response = client.get("/health")
    data = response.json()
    assert "database" in data
