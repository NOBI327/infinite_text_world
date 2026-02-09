# ITW 프로젝트 현재 상태
자동 생성일: 2026-02-10

## 구현 완료 (코드 존재)

### Core (src/core/)
- **axiom_system.py** (390줄): 214 Divine Axioms 로더, AxiomVector 태그 벡터, 8개 Domain/Resonance 분류
- **world_generator.py** (661줄): 무한 좌표 절차적 월드 생성, 희귀도 분포(94/5/1%), 클러스터 상속, 감각/자원 생성
- **navigator.py** (680줄): 4방향+상하 이동, Supply 소모, Fog of War(좌표 해시), 서브 그리드 내 이동
- **sub_grid.py** (386줄): L3 Depth 서브 그리드 생성 (Dungeon/Tower/Forest/Cave), 깊이별 난이도
- **echo_system.py** (556줄): 8 카테고리 Echo 생성, d6 Dice Pool 조사 판정, 시간 경과 소멸
- **core_rule.py** (315줄): Protocol T.A.G. 판정 엔진, d6 Dice Pool, CharacterSheet(WRITE/READ/EXEC/SUDO)
- **engine.py** (1250줄): 메인 엔진, 모든 하위 시스템 통합, 게임 액션(look/move/investigate/harvest/rest/enter/exit), DB 저장/로드
- **logging.py**: 프로젝트 공용 로깅

### API (src/api/)
- **game.py** (261줄): POST /game/register, GET /game/state/{id}, POST /game/action (look/move/rest/investigate/harvest/enter/exit)
- **schemas.py** (91줄): 요청/응답 Pydantic 스키마
- **health.py**: GET /health 헬스체크

### Services (src/services/)
- **narrative_service.py** (147줄): AI 기반 서술 생성, AI 불가 시 템플릿 fallback
- **ai/base.py**: AIProvider 추상 인터페이스
- **ai/mock.py**: Mock AI Provider (테스트/fallback)
- **ai/gemini.py**: Google Gemini API Provider
- **ai/factory.py**: Provider 팩토리 (config 기반 선택)

### DB (src/db/)
- **models.py** (137줄): MapNodeModel, ResourceModel, EchoModel, PlayerModel, SubGridNodeModel
- **database.py**: SQLAlchemy 엔진/세션 팩토리

### Data (src/data/)
- **itw_214_divine_axioms.json**: 214개 공리 마스터 데이터

### Infra
- **main.py**: FastAPI 엔트리포인트, lifespan에서 DB/Engine/AI 초기화
- **config.py**: pydantic-settings 기반 환경 설정

### Tests (tests/)
- 168개 테스트 전체 통과
- 전체 커버리지: **77%**
- 파일별 커버리지:
  - schemas.py: 100%, db/models.py: 100%, config.py: 100%, logging.py: 100%
  - sub_grid.py: 96%, narrative_service.py: 93%, ai/factory.py: 90%
  - game.py: 87%, world_generator.py: 84%, health.py: 83%
  - navigator.py: 78%, core_rule.py: 71%, axiom_system.py: 66%
  - engine.py: 65%, echo_system.py: 68%, main.py: 55%

## 설계 완료 (문서 존재, 코드 미구현)

### NPC 시스템 (docs/20_design/npc-system.md)
- 배경 존재 3유형 (거주형/유랑형/적대형) - 미구현
- 승격 점수제 (임계값 50) - 미구현
- HEXACO 성격 (0.0~1.0) - 미구현
- 3계층 기억 (핵심/최근/아카이브) - 미구현
- 공리 숙련도 (level^2.2) - 미구현
- 자율 행동 (Phase A/B/C) - 미구현

### 관계 시스템 (docs/20_design/relationship-system.md)
- 3축 관계 (affinity/trust/familiarity) - 미구현
- 6단계 상태 전이 (Stranger~Bonded, Rival~Nemesis) - 미구현
- 반전 이벤트 3유형 (betrayal/redemption/trust_collapse) - 미구현
- Python 3단계 태도 태그 파이프라인 - 미구현
- 감쇠 곡선 (지수 1.2, trust 비대칭) - 미구현

