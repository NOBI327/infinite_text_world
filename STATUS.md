# ITW 프로젝트 현재 상태
자동 생성일: 2026-02-12

## 구현 완료 (코드 존재)

### Core (src/core/)
- **axiom_system.py** (390줄): 214 Divine Axioms 로더, AxiomVector 태그 벡터, 8개 Domain/Resonance 분류
- **world_generator.py** (661줄): 무한 좌표 절차적 월드 생성, 희귀도 분포(94/5/1%), 클러스터 상속, 감각/자원 생성
- **navigator.py** (680줄): 4방향+상하 이동, Supply 소모, Fog of War(좌표 해시), 서브 그리드 내 이동
- **sub_grid.py** (386줄): L3 Depth 서브 그리드 생성 (Dungeon/Tower/Forest/Cave), 깊이별 난이도
- **echo_system.py** (556줄): 8 카테고리 Echo 생성, d6 Dice Pool 조사 판정, 시간 경과 소멸
- **core_rule.py** (315줄): Protocol T.A.G. 판정 엔진, d6 Dice Pool, CharacterSheet(WRITE/READ/EXEC/SUDO)
- **engine.py** (1324줄): 메인 엔진, 모든 하위 시스템 통합, ModuleManager 연결, 게임 액션(look/move/investigate/harvest/rest/enter/exit), DB 저장/로드
- **event_bus.py** (136줄): 동기식 EventBus, 전파 깊이 제한(MAX_DEPTH=5), 동일 source:event_type 중복 차단
- **event_types.py**: NPC 관련 이벤트 상수 (NPC_PROMOTED, NPC_CREATED, NPC_DIED, NPC_MOVED, NPC_NEEDED, TURN_PROCESSED)
- **logging.py**: 프로젝트 공용 로깅

### Core/NPC (src/core/npc/) — 지시서 #08-A~C 구현
- **models.py**: NPC 도메인 모델 (EntityType, BackgroundEntity, BackgroundSlot, HEXACO, NPCData)
- **hexaco.py**: HEXACO 성격 생성 (7종 역할 템플릿, ±0.15 랜덤, 행동 수정자 매핑)
- **tone.py**: 톤 태그 생성 (HEXACO → manner_tags, 감정 계산)
- **slots.py**: 시설 슬롯 관리 (7종 시설 기본 슬롯, 리셋 규칙)
- **promotion.py**: 승격 시스템 (10종 행동 점수, 임계값 50/15, 엔티티→NPC 순수 변환)
- **naming.py**: NPC 명명 (이름 풀 기반 시드 생성)
- **memory.py**: 기억 시스템 (Tier 1 고정2+교체3, Tier 2 관계별 용량, 컨텍스트 선택)

### Modules (src/modules/)
- **base.py** (97줄): GameModule ABC, GameContext, Action 데이터 클래스
- **module_manager.py** (126줄): 모듈 등록/활성화/비활성화, 의존성 검증, cascade 비활성화, EventBus 소유, 턴/노드진입 전파
- **geography/module.py** (215줄): WorldGenerator/Navigator/SubGridGenerator 래핑, context.extra에 지리 정보 저장, 이동/depth 액션 제공
- **npc/module.py**: NPCCoreModule — NPCService 래핑, npc_needed 이벤트 구독, 노드 진입 시 context.extra["npc_core"] 저장, 공개 조회 API

### API (src/api/)
- **game.py** (261줄): POST /game/register, GET /game/state/{id}, POST /game/action (look/move/rest/investigate/harvest/enter/exit)
- **schemas.py** (91줄): 요청/응답 Pydantic 스키마
- **health.py**: GET /health 헬스체크

### Services (src/services/)
- **npc_service.py** (404줄): NPC CRUD, 승격 흐름(점수→WorldPool→승격), 기억 관리(Tier 1/2), ORM↔Core 변환, EventBus 이벤트 발행 — 지시서 #08-D 구현
- **narrative_service.py** (147줄): AI 기반 서술 생성, AI 불가 시 템플릿 fallback
- **ai/base.py**: AIProvider 추상 인터페이스
- **ai/mock.py**: Mock AI Provider (테스트/fallback)
- **ai/gemini.py**: Google Gemini API Provider
- **ai/factory.py**: Provider 팩토리 (config 기반 선택)

