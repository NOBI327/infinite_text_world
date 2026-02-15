# src/ INDEX

## 의존 흐름 요약
main.py → api/game.py → services/narrative_service.py → services/ai/base.py
                       → services/dialogue_service.py → services/narrative_service.py + core/dialogue/* + db/models_v2.py
                       → services/item_service.py → core/item/* + db/models_v2.py
                       → core/engine.py → (axiom, world_gen, navigator, echo, sub_grid, core_rule)
                       → db/models.py
engine/objective_watcher.py → services/quest_service.py + services/companion_service.py
modules/module_manager.py → modules/base.py, core/event_bus.py
modules/geography/module.py → core/(world_gen, navigator, sub_grid)
modules/npc/module.py → services/npc_service.py → core/npc/* + db/models_v2.py
modules/relationship/module.py → services/relationship_service.py → core/relationship/* + db/models_v2.py
modules/dialogue/module.py → services/dialogue_service.py → core/dialogue/* + services/narrative_service.py + db/models_v2.py
modules/item/module.py → services/item_service.py → core/item/* + db/models_v2.py
modules/quest/module.py → services/quest_service.py → core/quest/* + db/models_v2.py
modules/companion/module.py → services/companion_service.py → core/companion/* + db/models_v2.py

## 루트

### config.py
- **목적:** 애플리케이션 설정 (환경변수/.env 로드)
- **핵심:** pydantic-settings 기반. DATABASE_URL, DEBUG, AI_PROVIDER, AI_API_KEY 등 관리.
- **패턴:** `settings = Settings()` 싱글턴으로 전역 사용.

### main.py
- **목적:** FastAPI 앱 엔트리포인트 및 라이프사이클 관리
- **핵심:** lifespan에서 DB 테이블 생성, ITWEngine 초기화, AI Provider/NarrativeService/DialogueService/ItemService/QuestService/CompanionService/ObjectiveWatcher 초기화. PrototypeRegistry+AxiomTagMapping 로드 후 ItemService 생성, sync_prototypes_to_db 실행. ObjectiveWatcher는 __init__에서 자동 구독.
- **의존:** config, core.engine, core.event_bus, core.item.registry, core.item.axiom_mapping, engine.objective_watcher, db, services.ai, services.narrative_service, services.dialogue_service, services.item_service, services.quest_service, services.companion_service.

---

## engine/ - ModuleManager 내부 컴포넌트

### engine/\_\_init\_\_.py
- **목적:** engine 패키지 초기화

### engine/objective_watcher.py
- **목적:** 활성 퀘스트 목표 감시 + 달성/실패 판정
- **핵심:** `ObjectiveWatcher` - EventBus를 구독하여 player_moved, action_completed, dialogue_started/ended, check_result, item_given, npc_died 이벤트를 감시. 활성 목표(reach_node, deliver, escort, talk_to_npc, resolve_check)와 대조하여 objective_completed/objective_failed 이벤트 발행. deliver 누적 수량은 in-memory dict 관리.
- **의존:** core.event_bus, core.event_types. services.quest_service (get_active_objectives_by_type), services.companion_service (is_companion).

### engine/replacement_choices.py
- **목적:** 대체 목표 선택지 시스템 메시지 포맷
- **핵심:** `format_replacement_choices` - 실패한 목표 설명 + 대체 목표 리스트를 시스템 메시지로 포맷. Alpha에서는 가이드 메시지, 대체 목표는 전부 active.

---

## core/ - 게임 핵심 로직 (DB 무관)

### core/\_\_init\_\_.py
- **목적:** core 패키지 공개 API 정의
- **핵심:** 모든 핵심 클래스를 re-export. AxiomLoader, WorldGenerator, Navigator, EchoManager, ResolutionEngine, ITWEngine 등.
- **버전:** 0.1.0-alpha.

### core/logging.py
- **목적:** 프로젝트 공용 로깅 설정
- **핵심:** `setup_logging(level)` 으로 포맷/레벨 초기화, `get_logger(name)` 으로 모듈별 로거 생성.
- **규칙:** print() 대신 logging 사용 (CLAUDE.md 규칙).

### core/axiom_system.py (390줄)
- **목적:** 214 Divine Axioms 로더 및 태그 벡터 시스템
- **핵심:** `AxiomLoader` - JSON에서 214개 공리 로드, ID/code/domain/resonance/tier 다중 인덱스 검색. `AxiomVector` - 엔티티의 태그 가중치 벡터 (병합, 상위 N개 추출).
- **주요 클래스:** Axiom, AxiomVector, AxiomLoader, DomainType(8종), ResonanceType(8종).

### core/world_generator.py (661줄)
- **목적:** 무한 좌표 기반 절차적 월드 생성
- **핵심:** `WorldGenerator` - (x,y) 좌표 시드 기반 결정론적 노드 생성. 희귀도 분포(94/5/1%), 클러스터 상속(40%), 감각 데이터/자원 자동 생성.
- **주요 클래스:** MapNode, NodeTier, Resource, SensoryData, Echo.

### core/navigator.py (680줄)
- **목적:** 탐색 시스템 및 Fog of War
- **핵심:** `Navigator` - 4방향(NSEW)+상하 이동, Supply 소모, 위험도 추정, 장비 체크. 좌표를 해시로 숨겨 플레이어에게 감각 힌트만 제공. 서브 그리드 내 이동(`travel_sub_grid`) 지원.
- **주요 클래스:** Direction, DirectionHint, LocationView, TravelResult, Navigator.

### core/sub_grid.py (386줄)
- **목적:** 메인 노드 내부 서브 그리드(L3 Depth) 시스템
- **핵심:** `SubGridGenerator` - 부모 좌표+서브 좌표(sx,sy,sz) 기반 절차적 생성. 유효 난이도 = depth_tier + abs(sz). 도메인별 감각 템플릿.
- **주요 클래스:** SubGridType(Dungeon/Tower/Forest/Cave), DepthPoint, SubGridNode, SubGridGenerator.

### core/echo_system.py (556줄)
- **목적:** 노드 메모리(Echo) 및 조사 시스템
- **핵심:** `EchoManager` - 8개 카테고리별 Echo 생성(템플릿+Axiom 강화), d6 Dice Pool 기반 조사 판정, 시간 경과 소멸(Short Echo). 글로벌 훅(보스 킬 등) 관리.
- **주요 클래스:** EchoType, EchoVisibility, EchoCategory, EchoManager, InvestigationResult.

### core/core_rule.py (315줄)
- **목적:** Protocol T.A.G. 판정 엔진 (d6 Dice Pool)
- **핵심:** `ResolutionEngine` - 스탯(WRITE/READ/EXEC/SUDO) 기반 Dice Pool 구성, 5/6=Hit, 4단계 결과(Critical Success/Success/Failure/Critical Failure). `CharacterSheet` - 4대 스탯 + 8대 Resonance Shield.
- **주요 클래스:** StatType, CheckResultTier, CheckResult, CharacterSheet, ResolutionEngine.

### core/engine.py (1250줄)
- **목적:** ITW 메인 엔진 - 모든 하위 시스템 통합
- **핵심:** `ITWEngine` - AxiomLoader/WorldGenerator/Navigator/EchoManager/ResolutionEngine 조합. 게임 액션(look/move/investigate/harvest/rest/enter/exit) 처리. DB 저장/로드(SQLAlchemy Session). CLI 데모 포함.
- **주요 클래스:** PlayerState, ActionResult, ITWEngine.

### core/event_bus.py
- **목적:** 모듈/서비스 간 동기식 이벤트 통신 인프라
- **핵심:** `EventBus` - subscribe/emit/unsubscribe. 전파 깊이 최대 5단계, 동일 source 중복 발행 차단. `GameEvent(event_type, data, source)`.
- **주요 클래스:** GameEvent, EventBus.

### core/event_types.py
- **목적:** 이벤트 유형 문자열 상수
- **핵심:** `EventTypes` - NPC_PROMOTED, NPC_CREATED, NPC_DIED, NPC_MOVED, NPC_NEEDED, RELATIONSHIP_CHANGED, RELATIONSHIP_REVERSED, ATTITUDE_REQUEST, ATTITUDE_RESPONSE, DIALOGUE_STARTED, DIALOGUE_ENDED, QUEST_SEED_GENERATED, TURN_PROCESSED, ITEM_TRANSFERRED, ITEM_BROKEN, ITEM_CREATED, QUEST_ACTIVATED, QUEST_COMPLETED, QUEST_FAILED, QUEST_ABANDONED, QUEST_SEED_CREATED, QUEST_SEED_EXPIRED, QUEST_CHAIN_FORMED, QUEST_CHAIN_FINALIZED, CHAIN_ELIGIBLE_MATCHED, OBJECTIVE_COMPLETED, OBJECTIVE_FAILED, PLAYER_MOVED, ACTION_COMPLETED, ITEM_GIVEN, CHECK_RESULT, COMPANION_JOINED, COMPANION_MOVED, COMPANION_DISBANDED.

### core/dialogue/ - 대화 시스템 Core 로직 (순수 Python, DB 무관)

### core/dialogue/models.py
- **목적:** 대화 세션/턴 도메인 모델
- **핵심:** `DialogueSession` - 세션 상태, 예산, NPC 컨텍스트, 누적 delta. `DialogueTurn` - 턴별 PC 입력, NPC 응답, META.
- **주요 클래스:** DialogueSession, DialogueTurn.

### core/dialogue/budget.py
- **목적:** 대화 예산 계산 및 페이즈 관리
- **핵심:** `calculate_budget(rel_status, hexaco_x, has_seed)` - 관계+HEXACO+시드 기반 예산. `get_budget_phase(remaining, total)` - 4단계(open/winding/closing/final). `get_phase_instruction(phase, seed_delivered, has_seed)` - 페이즈별 지시.

### core/dialogue/hexaco_descriptors.py
- **목적:** HEXACO 6요인 → 자연어 성격 설명 변환
- **핵심:** `hexaco_to_natural_language(hexaco_dict)` - 6요인 수치를 일본어 성격 요약으로 변환.

### core/dialogue/validation.py
- **목적:** LLM META JSON 검증 및 보정
- **핵심:** `validate_meta(raw_meta)` - 스키마 기반 검증. 누락 키 보충, 범위 초과 클램프, 타입 불일치 교정.

### core/dialogue/constraints.py
- **목적:** PC 행동 해석(action_interpretation) 검증
- **핵심:** `validate_action_interpretation(ai, pc_axioms, pc_items, pc_stats)` - LLM이 생성한 행동 해석을 PC 제약 조건에 맞춰 검증/보정.

### core/relationship/ - 관계 시스템 Core 로직

### core/relationship/models.py
- **목적:** 관계 도메인 모델 (DB 무관)
- **핵심:** RelationshipStatus, Relationship, AttitudeContext

### core/relationship/calculations.py
- **목적:** 3축 수치 계산
- **핵심:** affinity/trust 감쇠, familiarity 시간 감쇠, 클램프

### core/relationship/transitions.py
- **목적:** 관계 상태 전이 판정
- **핵심:** TRANSITION_TABLE, 우선순위 기반 전이 평가

### core/relationship/reversals.py
- **목적:** 반전 이벤트 처리
- **핵심:** betrayal/redemption/trust_collapse 공식

### core/relationship/attitude.py
- **목적:** 태도 태그 생성 파이프라인
- **핵심:** 3단계 (수치 → HEXACO → 기억), 태그 2~7개

### core/relationship/npc_opinions.py
- **목적:** NPC간 의견 태그
- **핵심:** 관계 수치 → 대화용 태그 변환

### core/npc/ - NPC 핵심 로직 (순수 Python, DB 무관)

### core/npc/\_\_init\_\_.py
- **목적:** npc 패키지 공개 API (re-export)
- **핵심:** models, hexaco, tone, slots, promotion, naming, memory 전체 심볼 re-export.

### core/npc/models.py
- **목적:** NPC 데이터 모델 정의
- **핵심:** `EntityType(Enum)` - RESIDENT/WANDERER/HOSTILE. `BackgroundEntity` - 배경 존재 데이터. `BackgroundSlot` - 시설 슬롯. `HEXACO` - 6요인 성격 모델. `NPCData` - 승격된 NPC 전체 데이터.
- **주요 클래스:** EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData.

### core/npc/hexaco.py
- **목적:** HEXACO 성격 생성 및 행동 수정자
- **핵심:** `generate_hexaco(role, seed)` - 역할별 템플릿 + ±0.15 랜덤 분산. `get_behavior_modifier(hexaco, factor, modifier)` - 성격→행동 변환.
- **주요 데이터:** ROLE_HEXACO_TEMPLATES(7종), HEXACO_BEHAVIOR_MAP(6요인×2).

### core/npc/tone.py
- **목적:** NPC 어조/감정 태그 시스템
- **핵심:** `derive_manner_tags(hexaco)` - HEXACO→태도 태그. `calculate_emotion(event, affinity, hexaco)` - 이벤트+관계→감정 도출.
- **주요 클래스:** ToneContext.

### core/npc/slots.py
- **목적:** 시설 배경 슬롯 관리
- **핵심:** `calculate_slot_count(facility_type, size)` - 시설 크기별 슬롯 수. `should_reset_slot(score, turns, interval)` - 슬롯 리셋 판정.
- **주요 데이터:** FACILITY_BASE_SLOTS(7종), FACILITY_REQUIRED_ROLES(7종).

### core/npc/promotion.py
- **목적:** 배경 존재 → NPC 승격 시스템
- **핵심:** `calculate_new_score(current, action)` - 행동별 점수 부여. `check_promotion_status(score)` - 임계값 판정(50=promoted, 15=worldpool). `build_npc_from_entity(entity, hexaco)` - 순수 변환.
- **주요 상수:** PROMOTION_THRESHOLD=50, WORLDPOOL_THRESHOLD=15, PROMOTION_SCORE_TABLE(10종).

### core/npc/naming.py
- **목적:** NPC 이름 절차적 생성
- **핵심:** `generate_name(seed, rng_seed)` - 시드 기반 이름 생성. `NPCFullName` - formal/current/short_name 포맷.
- **주요 클래스:** NPCNameSeed, NPCFullName.

### core/npc/memory.py
- **목적:** NPC 3계층 기억 시스템
- **핵심:** `create_memory(...)` - 자동 importance 할당. `assign_tier1_slot(memories, new)` - 고정2+교체3 슬롯 관리. `enforce_tier2_capacity(memories, status)` - 관계별 용량 제한. `get_memories_for_context(all, status)` - Tier 1+2만 반환.
- **주요 클래스:** NPCMemory. **주요 데이터:** IMPORTANCE_TABLE(7종), TIER2_CAPACITY(5단계).

### core/item/ - 아이템 시스템 Core 로직 (순수 Python, DB 무관)

### core/item/\_\_init\_\_.py
- **목적:** item 패키지 공개 API (re-export)
- **핵심:** ItemType, ItemPrototype, ItemInstance, PrototypeRegistry, AxiomTagInfo, AxiomTagMapping re-export.

### core/item/models.py
- **목적:** 아이템 도메인 모델 (Prototype + Instance)
- **핵심:** `ItemType(str, Enum)` - EQUIPMENT/CONSUMABLE/MATERIAL/MISC. `ItemPrototype(frozen=True)` - 불변 원형 (id, type, weight, bulk, base_value, axiom_tags, max_durability 등). `ItemInstance` - 가변 인스턴스 (owner, durability, state_tags).
- **주요 클래스:** ItemType, ItemPrototype, ItemInstance.

### core/item/registry.py
- **목적:** 프로토타입 레지스트리 (JSON 로드 + 검색)
- **핵심:** `PrototypeRegistry` - load_from_json(60종 시드), register, get, get_all, search_by_tags(OR 로직), search_by_axiom, count.

### core/item/axiom_mapping.py
- **목적:** 자유 태그 → Divine Axiom 매핑
- **핵심:** `AxiomTagInfo(frozen=True)` - tag, domain, resonance, axiom_ids. `AxiomTagMapping` - load_from_json(23종), get, get_domain, get_resonance, get_all_tags.
- **주요 클래스:** AxiomTagInfo, AxiomTagMapping.

### core/item/inventory.py
- **목적:** Bulk 기반 인벤토리 용량 계산
- **핵심:** `calculate_inventory_capacity(stats)` - BASE 50 + (EXEC-2)*5, min 30. `calculate_current_bulk`, `can_add_item`.
- **주요 상수:** BASE_INVENTORY_CAPACITY=50.

### core/item/durability.py
- **목적:** 내구도 소모 및 파괴 판정
- **핵심:** `apply_durability_loss(instance, prototype)` - 사용 시 내구도 감소, 0 이하 시 파괴(broken_result 반환). `get_durability_ratio` - 0.0~1.0.

### core/item/trade.py
- **목적:** 거래 가격 계산 및 흥정(Haggle) 시스템
- **핵심:** `calculate_trade_price` - 기본값×매매 배수×관계 할인×HEXACO H×내구도. `evaluate_haggle` - HEXACO A 기반 수락/역제안/거절. `calculate_counter_price` - 중간값.
- **주요 데이터:** RELATIONSHIP_DISCOUNT(6단계).

### core/item/gift.py
- **목적:** 선물 호감도 계산
- **핵심:** `calculate_gift_affinity(base_value, npc_desire_tags, item_tags)` - base 1 + 가치 보너스 + 태그 매칭, max 5.

### core/item/constraints.py
- **목적:** PC 아이템 제약 조건 빌드 (대화 시스템 연동)
- **핵심:** `build_item_constraints(instances, get_prototype)` - {pc_items, pc_axiom_powers} 반환. DI 콜러블로 Core↔Service 분리.

### core/item/restock.py (TEMPORARY)
- **목적:** 상점 재입고 로직 (NPC Phase B에서 자율 행동으로 대체 예정)
- **핵심:** `ShopRestockConfig` - npc_id, shelf_instance_id, stock_template, restock_cooldown, max_stock_per_item. `check_restock_needed` - 쿨다운 모듈로 판정. `calculate_restock_deficit` - 부족 수량 계산.

### core/quest/ - 퀘스트 시스템 Core 로직 (순수 Python, DB 무관)

### core/quest/\_\_init\_\_.py
- **목적:** quest 패키지 공개 API (re-export)
- **핵심:** enums, models, probability 전체 심볼 re-export.

### core/quest/enums.py
- **목적:** 퀘스트 관련 열거형
- **핵심:** QuestType(7종), ObjectiveType(5종), QuestStatus(4종), QuestResult(4종), SeedType(4종), SeedStatus(4종), ObjectiveStatus(3종), Urgency(2종).

### core/quest/models.py
- **목적:** 퀘스트 도메인 모델 (DB 무관)
- **핵심:** `QuestSeed` - 퀘스트 떡밥. `Quest` - 퀘스트 본체 (출처/유형/상태/체이닝/보상). `Objective` - 목표 단위 (대체 목표 지원). `QuestRewards` - 보상 (관계 변동/아이템/경험치). `ChainEligibleNPC`, `RelationshipDelta`, `WorldChange`.

### core/quest/probability.py
- **목적:** 퀘스트 확률 판정 (순수 Python)
- **핵심:** `roll_seed_chance` (5%), `determine_seed_tier` (3/2/1=60/30/10%), `roll_chain_chance` (티어별), `should_finalize_chain` (길이별), `can_generate_seed` (쿨다운), `get_default_ttl` (유형별 TTL).

### core/quest/seed_logic.py
- **목적:** 시드 생성 + TTL 처리 로직
- **핵심:** `try_generate_seed` - 쿨다운+확률+체이닝 통합 판정. `process_seed_ttl` - 만료 체크. `select_seed_type` - 균등 분포.

### core/quest/result_logic.py
- **목적:** 퀘스트 결과 판정 + 보상 계산
- **핵심:** `evaluate_quest_result` - success/partial/failure/None 4단계. `calculate_rewards` - 티어 스케일링. `calculate_pc_tendency` - 최근 퀘스트 기반 스타일 산출.

### core/quest/objective_logic.py
- **목적:** Objective 관련 로직 (hint 매핑, 대체 목표, fallback)
- **핵심:** `map_hint_to_objective_type` - LLM hint→type. `validate_objectives_hint` - 검증+fallback. `generate_replacement_objectives` - 실패 시 대체 목표 (client_consult 필수). `create_fallback_objectives` - 퀘스트 유형별 기본 목표.

### core/quest/chain_logic.py
- **목적:** 체이닝 관련 로직
- **핵심:** `match_unborn_npc` - 승격 NPC 매칭. `build_chain_eligible_npcs` - 티어별 eligible 생성. `build_chain_context` - LLM 체이닝 컨텍스트.

### core/quest/context_builder.py
- **목적:** LLM 프롬프트용 퀘스트 컨텍스트 빌더
- **핵심:** `build_seed_context`, `build_activation_context`, `build_expired_seed_context`, `build_failure_report_context`, `build_quest_update_context`. TIER_INSTRUCTIONS(3단계), FINALE_INSTRUCTION.

### core/companion/ - 동행 시스템 Core 로직 (순수 Python, DB 무관)

### core/companion/\_\_init\_\_.py
- **목적:** companion 패키지 공개 API (re-export)
- **핵심:** CompanionState, acceptance, conditions, return_logic 전체 심볼 re-export.

### core/companion/models.py
- **목적:** 동행 도메인 모델
- **핵심:** `CompanionState` - companion_id, player_id, npc_id, companion_type, quest_id, status, condition 등.

### core/companion/acceptance.py
- **목적:** 동행 수락 판정
- **핵심:** `quest_companion_accept_chance` - 퀘스트 동행 수락률 (기본 90%, 구출 98%). `roll_quest_companion` - 판정. `voluntary_companion_accept` - 관계·성격 기반 수락 (ACCEPT_BY_STATUS + trust/HEXACO 보정).

### core/companion/conditions.py
- **목적:** 동행 조건 생성 + 만료 판정
- **핵심:** `roll_condition` (40%). `generate_condition_data` - 유형별 데이터 생성 (payment/time_limit/destination_only/safety_guarantee/item_request). `check_condition_expired` - 만료 판정.

### core/companion/return_logic.py
- **목적:** 해산 후 NPC 귀환 목적지 결정
- **핵심:** `determine_return_destination` - escort 완료→잔류, 정주형→home_node, 방랑형→잔류.

---

## api/ - FastAPI 엔드포인트

### api/\_\_init\_\_.py
- **목적:** api 패키지 초기화 (빈 파일)

### api/health.py
- **목적:** 헬스체크 엔드포인트
- **핵심:** `GET /health` - DB 연결 상태 확인 (`SELECT 1`). ok/error 반환.
- **의존:** db.database (get_db).

### api/schemas.py (91줄)
- **목적:** API 요청/응답 Pydantic 스키마
- **핵심:** Request - RegisterRequest, ActionRequest. Response - GameStateResponse, ActionResponse, LocationInfo, DirectionInfo, PlayerInfo, ErrorResponse.
- **패턴:** 모든 필드에 타입 어노테이션 및 Field 설명.

### api/game.py
- **목적:** 게임 API 라우터 (`/game` 접두사)
- **핵심:** `POST /game/register` (등록), `GET /game/state/{id}` (상태조회), `POST /game/action` (액션 실행). NarrativeService로 look/move 시 AI 서술 생성. DialogueService로 talk/say/end_talk 대화 처리. ItemService로 inventory/pickup/drop/use/browse/give 아이템 처리. QuestService로 quest_list/quest_detail/quest_abandon 퀘스트 처리. CompanionService로 recruit/dismiss 동행 처리. 이벤트 훅: move/enter/exit → PLAYER_MOVED, look/investigate → ACTION_COMPLETED, give → ITEM_GIVEN.
- **액션:** look, move, rest, investigate, harvest, enter, exit, talk, say, end_talk, inventory, pickup, drop, use, browse, give, quest_list, quest_detail, quest_abandon, recruit, dismiss.

---

## db/ - ORM 모델 및 DB 설정

### db/\_\_init\_\_.py
- **목적:** db 패키지 초기화 (빈 파일)

### db/database.py
- **목적:** SQLAlchemy 엔진 및 세션 팩토리
- **핵심:** SQLite 기반. `create_engine` + `SessionLocal`. `get_db()` 제너레이터로 FastAPI 의존성 주입.
- **설정:** config.settings에서 DATABASE_URL/DEBUG 참조.

### db/models.py (138줄)
- **목적:** SQLAlchemy ORM 모델 정의 (v1)
- **핵심:** `MapNodeModel` (좌표/tier/axiom/sensory + L3 Depth 필드), `ResourceModel`, `EchoModel`, `PlayerModel` (위치/스탯/인벤토리/currency), `SubGridNodeModel`.
- **관계:** MapNode 1:N Resource, MapNode 1:N Echo (cascade delete).

### db/models_v2.py (506줄)
- **목적:** Phase 2 ORM 모델 정의 (NPC/관계/퀘스트/대화/아이템)
- **핵심:** 16개 테이블. `Mapped[T]` + `mapped_column()` 스타일 (models.py와 일관). `relationship()` 없음, FK 제약만. `__table_args__`에 Index/UniqueConstraint 선언.
- **모델:** ItemPrototypeModel, QuestChainModel, BackgroundSlotModel, BackgroundEntityModel, NPCModel, NPCMemoryModel, RelationshipModel, QuestSeedModel, WorldPoolModel, QuestModel, QuestObjectiveModel, QuestChainEligibleModel, QuestUnresolvedThreadModel, DialogueSessionModel, DialogueTurnModel, ItemInstanceModel, CompanionModel, CompanionLogModel.
- **참조:** DDL은 docs/30_technical/db-schema-v2.md.

---

## modules/ - 토글 가능한 기능 모듈

### modules/base.py
- **목적:** 모듈 기반 인터페이스 정의
- **핵심:** `GameModule(ABC)` - name, on_enable, on_disable, on_turn, on_node_enter, get_available_actions. `GameContext` - player_id, current_node_id, current_turn, db_session, extra. `Action` - name, display_name, module_name, description, params.
- **주요 클래스:** GameModule, GameContext, Action.

### modules/module_manager.py
- **목적:** 모듈 등록/활성화/비활성화/의존성 검증/턴 전파
- **핵심:** `ModuleManager` - 자체 EventBus 소유. register/enable/disable(cascade)/process_turn/process_node_enter/get_all_actions.
- **주요 클래스:** ModuleManager.

### modules/geography/module.py
- **목적:** 지리 시스템 모듈 (WorldGenerator/Navigator/SubGridGenerator 래핑)
- **핵심:** `GeographyModule` - 맵 노드 조회, 위치 정보, 서브그리드. on_node_enter에서 context.extra["geography"] 설정.
- **의존성:** 없음 (Layer 1).

### modules/npc/module.py
- **목적:** NPC 시스템 모듈 (NPCService 래핑, GameModule 인터페이스)
- **핵심:** `NPCCoreModule` - NPCService 생성/관리, npc_needed 이벤트 구독, 노드 진입 시 NPC/엔티티 정보 context.extra["npc_core"]에 저장. 공개 API: get_npcs_at_node, get_npc_by_id, get_background_entities_at_node, add_promotion_score.
- **의존성:** ["geography"].

### modules/relationship/module.py
- **목적:** RelationshipModule — GameModule 인터페이스
- **핵심:** `RelationshipModule` - RelationshipService 래핑, EventBus 구독 (npc_promoted, dialogue_ended, attitude_request). 턴 처리: familiarity 감쇠. 공개 API: get_relationship, get_relationships_for, generate_attitude.
- **의존성:** ["npc_core"].

### modules/dialogue/module.py
- **목적:** DialogueModule — GameModule 인터페이스
- **핵심:** `DialogueModule` - DialogueService 래핑 (DI). 대화 상태를 context.extra["dialogue"]에 표시. talk/say/end_talk 액션 제공. EventBus 구독은 DialogueService가 자체 처리.
- **의존성:** ["npc_core", "relationship"].

### modules/item/\_\_init\_\_.py
- **목적:** item 모듈 패키지 초기화
- **핵심:** ItemModule re-export.

### modules/item/module.py
- **목적:** ItemModule — GameModule 인터페이스
- **핵심:** `ItemModule` - ItemService 래핑. on_node_enter에서 context.extra["item"]에 노드 아이템 정보 설정. inventory/pickup/drop/use/browse 5개 액션 제공. TEMPORARY: register_restock_config로 상점 재입고 설정, on_turn에서 쿨다운 기반 자동 재입고 실행.
- **의존성:** [] (Layer 1).

### modules/quest/\_\_init\_\_.py
- **목적:** quest 모듈 패키지 초기화
- **핵심:** QuestModule re-export.

### modules/quest/module.py
- **목적:** QuestModule — GameModule 인터페이스
- **핵심:** `QuestModule` - QuestService 래핑. on_node_enter에서 context.extra["quest"]에 활성 퀘스트 수, 현재 노드 관련 퀘스트 정보 설정. quest_list/quest_detail/quest_abandon 3개 액션 제공.
- **의존성:** ["npc_core", "relationship", "dialogue"].

### modules/companion/\_\_init\_\_.py
- **목적:** companion 모듈 패키지 초기화
- **핵심:** CompanionModule re-export.

### modules/companion/module.py
- **목적:** CompanionModule — GameModule 인터페이스
- **핵심:** `CompanionModule` - CompanionService 래핑. on_node_enter에서 context.extra["companion"]에 동행 NPC 정보 설정. recruit/dismiss 2개 액션 제공.
- **의존성:** ["npc_core", "relationship", "dialogue"].

---

## services/ - 비즈니스 로직

### services/\_\_init\_\_.py
- **목적:** services 패키지 초기화 (빈 파일)

### services/npc_service.py (404줄)
- **목적:** NPC CRUD, 승격, WorldPool, 기억 관리 (Core↔DB 연결)
- **핵심:** `NPCService` - get_background_entities_at_node, get_npcs_at_node, get_npc_by_id, add_promotion_score(_promote_entity, _register_worldpool), create_npc_for_quest, save_memory, get_memories_for_context. ORM↔Core 변환 메서드 포함.
- **의존:** core.npc.*, db.models_v2, core.event_bus.

### services/relationship_service.py
- **목적:** Relationship Service — Core와 DB 연결
- **핵심:** `RelationshipService` - get/create/apply_dialogue_delta/apply_action_delta/apply_reversal/process_familiarity_decay/create_initial_npc_relationships/generate_attitude. ORM↔Core 변환.
- **의존:** core.relationship.*, db.models_v2, core.event_bus.

### services/item_service.py
- **목적:** 아이템 CRUD, 거래, 선물, 인벤토리 관리 Service (Core↔DB 연결)
- **핵심:** `ItemService` - Prototype: get_prototype, sync_prototypes_to_db. Instance: create_instance(uuid+event), get_instance, get_instances_by_owner, count_instances, transfer_item(event). Durability: use_item(파괴 시 broken_result 생성). Trade: calculate_price, process_haggle, execute_trade(통화 갱신). Gift: process_gift(호감도+이전). Constraints: get_item_constraints. Inventory: get_inventory_bulk, get_inventory_capacity, can_add_to_inventory. EventBus 구독: DIALOGUE_ENDED(stub).
- **의존:** core.item.*, core.event_bus, db.models, db.models_v2.

### services/quest_service.py
- **목적:** 퀘스트 CRUD, 시드 관리, 체이닝, 결과 판정, LLM 컨텍스트 빌드 Service (Core↔DB 연결)
- **핵심:** `QuestService` - Seed: create_seed, get_seed, get_active_seeds_for_npc, process_all_seed_ttls. Quest: activate_quest, get_quest, get_active_quests, get_quest_objectives, get_active_objectives_by_type, abandon_quest. Result: check_quest_completion, complete_objective, fail_objective. Chaining: find_quests_with_eligible_npc, finalize_quest_chain, scan_unborn_eligible. Context: build_dialogue_quest_context, build_quest_activation_context, get_pc_tendency. Time: check_urgent_time_limits. EventBus 구독: DIALOGUE_STARTED/ENDED, TURN_PROCESSED, NPC_PROMOTED, OBJECTIVE_COMPLETED/FAILED. ORM↔Core 변환 메서드 포함.
- **의존:** core.quest.*, core.event_bus, db.models_v2.

### services/companion_service.py
- **목적:** 동행 CRUD, 요청/수락/해산, 이동 동기화, 조건 체크, 퀘스트 동행 자동 처리 Service (Core↔DB 연결)
- **핵심:** `CompanionService` - get_active_companion, is_companion, request_quest_companion, request_voluntary_companion, dismiss_companion, build_companion_context. EventBus 구독: PLAYER_MOVED(이동 동기화), QUEST_ACTIVATED/COMPLETED/FAILED/ABANDONED(퀘스트 동행 자동 처리), NPC_DIED(강제 해산), TURN_PROCESSED(조건 만료 체크). ORM↔Core 변환.
- **의존:** core.companion.*, core.event_bus, db.models_v2.

### services/dialogue_service.py
- **목적:** 대화 세션 관리 Service (Core↔DB 연결, EventBus 통신)
- **핵심:** `DialogueService` - start_session/process_turn/end_session 생명주기. 예산 계산, NarrativeService 호출, META 검증, 누적 delta/memory 관리, DB 영속화. EventBus 구독: attitude_response, quest_seed_generated.
- **의존:** core.dialogue.*, core.event_bus, db.models_v2, services.narrative_service (DI).

### services/narrative_service.py
- **목적:** AI 기반 게임 서술 생성 서비스 (v2.0 — 단일 관문)
- **핵심:** `NarrativeService` - PromptBuilder/ResponseParser/Safety 조합. generate_look/move (기존 호환) + generate_dialogue_response/quest_seed/impression_tag (신규). 3단계 폴백 체인 (통상→간소화→템플릿).
- **의존:** services.ai.base, services.narrative_types, services.narrative_prompts, services.narrative_parser, services.narrative_safety.

### services/narrative_types.py
- **목적:** Narrative 관련 타입 정의
- **핵심:** `NarrativeRequestType(Enum)` - LOOK/MOVE/DIALOGUE/QUEST_SEED/IMPRESSION_TAG. `DialoguePromptContext` - 대화 프롬프트 컨텍스트. `QuestSeedPromptContext` - 퀘스트 시드 컨텍스트. `NarrativeResult` - narrative + raw_meta. `NarrativeConfig`, `BuiltPrompt`.

### services/narrative_prompts.py
- **목적:** 호출 유형별 프롬프트 빌더
- **핵심:** `PromptBuilder` - build_look/move/dialogue/quest_seed/impression_tag. 일본어 시스템 프롬프트 + 구조화된 유저 프롬프트 조립. `DIALOGUE_TOKEN_MAP` 페이즈별 토큰 제한.

### services/narrative_parser.py
- **목적:** LLM 응답 파싱 (narrative + META 분리)
- **핵심:** `ResponseParser` - parse_dual (3단계: 전체 JSON → ```json 블록 → fallback), parse_text.

### services/narrative_safety.py
- **목적:** 콘텐츠 안전 필터 + 나레이션 레벨 관리 (Alpha 최소)
- **핵심:** `NarrationManager` - 카테고리별 나레이션 레벨 캐시. `ContentSafetyFilter` - scene_direction 프롬프트 생성.

### services/ai/\_\_init\_\_.py
- **목적:** AI 모듈 공개 API
- **핵심:** AIProvider, GeminiProvider, MockProvider, get_ai_provider를 re-export.

### services/ai/base.py
- **목적:** AI Provider 추상 인터페이스
- **핵심:** `AIProvider(ABC)` - name(property), is_available(), generate(prompt, system_prompt, max_tokens, context) 추상 메서드.
- **패턴:** 모든 구체 프로바이더가 이 인터페이스 구현.

### services/ai/mock.py
- **목적:** 테스트/폴백용 Mock AI 프로바이더
- **핵심:** `MockProvider` - is_available() 항상 True, generate()는 고정 문자열 반환. JSON 요청 시 MOCK_DIALOGUE_RESPONSE 반환.
- **용도:** API 키 미설정 시 자동 사용.

### services/ai/factory.py
- **목적:** AI Provider 인스턴스 팩토리
- **핵심:** `get_ai_provider(name)` - config 기반으로 mock/gemini 프로바이더 생성. API 키 없거나 알 수 없는 프로바이더면 MockProvider 폴백.
- **의존:** config.settings, ai.base, ai.gemini, ai.mock.

### services/ai/gemini.py
- **목적:** Google Gemini API 프로바이더 구현
- **핵심:** `GeminiProvider` - google-generativeai SDK로 텍스트 생성. 기본 모델 gemini-2.0-flash.
- **에러:** API 실패 시 RuntimeError 발생 (상위에서 fallback 처리).

---

## data/ - 정적 데이터

### data/\_\_init\_\_.py
- **목적:** data 패키지 초기화 (빈 파일)

### data/itw_214_divine_axioms.json
- **목적:** 214 Divine Axioms 마스터 데이터
- **핵심:** 214개 공리의 id, code, name(latin/kr/en), domain, resonance, tier, logic(passive/on_contact/damage_mod), tags, flavor.
- **용도:** AxiomLoader가 시작 시 로드.

### data/seed_items.json
- **목적:** 아이템 프로토타입 시드 데이터 (60종)
- **핵심:** 20 EQUIPMENT, 11 CONSUMABLE, 14 MATERIAL, 12 MISC, 3 파괴 부산물. 각 아이템: item_id, item_type, weight, bulk, base_value, primary_material, axiom_tags, max_durability, durability_loss_per_use, tags, name_kr 등.
- **용도:** PrototypeRegistry.load_from_json으로 시작 시 로드.

### data/axiom_tag_mapping.json
- **목적:** 자유 태그 → Divine Axiom 매핑 데이터 (23종)
- **핵심:** 각 태그: tag, domain, resonance, axiom_ids, description. Ignis/Ferrum/Aqua/Herba 등 물성 태그를 8개 도메인+8개 레조넌스에 연결.
- **용도:** AxiomTagMapping.load_from_json으로 시작 시 로드.
