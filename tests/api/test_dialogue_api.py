"""대화 API 통합 테스트

#10-E 검증: 최소 6개 API 테스트 케이스.
TestClient + in-memory SQLite + MockProvider.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.game import router as game_router
from src.core.engine import ITWEngine
from src.core.event_bus import EventBus
from src.db.models import Base
from src.db.models_v2 import DialogueSessionModel, DialogueTurnModel  # noqa: F401
from src.services.ai import MockProvider
from src.services.dialogue_service import DialogueService
from src.services.narrative_service import NarrativeService


@pytest.fixture()
def client():
    """TestClient + 인메모리 환경 세팅"""
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa_event.listens_for(db_engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(db_engine)
    session_factory = sessionmaker(bind=db_engine)
    db = session_factory()

    bus = EventBus()
    provider = MockProvider()
    narrative_service = NarrativeService(provider)
    dialogue_service = DialogueService(db, bus, narrative_service)

    # 테스트용 엔진
    engine = ITWEngine(
        axiom_data_path="src/data/itw_214_divine_axioms.json",
        world_seed=42,
    )

    app = FastAPI()
    app.include_router(game_router)
    app.state.narrative_service = narrative_service
    app.state.dialogue_service = dialogue_service

    # get_engine 의존성을 오버라이드
    import src.main

    original_engine = src.main.game_engine
    src.main.game_engine = engine

    # 플레이어 등록
    engine.register_player("test_player")

    with TestClient(app) as tc:
        yield tc

    src.main.game_engine = original_engine
    db.close()


def _talk_action(npc_id: str = "npc_001") -> dict:
    return {
        "player_id": "test_player",
        "action": "talk",
        "params": {"npc_id": npc_id},
    }


def _say_action(text: str) -> dict:
    return {
        "player_id": "test_player",
        "action": "say",
        "params": {"text": text},
    }


def _end_talk_action() -> dict:
    return {
        "player_id": "test_player",
        "action": "end_talk",
        "params": {},
    }


# ── talk 액션 ──────────────────────────────────────────────


class TestTalkAction:
    def test_start_dialogue(self, client):
        """talk → 대화 세션 시작"""
        resp = client.post("/game/action", json=_talk_action())

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "talk"
        assert "session_id" in data["data"]
        assert data["data"]["budget_total"] > 0

    def test_talk_missing_npc_id(self, client):
        """talk → npc_id 누락 → 400"""
        resp = client.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "talk",
                "params": {},
            },
        )

        assert resp.status_code == 400


# ── say 액션 ──────────────────────────────────────────────


class TestSayAction:
    def test_dialogue_turn(self, client):
        """say → 대화 턴 처리"""
        # 세션 시작
        client.post("/game/action", json=_talk_action())

        # 발언
        resp = client.post("/game/action", json=_say_action("こんにちは"))

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "say"
        assert data["narrative"] is not None
        assert data["data"]["turn_index"] == 0

    def test_say_without_session(self, client):
        """say → 활성 세션 없을 때 → 500"""
        resp = client.post("/game/action", json=_say_action("hello"))

        assert resp.status_code == 500

    def test_say_missing_text(self, client):
        """say → text 누락 → 400"""
        client.post("/game/action", json=_talk_action())

        resp = client.post(
            "/game/action",
            json={
                "player_id": "test_player",
                "action": "say",
                "params": {},
            },
        )

        assert resp.status_code == 400


# ── end_talk 액션 ──────────────────────────────────────────


class TestEndTalkAction:
    def test_end_dialogue(self, client):
        """end_talk → 세션 종료"""
        client.post("/game/action", json=_talk_action())

        resp = client.post("/game/action", json=_end_talk_action())

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "end_talk"
        assert data["data"]["reason"] == "ended_by_pc"


# ── 통합 시나리오 ──────────────────────────────────────────


class TestFullDialogueScenario:
    def test_full_conversation(self, client):
        """start → say × N → end_talk 통합 테스트"""
        # 대화 시작
        resp = client.post("/game/action", json=_talk_action())
        assert resp.json()["success"] is True

        # 대화 턴 (budget=3이므로 최대 3턴)
        session_ended = False
        for i in range(3):
            resp = client.post("/game/action", json=_say_action(f"turn_{i}"))
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["turn_index"] == i
            if data["data"]["session_status"] != "active":
                session_ended = True
                break

        # 세션이 아직 활성이면 수동 종료
        if not session_ended:
            resp = client.post("/game/action", json=_end_talk_action())
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["reason"] == "ended_by_pc"