### DB (src/db/)
- **models.py** (138줄): v1 ORM — MapNodeModel, ResourceModel, EchoModel, PlayerModel, SubGridNodeModel (Mapped 스타일)
- **models_v2.py** (506줄): v2 ORM — 16개 테이블 (NPC/관계/퀘스트/대화/아이템). Mapped[T] + mapped_column() 스타일 (models.py와 일관)
- **database.py**: SQLAlchemy 엔진/세션 팩토리

### Data (src/data/)
- **itw_214_divine_axioms.json**: 214개 공리 마스터 데이터

### Infra
- **main.py**: FastAPI 엔트리포인트, lifespan에서 DB/Engine/AI 초기화, models_v2 import로 Phase 2 테이블 자동 등록
- **config.py**: pydantic-settings 기반 환경 설정

### Tests (tests/)
- **342개 테스트** 전체 통과
- 전체 커버리지: **83%**
- 파일별 커버리지:
  - 100%: modules/base.py, module_manager.py, event_types.py, npc models/memory/promotion/slots, models_v2.py, models.py, schemas.py, config.py, logging.py, database.py
  - 90%+: geography/module.py(96%), sub_grid.py(96%), narrative_service.py(93%), npc_service.py(91%), ai/factory.py(90%), naming.py(89%)
  - 80%+: game.py(87%), world_generator.py(86%), health.py(83%)
  - 70%+: hexaco.py(79%), navigator.py(78%), core_rule.py(71%)
  - ~70%: engine.py(69%), echo_system.py(68%), npc/module.py(68%), npc/tone.py(68%), axiom_system.py(66%), gemini.py(67%)
  - main.py(56%)

## 설계 완료 (문서 존재, 코드 미구현)

### NPC 시스템 — 잔여 미구현 항목
- 공리 숙련도 (level^2.2) - 미구현
- 자율 행동 Phase A/B/C (스케줄/욕구/완전 자율) - 미구현
- NPC 상호작용 (대화 연동) - 미구현

### 관계 시스템 (docs/20_design/relationship-system.md)
- 3축 관계 (affinity/trust/familiarity) - 미구현
- 6단계 상태 전이 (Stranger~Bonded, Rival~Nemesis) - 미구현
- 반전 이벤트 3유형 (betrayal/redemption/trust_collapse) - 미구현
- Python 3단계 태도 태그 파이프라인 - 미구현
- 감쇠 곡선 (지수 1.2, trust 비대칭) - 미구현

### 퀘스트 시스템 (docs/20_design/quest-system.md v1.1)
- Quest Seed 메커니즘 (5% 확률, TTL, 4유형) - 미구현
- 시드 티어 3단계 (소60%/중30%/대10%) - 미구현
- 체이닝 구조 (chain_eligible_npcs, unresolved_threads) - 미구현
- 수단의 자유 + 공리 역학 판정 - 미구현
- NPC 한줄평 (resolution_comment, impression_tag) - 미구현
- L4 Quest 오버레이 자동 생성/제거 - 미구현
- PC 경향 (pc_tendency) 산출 - 미구현
- **v1.1 추가**: Objective 구조 재설계 (fetch→deliver 통합, escort 독립, 목표 실패/대체 목표) - 미구현

### 퀘스트-액션 연동 (docs/20_design/quest-action-integration.md v1.1)
- ObjectiveWatcher: 5종 Objective(reach_node/deliver/escort/talk_to_npc/resolve_check) 달성/실패 판정 - 미구현
- 신규 액션 연동 (talk, give, use) - 미구현
- 대화 중 목표 달성 → LLM 컨텍스트 반영 - 미구현
- 대체 목표 생성 + 의뢰주 보고 필수 선택지 - 미구현

