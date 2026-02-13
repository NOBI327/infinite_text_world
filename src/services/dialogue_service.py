"""대화 세션 관리 Service — Core↔DB 연결, EventBus 통신

dialogue-system.md 섹션 3(생명주기), 섹션 8(EventBus) 대응.
architecture.md: Service → Core, Service → DB 허용. Service → Service 금지(EventBus 경유).
NarrativeService는 공유 인프라(LLM 관문)이므로 DI 허용.
"""

import json
import logging
import uuid

from sqlalchemy.orm import Session

from src.core.dialogue.budget import (
    calculate_budget,
    get_budget_phase,
    get_phase_instruction,
)
from src.core.dialogue.constraints import validate_action_interpretation
from src.core.dialogue.hexaco_descriptors import hexaco_to_natural_language
from src.core.dialogue.models import (
    DialogueSession,
    DialogueTurn,
)
from src.core.dialogue.validation import validate_meta
from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.db.models_v2 import DialogueSessionModel, DialogueTurnModel
from src.services.narrative_service import NarrativeService
from src.services.narrative_types import DialoguePromptContext

logger = logging.getLogger(__name__)

# PC 종료 의사 키워드
PC_END_KEYWORDS = frozenset(
    [
        "bye",
        "goodbye",
        "farewell",
        "じゃあ",
        "さよなら",
        "じゃあね",
        "また",
        "またね",
        "バイバイ",
    ]
)


