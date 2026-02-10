# src/ INDEX

## 의존 흐름 요약
main.py → api/game.py → services/narrative_service.py → services/ai/base.py
                       → core/engine.py → (axiom, world_gen, navigator, echo, sub_grid, core_rule)
                       → db/models.py
modules/module_manager.py → modules/base.py, core/event_bus.py
modules/geography/module.py → core/(world_gen, navigator, sub_grid)
modules/npc/module.py → services/npc_service.py → core/npc/* + db/models_v2.py

## 루트

### config.py
- **목적:** 애플리케이션 설정 (환경변수/.env 로드)
- **핵심:** pydantic-settings 기반. DATABASE_URL, DEBUG, AI_PROVIDER, AI_API_KEY 등 관리.
- **패턴:** `settings = Settings()` 싱글턴으로 전역 사용.

### main.py
- **목적:** FastAPI 앱 엔트리포인트 및 라이프사이클 관리
- **핵심:** lifespan에서 DB 테이블 생성, ITWEngine 초기화, AI Provider/NarrativeService 초기화.
- **의존:** config, core.engine, db, services.ai, services.narrative_service.

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
- **핵심:** `EventTypes` - NPC_PROMOTED, NPC_CREATED, NPC_DIED, NPC_MOVED, NPC_NEEDED, TURN_PROCESSED.

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

### api/game.py (261줄)
- **목적:** 게임 API 라우터 (`/game` 접두사)
- **핵심:** `POST /game/register` (등록), `GET /game/state/{id}` (상태조회), `POST /game/action` (액션 실행). NarrativeService로 look/move 시 AI 서술 생성.
- **액션:** look, move, rest, investigate, harvest, enter, exit.

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

### db/models_v2.py (338줄)
- **목적:** Phase 2 ORM 모델 정의 (NPC/관계/퀘스트/대화/아이템)
- **핵심:** 16개 테이블. `Column()` 스타일. `relationship()` 없음, FK 제약만. `__table_args__`에 Index/UniqueConstraint 선언.
- **모델:** ItemPrototypeModel, QuestChainModel, BackgroundSlotModel, BackgroundEntityModel, NPCModel, NPCMemoryModel, RelationshipModel, QuestSeedModel, WorldPoolModel, QuestModel, QuestObjectiveModel, QuestChainEligibleModel, QuestUnresolvedThreadModel, DialogueSessionModel, DialogueTurnModel, ItemInstanceModel.
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

---

## services/ - 비즈니스 로직

### services/\_\_init\_\_.py
- **목적:** services 패키지 초기화 (빈 파일)

### services/npc_service.py (404줄)
- **목적:** NPC CRUD, 승격, WorldPool, 기억 관리 (Core↔DB 연결)
- **핵심:** `NPCService` - get_background_entities_at_node, get_npcs_at_node, get_npc_by_id, add_promotion_score(_promote_entity, _register_worldpool), create_npc_for_quest, save_memory, get_memories_for_context. ORM↔Core 변환 메서드 포함.
- **의존:** core.npc.*, db.models_v2, core.event_bus.

### services/narrative_service.py (147줄)
- **목적:** AI 기반 게임 서술 생성 서비스
- **핵심:** `NarrativeService` - AIProvider를 DI로 받아 look/move 서술 생성. AI 불가 시 기본 템플릿 fallback.
- **의존:** services.ai.base (AIProvider 인터페이스만).

### services/ai/\_\_init\_\_.py
- **목적:** AI 모듈 공개 API
- **핵심:** AIProvider, GeminiProvider, MockProvider, get_ai_provider를 re-export.

### services/ai/base.py
- **목적:** AI Provider 추상 인터페이스
- **핵심:** `AIProvider(ABC)` - name(property), is_available(), generate(prompt, context) 3개 추상 메서드.
- **패턴:** 모든 구체 프로바이더가 이 인터페이스 구현.

### services/ai/mock.py
- **목적:** 테스트/폴백용 Mock AI 프로바이더
- **핵심:** `MockProvider` - is_available() 항상 True, generate()는 고정 문자열 반환.
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
