"""DialogueModule 단위 테스트

#10-E 검증: 최소 4개 테스트 케이스.
"""

import pytest
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker

from src.core.event_bus import EventBus
from src.db.models import Base
from src.modules.base import GameContext
from src.modules.dialogue.module import DialogueModule
from src.services.ai import MockProvider
from src.services.dialogue_service import DialogueService
from src.services.narrative_service import NarrativeService


@pytest.fixture()
def module_setup():
    """DialogueModule + 인메모리 DB 세팅"""
    engine = create_engine("sqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    bus = EventBus()

    provider = MockProvider()
    narrative = NarrativeService(provider)
    service = DialogueService(db, bus, narrative)
    module = DialogueModule(service)
    return module, service, db, bus


def _make_context(player_id: str = "p1") -> GameContext:
    return GameContext(
        player_id=player_id,
        current_node_id="node_001",
        current_turn=1,
    )


# ── 기본 속성 ──────────────────────────────────────────────


class TestDialogueModuleBasic:
    def test_name_and_dependencies(self, module_setup):
        """모듈 이름과 의존성 확인"""
        module, *_ = module_setup
        assert module.name == "dialogue"
        assert module.dependencies == ["npc_core", "relationship"]

    def test_initial_state(self, module_setup):
        """초기 상태: 비활성"""
        module, *_ = module_setup
        assert module.enabled is False


# ── get_available_actions ──────────────────────────────────


class TestGetAvailableActions:
    def test_no_session_returns_talk(self, module_setup):
        """세션 없을 때 talk 액션 반환"""
        module, *_ = module_setup
        ctx = _make_context()

        actions = module.get_available_actions(ctx)

        assert len(actions) == 1
        assert actions[0].name == "talk"
        assert actions[0].module_name == "dialogue"

    def test_active_session_returns_say_and_end_talk(self, module_setup):
        """세션 있을 때 say + end_talk 액션 반환"""
        module, service, *_ = module_setup

        # 세션 시작
        service.start_session(
            player_id="p1",
            npc_id="npc_001",
            node_id="node_001",
            game_turn=1,
            npc_data={"name": "Hans", "race": "human", "role": "blacksmith"},
            relationship_data={"status": "stranger", "familiarity": 0},
            npc_memories=[],
            pc_constraints={},
        )

        ctx = _make_context()
        actions = module.get_available_actions(ctx)

        names = [a.name for a in actions]
        assert "say" in names
        assert "end_talk" in names
        assert "talk" not in names


# ── on_node_enter ──────────────────────────────────────────


class TestOnNodeEnter:
    def test_sets_dialogue_extra(self, module_setup):
        """on_node_enter에서 context.extra['dialogue'] 설정"""
        module, *_ = module_setup
        ctx = _make_context()

        module.on_node_enter("node_001", ctx)

        assert "dialogue" in ctx.extra
        assert ctx.extra["dialogue"]["active_session"] is False

    def test_active_session_flag(self, module_setup):
        """활성 세션 있을 때 active_session=True"""
        module, service, *_ = module_setup

        service.start_session(
            player_id="p1",
            npc_id="npc_001",
            node_id="node_001",
            game_turn=1,
            npc_data={"name": "Hans", "race": "human"},
            relationship_data={"status": "stranger", "familiarity": 0},
            npc_memories=[],
            pc_constraints={},
        )

        ctx = _make_context()
        module.on_node_enter("node_001", ctx)

        assert ctx.extra["dialogue"]["active_session"] is True


# ── service 접근 ──────────────────────────────────────────


class TestServiceAccess:
    def test_service_property(self, module_setup):
        """service 프로퍼티로 DialogueService 접근"""
        module, service, *_ = module_setup
        assert module.service is service
