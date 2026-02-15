"""퀘스트 Service — Core↔DB 연결, EventBus 통신

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""

import json
import logging
import uuid

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.quest.chain_logic import (
    build_chain_eligible_npcs,
    match_unborn_npc,
)
from src.core.quest.context_builder import (
    TIER_INSTRUCTIONS,
    build_activation_context,
    build_expired_seed_context,
    build_seed_context,
)
from src.core.quest.models import (
    ChainEligibleNPC,
    Objective,
    Quest,
    QuestRewards,
    QuestSeed,
    RelationshipDelta,
    WorldChange,
)
from src.core.quest.objective_logic import (
    generate_replacement_objectives,
    validate_objectives_hint,
)
from src.core.quest.probability import should_finalize_chain
from src.core.quest.result_logic import (
    calculate_pc_tendency,
    calculate_rewards,
    evaluate_quest_result,
)
from src.core.quest.seed_logic import process_seed_ttl, try_generate_seed
from src.db.models_v2 import (
    QuestChainEligibleModel,
    QuestChainModel,
    QuestModel,
    QuestObjectiveModel,
    QuestSeedModel,
)

logger = logging.getLogger(__name__)


class QuestService:
    """퀘스트 CRUD + 비즈니스 로직"""

    def __init__(self, db: Session, event_bus: EventBus):
        self._db = db
        self._bus = event_bus
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독"""
        self._bus.subscribe(EventTypes.DIALOGUE_STARTED, self._on_dialogue_started)
        self._bus.subscribe(EventTypes.DIALOGUE_ENDED, self._on_dialogue_ended)
        self._bus.subscribe(EventTypes.TURN_PROCESSED, self._on_turn_processed)
        self._bus.subscribe(EventTypes.NPC_PROMOTED, self._on_npc_promoted)
        self._bus.subscribe(
            EventTypes.OBJECTIVE_COMPLETED, self._on_objective_completed
        )
        self._bus.subscribe(EventTypes.OBJECTIVE_FAILED, self._on_objective_failed)

    # === Seed 관리 ===

    def create_seed(
        self,
        npc_id: str,
        current_turn: int,
        conversation_count: int,
        eligible_quests: list[Quest] | None = None,
    ) -> QuestSeed | None:
        """시드 생성 시도. Core 로직 위임 + DB 저장 + 이벤트 발행."""
        # 마지막 시드의 conversation_count 조회
        last_seed = (
            self._db.query(QuestSeedModel)
            .filter(QuestSeedModel.npc_id == npc_id)
            .order_by(QuestSeedModel.created_turn.desc())
            .first()
        )
        last_count = (
            last_seed.conversation_count_at_creation if last_seed is not None else None
        )

        seed = try_generate_seed(
            npc_id=npc_id,
            current_turn=current_turn,
            last_seed_conversation_count=last_count,
            current_conversation_count=conversation_count,
            eligible_quests=eligible_quests,
        )

        if seed is None:
            return None

        # DB 저장
        orm = self._seed_to_orm(seed)
        orm.conversation_count_at_creation = conversation_count
        self._db.add(orm)
        self._db.commit()

        # 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.QUEST_SEED_CREATED,
                data={"seed_id": seed.seed_id, "npc_id": npc_id},
                source="quest_service",
            )
        )

        return seed

    def get_seed(self, seed_id: str) -> QuestSeed | None:
        """시드 조회."""
        orm = self._db.get(QuestSeedModel, seed_id)
        if orm is None:
            return None
        return self._seed_to_core(orm)

    def get_active_seeds_for_npc(self, npc_id: str) -> list[QuestSeed]:
        """NPC의 활성 시드 목록."""
        orms = (
            self._db.query(QuestSeedModel)
            .filter(QuestSeedModel.npc_id == npc_id, QuestSeedModel.status == "active")
            .all()
        )
        return [self._seed_to_core(o) for o in orms]

    def process_all_seed_ttls(self, current_turn: int) -> list[QuestSeed]:
        """모든 활성 시드 TTL 체크. 만료된 시드 목록 반환."""
        orms = (
            self._db.query(QuestSeedModel)
            .filter(QuestSeedModel.status == "active")
            .all()
        )

        expired: list[QuestSeed] = []
        for orm in orms:
            seed = self._seed_to_core(orm)
            if process_seed_ttl(seed, current_turn):
                orm.status = "expired"
                expired.append(seed)
                self._bus.emit(
                    GameEvent(
                        event_type=EventTypes.QUEST_SEED_EXPIRED,
                        data={"seed_id": seed.seed_id, "npc_id": seed.npc_id},
                        source="quest_service",
                    )
                )

        if expired:
            self._db.commit()

        return expired

    # === Quest 관리 ===

    def activate_quest(
        self,
        seed: QuestSeed,
        quest_details: dict,
        current_turn: int,
    ) -> Quest:
        """시드 → 퀘스트 활성화."""
        quest_id = f"quest_{uuid.uuid4().hex[:12]}"

        # objectives_hint 검증
        hints = quest_details.get("objectives_hint", [])
        quest_type = quest_details.get("quest_type", seed.seed_type)
        objectives = validate_objectives_hint(hints, quest_type, quest_id)

        quest = Quest(
            quest_id=quest_id,
            title=quest_details.get("title", ""),
            description=quest_details.get("description", ""),
            origin_type="conversation",
            origin_npc_id=seed.npc_id,
            origin_seed_id=seed.seed_id,
            quest_type=quest_type,
            seed_tier=seed.seed_tier,
            urgency=quest_details.get("urgency", "normal"),
            time_limit=quest_details.get("time_limit"),
            activated_turn=current_turn,
            chain_id=seed.chain_id,
            related_npc_ids=quest_details.get("related_npc_ids", []),
            target_node_ids=quest_details.get("target_node_ids", []),
            tags=quest_details.get("tags", []),
        )

        # seed status → accepted
        seed_orm = self._db.get(QuestSeedModel, seed.seed_id)
        if seed_orm is not None:
            seed_orm.status = "accepted"

        # DB 저장 (quest + objectives)
        self._db.add(self._quest_to_orm(quest))
        for obj in objectives:
            self._db.add(self._objective_to_orm(obj))

        # chain 레코드
        if quest.chain_id:
            existing_chain = self._db.get(QuestChainModel, quest.chain_id)
            if existing_chain is None:
                self._db.add(
                    QuestChainModel(
                        chain_id=quest.chain_id,
                        created_turn=current_turn,
                        total_quests=1,
                    )
                )
            else:
                existing_chain.total_quests += 1

        self._db.commit()

        # 이벤트 발행
        self._bus.emit(
            GameEvent(
                event_type=EventTypes.QUEST_ACTIVATED,
                data={"quest_id": quest_id, "npc_id": seed.npc_id},
                source="quest_service",
            )
        )

        return quest

    def get_quest(self, quest_id: str) -> Quest | None:
        """퀘스트 조회."""
        orm = self._db.get(QuestModel, quest_id)
        if orm is None:
            return None
        return self._quest_to_core(orm)

    def get_active_quests(self, player_id: str | None = None) -> list[Quest]:
        """활성 퀘스트 목록."""
        orms = self._db.query(QuestModel).filter(QuestModel.status == "active").all()
        return [self._quest_to_core(o) for o in orms]

    def get_quest_objectives(self, quest_id: str) -> list[Objective]:
        """퀘스트의 목표 목록 (대체 목표 포함)."""
        orms = (
            self._db.query(QuestObjectiveModel)
            .filter(QuestObjectiveModel.quest_id == quest_id)
            .all()
        )
        return [self._objective_to_core(o) for o in orms]

    def get_active_objectives_by_type(self, objective_type: str) -> list[Objective]:
        """특정 유형의 활성 목표. ObjectiveWatcher가 사용."""
        orms = (
            self._db.query(QuestObjectiveModel)
            .filter(
                QuestObjectiveModel.objective_type == objective_type,
                QuestObjectiveModel.status == "active",
            )
            .all()
        )
        return [self._objective_to_core(o) for o in orms]

    def abandon_quest(self, quest_id: str, current_turn: int) -> bool:
        """퀘스트 포기."""
        orm = self._db.get(QuestModel, quest_id)
        if orm is None:
            return False
        if orm.status != "active":
            return False

        orm.status = "abandoned"
        orm.result = "abandoned"
        orm.completed_turn = current_turn
        self._db.commit()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.QUEST_ABANDONED,
                data={"quest_id": quest_id},
                source="quest_service",
            )
        )
        return True

    # === 결과 처리 ===

    def check_quest_completion(self, quest_id: str, current_turn: int) -> str | None:
        """퀘스트 완료 판정."""
        quest = self.get_quest(quest_id)
        if quest is None or quest.status != "active":
            return None

        objectives = self.get_quest_objectives(quest_id)
        result = evaluate_quest_result(quest, objectives, current_turn)

        if result is None:
            return None

        # 보상 계산 + DB 갱신
        rewards = calculate_rewards(quest, result)
        quest.status = "completed" if result != "failure" else "failed"
        quest.result = result
        quest.completed_turn = current_turn
        quest.rewards = rewards

        orm = self._db.get(QuestModel, quest_id)
        if orm is not None:
            orm.status = quest.status
            orm.result = result
            orm.completed_turn = current_turn
            orm.rewards_json = json.dumps(self._rewards_to_dict(rewards))
            self._db.commit()

        # 이벤트 발행
        event_type = (
            EventTypes.QUEST_COMPLETED
            if result != "failure"
            else EventTypes.QUEST_FAILED
        )
        self._bus.emit(
            GameEvent(
                event_type=event_type,
                data={
                    "quest_id": quest_id,
                    "result": result,
                    "rewards": self._rewards_to_dict(rewards),
                },
                source="quest_service",
            )
        )

        # 체이닝 처리
        if result in ("success", "partial"):
            self.finalize_quest_chain(quest, current_turn)

        return result

    def complete_objective(
        self, objective_id: str, current_turn: int, trigger_data: dict
    ) -> None:
        """목표 달성 처리."""
        orm = self._db.get(QuestObjectiveModel, objective_id)
        if orm is None:
            return

        orm.status = "completed"
        orm.completed_turn = current_turn
        self._db.commit()

        logger.info("Objective completed: %s", objective_id)

        # 퀘스트 완료 판정 자동 실행
        self.check_quest_completion(orm.quest_id, current_turn)

    def fail_objective(
        self,
        objective_id: str,
        current_turn: int,
        fail_reason: str,
        trigger_data: dict,
    ) -> list[Objective]:
        """목표 실패 처리. 대체 목표 생성."""
        orm = self._db.get(QuestObjectiveModel, objective_id)
        if orm is None:
            return []

        orm.status = "failed"
        orm.failed_turn = current_turn
        orm.fail_reason = fail_reason

        obj = self._objective_to_core(orm)
        quest = self.get_quest(orm.quest_id)
        if quest is None:
            self._db.commit()
            return []

        context = {
            "client_npc_id": quest.origin_npc_id or "",
        }
        replacements = generate_replacement_objectives(obj, quest, context)

        for repl in replacements:
            self._db.add(self._objective_to_orm(repl))

        self._db.commit()

        logger.info(
            "Objective %s failed (reason=%s), %d replacements generated",
            objective_id,
            fail_reason,
            len(replacements),
        )
        return replacements

    # === 체이닝 ===

    def find_quests_with_eligible_npc(self, npc_id: str) -> list[Quest]:
        """해당 NPC가 chain_eligible에 포함된 완료 퀘스트 검색."""
        eligible_orms = (
            self._db.query(QuestChainEligibleModel)
            .filter(
                QuestChainEligibleModel.npc_ref == npc_id,
                QuestChainEligibleModel.ref_type == "existing",
            )
            .all()
        )

        quest_ids = {e.quest_id for e in eligible_orms}
        result: list[Quest] = []
        for qid in quest_ids:
            quest = self.get_quest(qid)
            if quest is not None and quest.status in ("completed", "failed"):
                result.append(quest)

        return result

    def finalize_quest_chain(self, quest: Quest, current_turn: int) -> None:
        """퀘스트 완료 후 체이닝 처리."""
        eligible_npcs = build_chain_eligible_npcs(quest, quest.seed_tier)

        # DB에 eligible 저장
        for enpc in eligible_npcs:
            self._db.add(
                QuestChainEligibleModel(
                    quest_id=quest.quest_id,
                    npc_ref=enpc.npc_ref,
                    ref_type=enpc.ref_type,
                    node_hint=enpc.node_hint,
                    reason=enpc.reason,
                )
            )

        # 체인이 있으면 완결 판정
        if quest.chain_id:
            chain = self._db.get(QuestChainModel, quest.chain_id)
            if chain is not None:
                if should_finalize_chain(chain.total_quests):
                    chain.finalized = True
                    self._bus.emit(
                        GameEvent(
                            event_type=EventTypes.QUEST_CHAIN_FINALIZED,
                            data={
                                "chain_id": quest.chain_id,
                                "total_quests": chain.total_quests,
                            },
                            source="quest_service",
                        )
                    )
                else:
                    self._bus.emit(
                        GameEvent(
                            event_type=EventTypes.QUEST_CHAIN_FORMED,
                            data={
                                "chain_id": quest.chain_id,
                                "quest_id": quest.quest_id,
                            },
                            source="quest_service",
                        )
                    )

        self._db.commit()

    def scan_unborn_eligible(
        self, npc_id: str, npc_tags: list[str], npc_node: str
    ) -> None:
        """NPC 승격 시 unborn eligible 스캔."""
        orms = (
            self._db.query(QuestChainEligibleModel)
            .filter(QuestChainEligibleModel.ref_type == "unborn")
            .all()
        )

        for orm in orms:
            eligible = ChainEligibleNPC(
                npc_ref=orm.npc_ref,
                ref_type=orm.ref_type,
                node_hint=orm.node_hint,
                reason=orm.reason,
            )
            if match_unborn_npc(eligible, npc_tags, npc_node):
                orm.matched_npc_id = npc_id
                orm.matched_turn = 0  # will be set by caller
                self._bus.emit(
                    GameEvent(
                        event_type=EventTypes.CHAIN_ELIGIBLE_MATCHED,
                        data={
                            "npc_id": npc_id,
                            "quest_id": orm.quest_id,
                            "reason": orm.reason,
                        },
                        source="quest_service",
                    )
                )

        self._db.commit()

    # === LLM 컨텍스트 ===

    def build_dialogue_quest_context(
        self, npc_id: str, current_turn: int
    ) -> dict | None:
        """대화 시작 시 퀘스트 관련 LLM 컨텍스트."""
        # 활성 시드 확인
        active_seeds = self.get_active_seeds_for_npc(npc_id)
        if active_seeds:
            seed = active_seeds[0]
            instruction = TIER_INSTRUCTIONS.get(seed.seed_tier, TIER_INSTRUCTIONS[3])
            return build_seed_context(seed, instruction)

        # 만료 시드 확인
        expired_orms = (
            self._db.query(QuestSeedModel)
            .filter(
                QuestSeedModel.npc_id == npc_id,
                QuestSeedModel.status == "expired",
            )
            .order_by(QuestSeedModel.created_turn.desc())
            .first()
        )
        if expired_orms is not None:
            seed = self._seed_to_core(expired_orms)
            return build_expired_seed_context(seed)

        return None

    def build_quest_activation_context(
        self, seed: QuestSeed, npc_personality: dict, relationship_status: str
    ) -> dict:
        """퀘스트 활성화 시 LLM 컨텍스트."""
        return build_activation_context(seed, npc_personality, relationship_status)

    def get_pc_tendency(self) -> dict:
        """PC 경향 산출."""
        orms = (
            self._db.query(QuestModel)
            .filter(QuestModel.status.in_(["completed", "failed"]))
            .all()
        )
        quests = [self._quest_to_core(o) for o in orms]
        return calculate_pc_tendency(quests)

    # === 시간 제한 ===

    def check_urgent_time_limits(self, current_turn: int) -> list[Quest]:
        """urgent 퀘스트 시간 초과 체크."""
        orms = (
            self._db.query(QuestModel)
            .filter(
                QuestModel.status == "active",
                QuestModel.urgency == "urgent",
                QuestModel.time_limit.isnot(None),
            )
            .all()
        )

        timed_out: list[Quest] = []
        for orm in orms:
            quest = self._quest_to_core(orm)
            if (
                quest.time_limit is not None
                and current_turn > quest.activated_turn + quest.time_limit
            ):
                # 활성 목표 전체 fail
                obj_orms = (
                    self._db.query(QuestObjectiveModel)
                    .filter(
                        QuestObjectiveModel.quest_id == quest.quest_id,
                        QuestObjectiveModel.status == "active",
                    )
                    .all()
                )
                for obj_orm in obj_orms:
                    obj_orm.status = "failed"
                    obj_orm.failed_turn = current_turn
                    obj_orm.fail_reason = "time_expired"

                self._db.commit()

                # 퀘스트 완료 판정
                self.check_quest_completion(quest.quest_id, current_turn)
                timed_out.append(quest)

        return timed_out

    # === EventBus 핸들러 ===

    def _on_dialogue_started(self, event: GameEvent) -> None:
        """대화 시작 시 시드 발생 판정 (5%)."""
        npc_id = event.data.get("npc_id", "")
        if not npc_id:
            return

        current_turn = event.data.get("turn", 0)
        conversation_count = event.data.get("conversation_count", 0)

        # 시드 생성 시도
        eligible = self.find_quests_with_eligible_npc(npc_id)
        seed = self.create_seed(
            npc_id=npc_id,
            current_turn=current_turn,
            conversation_count=conversation_count,
            eligible_quests=eligible if eligible else None,
        )

        # quest_context를 event.data에 주입
        if seed is not None:
            instruction = TIER_INSTRUCTIONS.get(seed.seed_tier, TIER_INSTRUCTIONS[3])
            event.data["quest_context"] = build_seed_context(seed, instruction)
        else:
            # 만료 시드 확인
            ctx = self.build_dialogue_quest_context(npc_id, current_turn)
            if ctx is not None:
                event.data["quest_context"] = ctx

    def _on_dialogue_ended(self, event: GameEvent) -> None:
        """대화 종료 시 META 확인."""
        meta = event.data.get("meta", {})
        seed_response = meta.get("quest_seed_response")

        if seed_response == "accepted":
            seed_id = meta.get("seed_id", "")
            quest_details = meta.get("quest_details", {})
            seed = self.get_seed(seed_id)
            if seed is not None:
                current_turn = event.data.get("turn", 0)
                self.activate_quest(seed, quest_details, current_turn)

    def _on_turn_processed(self, event: GameEvent) -> None:
        """턴 처리: 시드 TTL 체크, urgent 시간 체크."""
        current_turn = event.data.get("turn", 0)
        self.process_all_seed_ttls(current_turn)
        self.check_urgent_time_limits(current_turn)

    def _on_npc_promoted(self, event: GameEvent) -> None:
        """NPC 승격 시 unborn eligible 스캔."""
        npc_id = event.data.get("npc_id", "")
        npc_tags = event.data.get("tags", [])
        npc_node = event.data.get("current_node", "")
        if npc_id:
            self.scan_unborn_eligible(npc_id, npc_tags, npc_node)

    def _on_objective_completed(self, event: GameEvent) -> None:
        """objective_completed 수신."""
        objective_id = event.data.get("objective_id", "")
        current_turn = event.data.get("turn", 0)
        trigger_data = event.data.get("trigger_data", {})
        if objective_id:
            self.complete_objective(objective_id, current_turn, trigger_data)

    def _on_objective_failed(self, event: GameEvent) -> None:
        """objective_failed 수신."""
        objective_id = event.data.get("objective_id", "")
        current_turn = event.data.get("turn", 0)
        fail_reason = event.data.get("fail_reason", "unknown")
        trigger_data = event.data.get("trigger_data", {})
        if objective_id:
            self.fail_objective(objective_id, current_turn, fail_reason, trigger_data)

    # === ORM ↔ Core 변환 ===

    def _quest_to_core(self, orm: QuestModel) -> Quest:
        """ORM → Core. JSON 필드 역직렬화."""
        rewards = None
        if orm.rewards_json:
            rewards = self._rewards_from_dict(json.loads(orm.rewards_json))

        return Quest(
            quest_id=orm.quest_id,
            title=orm.title,
            description=orm.description,
            origin_type=orm.origin_type,
            origin_npc_id=orm.origin_npc_id,
            origin_seed_id=orm.origin_seed_id,
            origin_overlay_id=orm.origin_overlay_id,
            quest_type=orm.quest_type,
            seed_tier=orm.seed_tier,
            urgency=orm.urgency,
            time_limit=orm.time_limit,
            status=orm.status,
            result=orm.result,
            activated_turn=orm.activated_turn,
            completed_turn=orm.completed_turn,
            chain_id=orm.chain_id,
            chain_index=orm.chain_index,
            is_chain_finale=orm.is_chain_finale,
            related_npc_ids=json.loads(orm.related_npc_ids),
            target_node_ids=json.loads(orm.target_node_ids),
            overlay_id=orm.overlay_id,
            resolution_method=orm.resolution_method,
            resolution_comment=orm.resolution_comment,
            resolution_method_tag=orm.resolution_method_tag,
            resolution_impression_tag=orm.resolution_impression_tag,
            rewards=rewards,
            tags=json.loads(orm.tags),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _quest_to_orm(self, core: Quest) -> QuestModel:
        """Core → ORM. JSON 필드 직렬화."""
        rewards_json = None
        if core.rewards:
            rewards_json = json.dumps(self._rewards_to_dict(core.rewards))

        return QuestModel(
            quest_id=core.quest_id,
            title=core.title,
            description=core.description,
            origin_type=core.origin_type,
            origin_npc_id=core.origin_npc_id,
            origin_seed_id=core.origin_seed_id,
            origin_overlay_id=core.origin_overlay_id,
            quest_type=core.quest_type,
            seed_tier=core.seed_tier,
            urgency=core.urgency,
            time_limit=core.time_limit,
            status=core.status,
            result=core.result,
            activated_turn=core.activated_turn,
            completed_turn=core.completed_turn,
            chain_id=core.chain_id,
            chain_index=core.chain_index,
            is_chain_finale=core.is_chain_finale,
            related_npc_ids=json.dumps(core.related_npc_ids),
            target_node_ids=json.dumps(core.target_node_ids),
            overlay_id=core.overlay_id,
            resolution_method=core.resolution_method,
            resolution_comment=core.resolution_comment,
            resolution_method_tag=core.resolution_method_tag,
            resolution_impression_tag=core.resolution_impression_tag,
            rewards_json=rewards_json,
            tags=json.dumps(core.tags),
        )

    def _seed_to_core(self, orm: QuestSeedModel) -> QuestSeed:
        """ORM → Core."""
        return QuestSeed(
            seed_id=orm.seed_id,
            npc_id=orm.npc_id,
            seed_type=orm.seed_type,
            seed_tier=orm.seed_tier,
            created_turn=orm.created_turn,
            ttl_turns=orm.ttl_turns,
            status=orm.status,
            context_tags=json.loads(orm.context_tags),
            expiry_result=orm.expiry_result,
            chain_id=orm.chain_id,
            unresolved_threads=json.loads(orm.unresolved_threads),
        )

    def _seed_to_orm(self, core: QuestSeed) -> QuestSeedModel:
        """Core → ORM."""
        return QuestSeedModel(
            seed_id=core.seed_id,
            npc_id=core.npc_id,
            seed_type=core.seed_type,
            seed_tier=core.seed_tier,
            created_turn=core.created_turn,
            ttl_turns=core.ttl_turns,
            status=core.status,
            context_tags=json.dumps(core.context_tags),
            expiry_result=core.expiry_result,
            chain_id=core.chain_id,
            unresolved_threads=json.dumps(core.unresolved_threads),
        )

    def _objective_to_core(self, orm: QuestObjectiveModel) -> Objective:
        """ORM → Core. target JSON 역직렬화."""
        return Objective(
            objective_id=orm.objective_id,
            quest_id=orm.quest_id,
            description=orm.description,
            objective_type=orm.objective_type,
            target=json.loads(orm.target),
            status=orm.status,
            completed_turn=orm.completed_turn,
            failed_turn=orm.failed_turn,
            fail_reason=orm.fail_reason,
            is_replacement=orm.is_replacement,
            replaced_objective_id=orm.replaced_objective_id,
            replacement_origin=orm.replacement_origin,
        )

    def _objective_to_orm(self, core: Objective) -> QuestObjectiveModel:
        """Core → ORM. target JSON 직렬화."""
        return QuestObjectiveModel(
            objective_id=core.objective_id,
            quest_id=core.quest_id,
            description=core.description,
            objective_type=core.objective_type,
            target=json.dumps(core.target),
            status=core.status,
            completed_turn=core.completed_turn,
            failed_turn=core.failed_turn,
            fail_reason=core.fail_reason,
            is_replacement=core.is_replacement,
            replaced_objective_id=core.replaced_objective_id,
            replacement_origin=core.replacement_origin,
        )

    def _rewards_to_dict(self, rewards: QuestRewards) -> dict:
        """QuestRewards → dict (JSON 직렬화용)."""
        return {
            "relationship_deltas": {
                k: {
                    "affinity": v.affinity,
                    "trust": v.trust,
                    "familiarity": v.familiarity,
                    "reason": v.reason,
                }
                for k, v in rewards.relationship_deltas.items()
            },
            "items": rewards.items,
            "world_changes": [
                {"node_id": w.node_id, "change_type": w.change_type, "data": w.data}
                for w in rewards.world_changes
            ],
            "experience": rewards.experience,
        }

    def _rewards_from_dict(self, data: dict) -> QuestRewards:
        """dict → QuestRewards."""
        deltas = {}
        for k, v in data.get("relationship_deltas", {}).items():
            deltas[k] = RelationshipDelta(
                affinity=v.get("affinity", 0),
                trust=v.get("trust", 0),
                familiarity=v.get("familiarity", 0),
                reason=v.get("reason", ""),
            )

        world_changes = []
        for wc in data.get("world_changes", []):
            world_changes.append(
                WorldChange(
                    node_id=wc.get("node_id", ""),
                    change_type=wc.get("change_type", ""),
                    data=wc.get("data", {}),
                )
            )

        return QuestRewards(
            relationship_deltas=deltas,
            items=data.get("items", []),
            world_changes=world_changes,
            experience=data.get("experience", 0),
        )
