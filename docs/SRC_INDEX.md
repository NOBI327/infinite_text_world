# src/ INDEX

## 의존 흐름 요약
main.py → api/game.py → services/narrative_service.py → services/ai/base.py
                       → core/engine.py → (axiom, world_gen, navigator, echo, sub_grid, core_rule)
                       → db/models.py

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

### db/models.py (137줄)
- **목적:** SQLAlchemy ORM 모델 정의
- **핵심:** `MapNodeModel` (좌표/tier/axiom/sensory + L3 Depth 필드), `ResourceModel`, `EchoModel`, `PlayerModel` (위치/스탯/인벤토리), `SubGridNodeModel`.
- **관계:** MapNode 1:N Resource, MapNode 1:N Echo (cascade delete).

---

## services/ - 비즈니스 로직

### services/\_\_init\_\_.py
- **목적:** services 패키지 초기화 (빈 파일)

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