### 동행 시스템 (docs/20_design/companion-system.md v1.1)
- 퀘스트 동행 / 자발적 동행 2유형 - 미구현
- 라이프사이클 (요청→수락→동행→해산) - 미구현
- escort/rescue 퀘스트 연동 - 미구현
- 이동 동기화 (player_moved 구독) - 미구현
- 해산 후 NPC 귀환 행동 (정주형/구출대상/방랑형) - 미구현
- 조건부 동행 (time_limit, destination_only 등) - 미구현

### 대화 시스템 (docs/20_design/dialogue-system.md)
- 대화 세션 관리 (세션 = 게임 1턴) - 미구현
- 예산제 대화 (관계/HEXACO/시드 기반 budget) - 미구현
- 4단계 그라데이션 종료 (open→winding→closing→final) - 미구현
- META JSON 통합 형식 (서술 + meta 이중 구조, trade_request/gift_offered 포함) - 미구현
- Constraints 주입 + Python 사후 검증 파이프라인 - 미구현
- LLM 프롬프트 계층 구조 - 미구현

### 아이템 시스템 (docs/20_design/item-system.md)
- Prototype(불변) + Instance(가변) 분리 구조 - 미구현
- PrototypeRegistry 동적 등록 - 미구현
- axiom_tags 매핑 테이블 - 미구현
- bulk 기반 인벤토리 (50+EXEC 보정) - 미구현
- 4종 분류 (EQUIPMENT/CONSUMABLE/MATERIAL/MISC) - 미구현
- 거래 시스템 (관계/HEXACO H 보정 거래가, 흥정 3단계) - 미구현
- 선물 시스템 (calculate_gift_affinity) - 미구현
- 내구도 시스템 (파괴 → 변환/소멸) - 미구현
- 점포 구조 (container 체이닝, 임시 자동 보충) - 미구현

### 오버레이 시스템 (docs/20_design/overlay-layer-system.md)
- Weather/Territory/Quest/Event 오버레이 - 미구현
- severity 기반 영향권 - 미구현
- 오버레이 병합/충돌 처리 - 미구현

### 시뮬레이션 범위 (docs/30_technical/simulation-scope.md)
- Active Zone 5×5 (active_radius 설정 가능) - 미구현
- Background Zone 처리 (상태 추적, 시간 감쇠) - 미구현
- Zone 전환 처리 (진입/이탈) - 미구현
- BackgroundTask (event_bound/desire_wandered) - 미구현

### Nexus System & Travel Montage (docs/20_design/nexus_and_travel_spec.md)
- 구조물 건설 (SIGN, CACHE, SHELTER 등) - MapStructure 테이블 미구현
- 정착지 진화 (visit_count + structure_score 임계치) - 미구현
- 빠른 이동 (Travel Montage, 1d100 Risk Roll) - 미구현
- MapNode 확장 필드 (visit_count, danger_rating, is_settlement, environment_log) - 미구현

### World Layer System L0~L2 (docs/30_technical/world-layer-system.md)
- L0 Biome (biome_tags, weather_interpretation) - 미구현
- L1 Infrastructure (Road, Bridge, Tunnel, infrastructure_health) - 미구현
- L2 Facility (Mine, Inn, Farm, owner_id) - 미구현
- L3 Depth - **구현 완료** (sub_grid.py)

### DB 스키마 v1 확장 (docs/30_technical/db-schema.md)
- biomes 테이블 - 미구현
- 레이어별 필드 추가 - 미구현

### EventBus 통합 (docs/30_technical/event-bus.md v1.1)
- 이벤트 7종 추가 (player_moved, action_completed, item_given, objective_failed, companion_joined/moved/disbanded) - 설계 완료, event_types.py 미반영
- 구독 매트릭스 갱신 (ObjectiveWatcher + companion) - 설계 완료
- 모듈 초기화 순서 갱신 (companion → quest) - 설계 완료

### 콘텐츠 안전 정책 (docs/10_product/content-safety.md v0.3 초안)
- 페이드 아웃 정책 (차단 아닌 묘사 생략 + 결과 전달) - 아이디어 단계
- SaaS 대비 고려사항 - 메모
- 소환 아이템 확장 아이디어 - 메모

## 설계 미완 (로드맵/요구사항에 있지만 설계 문서 없음)