class DialogueService:
    """대화 세션 관리"""

    def __init__(
        self,
        db: Session,
        event_bus: EventBus,
        narrative_service: NarrativeService,
    ):
        self._db = db
        self._bus = event_bus
        self._narrative = narrative_service
        self._active_session: DialogueSession | None = None
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독 등록"""
        self._bus.subscribe(EventTypes.ATTITUDE_RESPONSE, self._on_attitude_response)
        self._bus.subscribe(
            EventTypes.QUEST_SEED_GENERATED, self._on_quest_seed_generated
        )

    # === 공개 API ===

    def start_session(
        self,
        player_id: str,
        npc_id: str,
        node_id: str,
        game_turn: int,
        npc_data: dict,
        relationship_data: dict,
        npc_memories: list[str],
        pc_constraints: dict,
    ) -> DialogueSession:
        """대화 세션 시작.

        1. 예산 계산
        2. dialogue_started 발행 → quest 시드 판정, attitude 수신
        3. DialogueSession 생성
        4. DB에 세션 레코드 생성
        """
        # 예산 계산
        rel_status = relationship_data.get("status", "stranger")
        hexaco = npc_data.get("hexaco", {})
        hexaco_x = hexaco.get("X", 0.5)
        budget = calculate_budget(rel_status, hexaco_x, False)

        # dialogue_started 이벤트 발행 (시드/태도 수신)
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_STARTED,
                data={
                    "player_id": player_id,
                    "npc_id": npc_id,
                    "node_id": node_id,
                    "game_turn": game_turn,
                },
                source="dialogue_service",
            )
        )

        # HEXACO 자연어 변환
        hexaco_summary = hexaco_to_natural_language(hexaco) if hexaco else ""

        # 세션 생성
        session_id = str(uuid.uuid4())
        session = DialogueSession(
            session_id=session_id,
            player_id=player_id,
            npc_id=npc_id,
            node_id=node_id,
            budget_total=budget,
            budget_remaining=budget,
            budget_phase=get_budget_phase(budget, budget),
            started_turn=game_turn,
            npc_context={
                "npc_name": npc_data.get("name", "NPC"),
                "npc_race": npc_data.get("race", "human"),
                "npc_role": npc_data.get("role", ""),
                "hexaco_summary": hexaco_summary,
                "manner_tags": npc_data.get("manner_tags", []),
                "attitude_tags": [],
                "relationship_status": rel_status,
                "familiarity": relationship_data.get("familiarity", 0),
                "npc_memories": npc_memories,
                "npc_opinions": npc_data.get("npc_opinions", {}),
                "node_environment": npc_data.get("node_environment", ""),
            },
            session_context={
                "constraints": pc_constraints,
            },
        )

        # 시드 보정 (이벤트에서 시드가 주입되었으면 예산 재계산)
        if session.quest_seed is not None:
            new_budget = calculate_budget(rel_status, hexaco_x, True)
            session.budget_total = new_budget
            session.budget_remaining = new_budget
            session.budget_phase = get_budget_phase(new_budget, new_budget)

        self._active_session = session

        # DB 저장
        self._save_session_to_db(session)

        logger.info(
            "Dialogue session started: %s (npc=%s, budget=%d)",
            session_id,
            npc_id,
            session.budget_total,
        )
        return session

    def process_turn(self, pc_input: str) -> dict:
        """대화 턴 1회 처리.

        Returns:
            {"narrative": str, "session_status": str, "turn_index": int}
        """
        session = self._active_session
        if session is None:
            raise RuntimeError("No active dialogue session")

        if session.status != "active":
            raise RuntimeError(f"Session is not active: {session.status}")

        # budget_phase 갱신
        session.budget_phase = get_budget_phase(
            session.budget_remaining, session.budget_total
        )

        # PC 종료 의사 감지
        if self._check_pc_end_intent(pc_input):
            result = self.end_session("ended_by_pc")
            return {
                "narrative": "（会話が終了した）",
                "session_status": "ended_by_pc",
                "turn_index": session.dialogue_turn_count,
                "end_result": result,
            }

        # DialoguePromptContext 조립
        ctx = self._build_prompt_context(pc_input)

        # NarrativeService 호출
        narr_result = self._narrative.generate_dialogue_response(ctx)

        # META 검증
        validated_meta = validate_meta(narr_result.raw_meta)

        # Constraints 검증 (action_interpretation)
        constraints = session.session_context.get("constraints", {})
        if validated_meta.get("action_interpretation") is not None:
            validated_meta["action_interpretation"] = validate_action_interpretation(
                validated_meta["action_interpretation"],
                pc_axioms=constraints.get("axioms", []),
                pc_items=constraints.get("items", []),
                pc_stats=constraints.get("stats", {}),
            )

        # 누적 delta 갱신
        rel_delta = validated_meta.get("relationship_delta", {})
        session.accumulated_affinity_delta += rel_delta.get("affinity", 0)

        # memory_tags 누적
        new_tags = validated_meta.get("memory_tags", [])
        session.accumulated_memory_tags.extend(new_tags)

        # seed_response 추적
        seed_resp = validated_meta.get("quest_seed_response")
        if seed_resp in ("accepted", "ignored"):
            session.seed_result = seed_resp
            session.seed_delivered = True

        # DialogueTurn 생성
        turn = DialogueTurn(
            turn_index=session.dialogue_turn_count,
            pc_input=pc_input,
            npc_narrative=narr_result.narrative,
            raw_meta=narr_result.raw_meta,
            validated_meta=validated_meta,
        )
        session.history.append(turn)
        session.dialogue_turn_count += 1

        # budget 차감
        session.budget_remaining -= 1
        session.budget_phase = get_budget_phase(
            session.budget_remaining, session.budget_total
        )

        # DB 턴 저장
        self._save_turn_to_db(turn, session.session_id)

        # 종료 판정
        end_reason = self._evaluate_end_condition(validated_meta, session)
        if end_reason is not None:
            result = self.end_session(end_reason)
            return {
                "narrative": narr_result.narrative,
                "session_status": end_reason,
                "turn_index": turn.turn_index,
                "end_result": result,
            }

        return {
            "narrative": narr_result.narrative,
            "session_status": "active",
            "turn_index": turn.turn_index,
        }

    def end_session(self, reason: str = "ended_by_pc") -> dict:
        """세션 종료 + 일괄 처리.

        Returns:
            {"session_id": str, "total_turns": int, "affinity_delta": float, ...}
        """
        session = self._active_session
        if session is None:
            raise RuntimeError("No active dialogue session to end")

        session.status = reason

        # dialogue_ended 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.DIALOGUE_ENDED,
                data={
                    "session_id": session.session_id,
                    "player_id": session.player_id,
                    "npc_id": session.npc_id,
                    "reason": reason,
                    "total_turns": session.dialogue_turn_count,
                    "accumulated_affinity_delta": session.accumulated_affinity_delta,
                    "accumulated_trust_delta": session.accumulated_trust_delta,
                    "accumulated_memory_tags": session.accumulated_memory_tags,
                    "seed_result": session.seed_result,
                },
                source="dialogue_service",
            )
        )

        # DB 갱신
        self._update_session_in_db(session)

        result = {
            "session_id": session.session_id,
            "total_turns": session.dialogue_turn_count,
            "affinity_delta": session.accumulated_affinity_delta,
            "trust_delta": session.accumulated_trust_delta,
            "memory_tags": session.accumulated_memory_tags,
            "seed_result": session.seed_result,
            "reason": reason,
        }

        logger.info(
            "Dialogue session ended: %s (reason=%s, turns=%d, affinity=%.1f)",
            session.session_id,
            reason,
            session.dialogue_turn_count,
            session.accumulated_affinity_delta,
        )

        # active_session 해제
        self._active_session = None

        return result

    def get_active_session(self) -> DialogueSession | None:
        """현재 활성 세션 반환"""
        return self._active_session

    # === EventBus 핸들러 ===

    def _on_attitude_response(self, event: GameEvent) -> None:
        """태도 태그 수신 → 활성 세션의 npc_context에 반영"""
        if self._active_session is None:
            return

        tags = event.data.get("attitude_tags", [])
        if tags:
            self._active_session.npc_context["attitude_tags"] = tags
            logger.info("Attitude tags received: %s", tags)

    def _on_quest_seed_generated(self, event: GameEvent) -> None:
        """퀘스트 시드 수신 → 활성 세션에 시드 주입"""
        if self._active_session is None:
            return

        seed = event.data.get("seed")
        if seed:
            self._active_session.quest_seed = seed
            self._active_session.session_context["quest_seed"] = seed
            logger.info("Quest seed injected: %s", seed.get("seed_id", "unknown"))

    # === 내부 ===

    def _build_prompt_context(self, pc_input: str) -> DialoguePromptContext:
        """활성 세션 데이터 → DialoguePromptContext 조립"""
        session = self._active_session
        assert session is not None

        npc_ctx = session.npc_context
        sess_ctx = session.session_context

        # 대화 이력 (narrative만, meta 제외)
        history = []
        for turn in session.history:
            history.append({"role": "pc", "text": turn.pc_input})
            history.append({"role": "npc", "text": turn.npc_narrative})

        phase_instruction = get_phase_instruction(
            session.budget_phase,
            session.seed_delivered,
            session.quest_seed is not None,
        )

        return DialoguePromptContext(
            npc_name=npc_ctx.get("npc_name", "NPC"),
            npc_race=npc_ctx.get("npc_race", "human"),
            npc_role=npc_ctx.get("npc_role", ""),
            hexaco_summary=npc_ctx.get("hexaco_summary", ""),
            manner_tags=npc_ctx.get("manner_tags", []),
            attitude_tags=npc_ctx.get("attitude_tags", []),
            relationship_status=npc_ctx.get("relationship_status", "stranger"),
            familiarity=npc_ctx.get("familiarity", 0),
            npc_memories=npc_ctx.get("npc_memories", []),
            npc_opinions=npc_ctx.get("npc_opinions", {}),
            node_environment=npc_ctx.get("node_environment", ""),
            constraints=sess_ctx.get("constraints", {}),
            quest_seed=sess_ctx.get("quest_seed"),
            budget_phase=session.budget_phase,
            budget_remaining=session.budget_remaining,
            budget_total=session.budget_total,
            seed_delivered=session.seed_delivered,
            phase_instruction=phase_instruction,
            accumulated_delta=session.accumulated_affinity_delta,
            history=history,
            pc_input=pc_input,
        )

    def _check_pc_end_intent(self, pc_input: str) -> bool:
        """PC 종료 의사 간단 감지 (키워드 기반)"""
        normalized = pc_input.strip().lower()
        return normalized in PC_END_KEYWORDS

    def _check_npc_end_intent(self, validated_meta: dict) -> bool:
        """META의 end_conversation, wants_to_continue 확인"""
        ds = validated_meta.get("dialogue_state", {})
        if ds.get("end_conversation") is True:
            return True
        if ds.get("wants_to_continue") is False:
            return True
        return False

    def _evaluate_end_condition(
        self, validated_meta: dict, session: DialogueSession
    ) -> str | None:
        """종료 조건 평가. 종료 시 이유 문자열, 미종료 시 None."""
        # NPC 종료 의사
        if self._check_npc_end_intent(validated_meta):
            return "ended_by_npc"

        # 예산 소진
        if session.budget_remaining <= 0:
            return "ended_by_budget"

        return None

    # === ORM ↔ Core 변환 ===

    def _save_session_to_db(self, session: DialogueSession) -> None:
        """Core → DB 세션 저장"""
        model = DialogueSessionModel(
            session_id=session.session_id,
            player_id=session.player_id,
            npc_id=session.npc_id,
            node_id=session.node_id,
            budget_total=session.budget_total,
            status=session.status,
            started_turn=session.started_turn,
            dialogue_turn_count=session.dialogue_turn_count,
        )
        self._db.add(model)
        self._db.flush()

    def _update_session_in_db(self, session: DialogueSession) -> None:
        """DB 세션 레코드 갱신"""
        row = (
            self._db.query(DialogueSessionModel)
            .filter(DialogueSessionModel.session_id == session.session_id)
            .first()
        )
        if row is None:
            logger.warning("Session not found in DB: %s", session.session_id)
            return

        row.status = session.status
        row.dialogue_turn_count = session.dialogue_turn_count
        row.total_affinity_delta = session.accumulated_affinity_delta
        row.seed_result = session.seed_result
        self._db.flush()

    def _save_turn_to_db(self, turn: DialogueTurn, session_id: str) -> None:
        """Core → DB 턴 저장"""
        model = DialogueTurnModel(
            turn_id=str(uuid.uuid4()),
            session_id=session_id,
            turn_index=turn.turn_index,
            pc_input=turn.pc_input,
            npc_narrative=turn.npc_narrative,
            raw_meta=json.dumps(turn.raw_meta, ensure_ascii=False),
            validated_meta=json.dumps(turn.validated_meta, ensure_ascii=False),
        )
        self._db.add(model)
        self._db.flush()
