"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.database import get_db
from src.main import app

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient wired to an in-memory SQLite database."""
    return TestClient(app)


@pytest.fixture()
def db_session() -> Session:
    """Raw database session for direct DB assertions."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