### Phase 3 예정 (docs/10_product/roadmap.md)
- 던전 시스템 (서브 그리드 기반 확장)
- NPC 상호작용
- 아이템 시스템

### Phase 4 예정
- 배포 및 문서화

## 아키텍처 현황

- **레이어 구조**: API → Service → Core → DB (docs/30_technical/architecture.md 정의대로)
- **모듈 시스템**: **구현 완료** (GameModule ABC + ModuleManager + geography 모듈 + npc 모듈)
- **이벤트버스**: **구현 완료** (src/core/event_bus.py, 깊이 제한 5, 중복 차단, ModuleManager 연동)
- **EventTypes**: **구현 완료** (src/core/event_types.py — NPC 이벤트 6종)
- **서비스 간 직접 호출**: 없음 (narrative_service는 ai 모듈 내부만 참조, 모듈 간 통신은 EventBus 경유)
- **SQLite 영속화**: 부분 구현 (engine.py에 save/load_world_to_db, save/load_players_to_db 존재)
- **DB v2**: **구현 완료** (models_v2.py — 16개 테이블, Mapped 스타일, main.py에서 자동 등록)
- **CI/CD**: 구현 완료 (GitHub Actions, ruff + ruff-format + pytest + mypy)

## 로드맵 대비 현황

| 항목 | 상태 |
|------|------|
| CI/CD 파이프라인 | 완료 (ruff + ruff-format + pytest + mypy) |
| 프로토타입 이식 | 완료 |
| SQLite 영속화 | 부분 구현 (save/load 메서드 존재, 통합 흐름 미완) |
| 통합 테스트 | 완료 (342개 테스트 통과, 커버리지 83%) |
| 서브 그리드 맵 시스템 | 완료 (sub_grid.py + test_sub_grid.py) |
| 모듈 시스템 인프라 | 완료 (지시서 #01~#04 완료) |
| DB 스키마 v2 | 완료 (지시서 #07 — models_v2.py 16개 테이블) |
| NPC Core + Service + Module | 완료 (지시서 #08-A~E — 도메인 모델, HEXACO, 톤, 슬롯, 승격, 명명, 기억, Service, Module) |

## 다음 작업 후보

### 구현 지시서 실행 이력
- ~~#00: 문서 세팅~~ → 완료
- ~~#01: ModuleManager + GameModule ABC + GameContext~~ → 완료
- ~~#02: EventBus 인프라~~ → 완료
- ~~#03: geography 모듈~~ → 완료
- ~~#04: engine.py 통합~~ → 완료
- ~~#05: 설계 문서 배치~~ → 완료
- ~~#06: 아이템/대화 문서 배치 + META 갱신~~ → 완료
- ~~#07: models_v2.py (Phase 2 DB)~~ → 완료
- ~~#08: NPC 모듈 (5블록)~~ → 완료

### Phase 2 다음 단계
1. **관계 시스템 구현**: relationship-system.md 기반 — 3축 관계, 상태 전이, 감쇠
2. **대화 시스템 구현**: dialogue-system.md 기반 — 세션 관리, META JSON, 예산제
3. **퀘스트 시스템 구현**: quest-system.md v1.1 기반 — Seed, 체이닝, 판정, Objective 재설계
4. **퀘스트-액션 연동 구현**: quest-action-integration.md 기반 — ObjectiveWatcher, 달성/실패 판정
5. **동행 시스템 구현**: companion-system.md 기반 — 동행 라이프사이클, escort 연동
6. **아이템 시스템 구현**: item-system.md 기반 — Prototype/Instance, 거래, 인벤토리

### 소규모 갱신 필요
1. **dialogue-system.md**: dialogue_started 페이로드에 companion_npc_id 선택 키 추가
2. **db-schema.md**: quest_objectives 필드 갱신, companions 테이블 추가
3. **event_types.py**: 신규 이벤트 7종 상수 추가 (event-bus.md v1.1 반영)

### 기타
1. **커버리지 향상**: engine.py(69%), echo_system.py(68%), axiom_system.py(66%) 테스트 보강
2. **Phase 1 잔여**: SQLite 영속화 통합 흐름 완성