### 퀘스트 시스템 (docs/20_design/quest-system.md)
- Quest Seed 메커니즘 (5% 확률, TTL, 4유형) - 미구현
- 시드 티어 3단계 (소60%/중30%/대10%) - 미구현
- 체이닝 구조 (chain_eligible_npcs, unresolved_threads) - 미구현
- 수단의 자유 + 공리 역학 판정 - 미구현
- NPC 한줄평 (resolution_comment, impression_tag) - 미구현
- L4 Quest 오버레이 자동 생성/제거 - 미구현
- PC 경향 (pc_tendency) 산출 - 미구현

### 대화 시스템 (docs/20_design/dialogue-system.md)
- 대화 세션 관리 (세션 = 게임 1턴) - 미구현
- 예산제 대화 (관계/HEXACO/시드 기반 budget) - 미구현
- 4단계 그라데이션 종료 (open→winding→closing→final) - 미구현
- META JSON 통합 형식 (서술 + meta 이중 구조) - 미구현
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

### DB 스키마 확장 (docs/30_technical/db-schema.md)
- biomes 테이블 - 미구현
- 레이어별 필드 추가 - 미구현

### 모듈 아키텍처 (docs/30_technical/module-architecture.md)
- ModuleManager - 미구현
- GameModule ABC - 미구현
- EventBus - 미구현
- geography 모듈 - 미구현

## 설계 미완 (로드맵/요구사항에 있지만 설계 문서 없음)

### Phase 2 잔여 (설계 필요)
- ~~item-system.md: 아이템 체계, 거래, 퀘스트 보상~~ → ✅ 설계 완료
- db-schema-v2.md: NPC/관계/퀘스트/대화 통합 스키마
- event-bus.md: 서비스 간 이벤트 통신 패턴 상세

### Phase 3 예정 (docs/10_product/roadmap.md)
- 던전 시스템 (서브 그리드 기반 확장)
- NPC 상호작용
- 아이템 시스템

### Phase 4 예정
- 배포 및 문서화

## 아키텍처 현황

- **레이어 구조**: API → Service → Core → DB (docs/30_technical/architecture.md 정의대로)
- **서비스 간 직접 호출**: 없음 (narrative_service는 ai 모듈 내부만 참조)
- **이벤트버스**: 미구현 (Phase 2에서 NPC 시스템과 동시 도입 예정)
- **모듈 매니저**: 미구현 (설계 문서 존재: docs/30_technical/module-architecture.md)
- **SQLite 영속화**: 부분 구현 (engine.py에 save/load_world_to_db, save/load_players_to_db 존재)
- **CI/CD**: 구현 완료 (GitHub Actions, ruff + pytest)

## 로드맵 대비 현황 (Phase 1)

| 항목 | 상태 |
|------|------|
| CI/CD 파이프라인 | 완료 |
| 프로토타입 이식 | 완료 |
| SQLite 영속화 | 부분 구현 (save/load 메서드 존재, 통합 흐름 미완) |
| 통합 테스트 | 부분 (test_persistence.py 존재, 168개 테스트 통과) |
| 서브 그리드 맵 시스템 | 완료 (sub_grid.py + test_sub_grid.py) |

## 다음 작업 후보

### 설계 (다음 작성 대상)
1. ~~**item-system.md**: 아이템 체계, 거래, 퀘스트 보상~~ → ✅ 완료
2. **db-schema-v2.md**: quest/dialogue/relationship/item 확정 후 통합 스키마
3. **event-bus.md**: 서비스 간 이벤트 통신 패턴 상세 (각 모듈 EventBus 인터페이스를 통합 정리)

### 구현 (설계 완료 후)
1. **구현 지시서 #01**: ModuleManager + GameModule ABC + GameContext
2. **구현 지시서 #02**: EventBus 인프라
3. **구현 지시서 #03**: geography 모듈 (기존 코드 래핑)
4. **구현 지시서 #04**: engine.py 통합 (ModuleManager 연결)
5. **Phase 1 잔여**: SQLite 영속화 통합 흐름 완성
6. **커버리지 향상**: engine.py(65%), echo_system.py(68%), axiom_system.py(66%) 테스트 보강
