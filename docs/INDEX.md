# docs/ INDEX

## 10_product/ (WHY)

### requirements.md
- **목적:** 프로젝트 요구사항 정의
- **핵심:** ITW는 그래픽 없는 절차적 1인용 텍스트 TRPG 엔진. 절차적 월드 생성, Fog of War, Protocol T.A.G. 판정, Echo 메모리, 서브 그리드 맵이 핵심 기능.
- **비즈니스:** 엔진 라이선스($10-15) + BYOK 모델.

### roadmap.md
- **목적:** 개발 단계별 계획
- **핵심:** Phase 1(Core Engine, 현재) → Phase 2(AI+NPC) → Phase 3(컨텐츠 확장) → Phase 4(Release).
- **현황:** CI/CD 완료, 프로토타입 이식 완료. SQLite 영속화/통합 테스트/서브 그리드 진행 중.

### content-safety.md
- **목적:** 콘텐츠 안전 정책 (v0.3 초안)
- **핵심:** 페이드 아웃 정책 — 차단 아닌 묘사 생략 + 결과 전달. 세계 내 반응 원칙.
- **상태:** 아이디어 단계. SaaS 대비 고려사항, 소환 아이템 확장 아이디어 포함.

---

## 20_design/ (WHAT)

### axiom-system.md
- **목적:** 214 Divine Axioms 도메인 체계 정의
- **핵심:** 8개 도메인(Primordial, Material, Force, Organic, Mind, Logic, Social, Mystery)으로 구성.
- **상호작용:** 같은 Domain은 amplify(x1.1), 같은 Resonance는 resist(x0.8), 그 외 neutral(x1.0).

### nexus_and_travel_spec.md
- **목적:** Nexus(비동기 건설) 시스템과 Travel Montage(빠른 이동) 명세
- **핵심:** 유저가 구조물(SIGN, CACHE, SHELTER 등)을 건설하고, 구조물 5개+방문 100회 시 정착지로 진화.
- **이동:** 탐험 완료된 경로만 빠른 이동 가능. 1d100 Risk Roll로 성공/인카운터 결정.

### world-structure.md
- **목적:** 2단계 그리드 월드 구조 설계
- **핵심:** 메인 그리드(x,y, 4방향)와 서브 그리드(sx,sy,sz, 6방향)로 구성.
- **서브 유형:** 던전(하강), 탑(상승), 숲(수평 미로), 동굴(복합 3D).

### game-loop.md
- **목적:** 게임 루프 흐름 및 명령어 정의
- **핵심:** 입력 → 판정(Protocol T.A.G.) → 상태 변경 → 서술 생성 → 출력.
- **명령어:** look, move, investigate, harvest, rest, enter, exit, up, down.

### sub-grid.md
- **목적:** 서브 그리드 시스템 상세 설계
- **핵심:** 메인 노드 내부 확장 공간. 좌표는 (parent_x, parent_y, sx, sy, sz). 절차적 생성(시드 기반).
- **데이터:** SubGridNode 모델 정의. 층별 난이도 = depth_tier + abs(sz).

### resolution-system.md
- **목적:** Protocol T.A.G. 판정 시스템 설계
- **핵심:** 모든 판정을 d6 Dice Pool로 통일. 스탯(WRITE/READ/EXEC/SUDO) 기반 풀 구성.
- **결과:** Critical Success / Success / Failure / Critical Failure 4단계 판정.

### npc-system.md
- **목적:** NPC 전체 생명주기 설계 (배경인물 → 승격 → NPC)
- **핵심:** 배경 존재 3유형(거주형/유랑형/적대형), 승격 점수제(임계값 50), HEXACO 성격(0.0~1.0), 3계층 기억(핵심/최근/아카이브), 공리 숙련도(level^2.2 곡선).
- **자율 행동:** Phase A(스케줄) → Phase B(욕구 7종) → Phase C(완전 자율).

### overlay-layer-system.md
- **목적:** 맵 오버레이 시스템 설계 ("퀘스트가 월드를 오염시키는 구조")
- **핵심:** L2 Weather, L3 Territory, L4 Quest, L5 Event 오버레이. severity(0.0~1.0) 기반 영향권 확장/축소. 우선순위 병합 + 충돌 시 창발적 효과.
- **상호작용:** 대화 태그 주입, 조우 확률 변경, 경제 수정자 적용.

### relationship-system.md
- **목적:** PC-NPC 간, NPC-NPC 간 관계 시스템 설계
- **핵심:** 3축(affinity/trust/familiarity), 6단계 상태 전이(Stranger→Bonded, Rival→Nemesis), 반전 이벤트 3유형(betrayal/redemption/trust_collapse).
- **태도 태그:** Python 3단계 파이프라인 (관계 수치 → HEXACO 보정 → 기억 보정). LLM은 서술만.
- **감쇠:** affinity/trust 지수 1.2 감쇠, trust 하락은 감쇠 없음, familiarity 30일당 -1.

### quest-system.md (v1.1)
- **목적:** 퀘스트 발생, 체이닝, 판정, 보상 시스템 설계
- **핵심:** Python 선행 제어(5% 확률) + LLM 내용 생성 2단계 구조. Quest Seed로 떡밥 심기 → PC 선택권 → 수락 시 활성화.
- **체이닝:** 시드 티어 3단계(소60%/중30%/대10%), 시드 생성 시 DB 참조하여 연작 결정. chain_eligible_npcs(existing + unborn).
- **판정:** 수단의 자유 원칙. 공리 역학 활용이 전투 핵심. NPC 한줄평(impression_tag)이 태도 태그에 반영.
- **v1.1:** Objective 구조 재설계 — fetch 폐지→deliver 통합, escort 독립화, 목표 실패/대체 목표 생성, 전투 추상화.

### quest-action-integration.md (v1.1)
- **목적:** 퀘스트-액션 연동 설계 — Objective 달성/실패 판정, ObjectiveWatcher
- **핵심:** Python 판정(LLM 서술만), 분산 감지·중앙 발행 구조. 5종 Objective(reach_node/deliver/escort/talk_to_npc/resolve_check) 달성 조건 정의.
- **ObjectiveWatcher:** engine 내부 컴포넌트. player_moved, item_given, dialogue_started/ended, check_result 구독하여 목표 대조.
- **대체 목표:** 목표 실패 시 PC 선택지 제시, 의뢰주 보고 필수 포함.

### companion-system.md (v1.1)
- **목적:** 동행(Companion) 시스템 설계 — 퀘스트/자발적 동행, 라이프사이클, escort 연동
- **핵심:** 퀘스트 동행(escort 자동 요청) + 자발적 동행(recruit, 관계·성격 기반 수락), 1인 동행 제한(Alpha).
- **라이프사이클:** 요청→수락(무조건/조건부)→동행(이동 동기화, 대화)→해산(자동/수동).
- **해산 후 귀환:** 정주형(원래 위치), 구출 대상(의뢰인 위치), 방랑형(현재 잔류). Background Task 이동.

### dialogue-system.md
- **목적:** PC-NPC 대화 세션 관리, META JSON 통합, 행동 검증 시스템 설계
- **핵심:** 대화 세션 전체 = 게임 1턴. 예산제(관계/HEXACO/시드 기반) + 4단계 그라데이션 종료(open→winding→closing→final).
- **META JSON:** narrative + meta 이중 구조. dialogue_state, relationship_delta, memory_tags, quest_seed_response, action_interpretation, resolution_comment, npc_internal.
- **검증:** Constraints 항상 주입(퀘스트 무관) + Python 사후 검증(보정 우선, 재생성 최소화).

### item-system.md
- **목적:** 아이템 체계, 거래, 선물, 인벤토리, 내구도 시스템 설계
- **핵심:** Prototype(불변) + Instance(가변) 분리, axiom_tags 매핑, bulk 기반 인벤토리(50+EXEC 보정), 4종 분류(EQUIPMENT/CONSUMABLE/MATERIAL/MISC).
- **거래:** 관계/HEXACO H 보정 거래가, A(관용성) 기반 흥정 3단계(accept/counter/reject), browse→거래대화 자동진입.
- **확장:** PrototypeRegistry 동적 등록, 초기 43종 → 수천 종 스케일.

---

## 30_technical/ (HOW)

### architecture.md
- **목적:** 시스템 레이어 아키텍처 정의
- **핵심:** API → Service → Core → DB 4계층 구조.
- **규칙:** Core는 DB를 모름, Service가 Core와 DB를 연결, API는 Service만 호출.

### api-spec.md
- **목적:** Game API 엔드포인트 명세
- **핵심:** POST /game/register(등록), GET /game/state/{id}(상태조회), POST /game/action(액션 실행).
- **액션:** look, move, rest, investigate, harvest 지원. 에러코드 200/400/404/500.

### ai-provider.md
- **목적:** AI Provider 추상화 레이어 설계
- **핵심:** AIProvider 인터페이스로 여러 LLM(mock, gemini, openai, anthropic, ollama) 교체 가능.
- **Fallback:** API 키 없음/에러/Provider 없음 시 모두 MockProvider로 대체.

### narrative-service.md
- **목적:** AI 기반 게임 서술 생성 서비스 설계
- **핵심:** NarrativeService가 AIProvider를 사용해 look/move 서술 생성.
- **Fallback:** AI 사용 불가/API 에러/예외 시 기본 템플릿 서술 제공.

### world-layer-system.md
- **목적:** 4-Layer Geography 시스템 통합 설계
- **핵심:** L0(Biome) → L1(Infrastructure) → L2(Facility) → L3(Depth) 레이어 구조.
- **우선순위:** L3 서브 그리드(MVP) → L0 Biome → L1 Infrastructure → L2 Facility.

### db-schema.md
- **목적:** SQLite DB 스키마 정의
- **핵심:** map_nodes(좌표/tier/axiom/sensory) + players(위치/상태) 테이블. 레이어별 필드 추가 예정.
- **신규:** biomes 테이블 추가 예정(id, name_kr, base_tags, weather_interpretation).

### db-schema-v2.md
- **목적:** Phase 2 통합 DB 스키마 (NPC/관계/퀘스트/대화/아이템)
- **핵심:** 기존 v1 유지 + 16개 신규 테이블. models_v2.py 단일 파일 구성. JSON 필드 활용.
- **마이그레이션:** 의존 순서 5단계 생성. 운영 DB 발생 시 Alembic 도입 예정.
- **구현:** models_v2.py 완료 (Mapped 스타일, main.py에서 자동 등록)

### module-architecture.md
- **목적:** 모듈식 개발 구조 설계
- **핵심:** Layer 0(Core) → Layer 1(기반: geography, time, npc, item) → Layer 2(오버레이) → Layer 3(상호작용) → Layer 4(고급). GameModule ABC + ModuleManager로 모듈 토글.
- **원칙:** 모듈 격리, 명시적 의존성, EventBus 통신, 점진적 복잡도 증가.

### event-bus.md (v1.1)
- **목적:** EventBus 이벤트 통합 설계 — 전체 이벤트 카탈로그, 구독 매트릭스, 순환 분석
- **핵심:** 모듈/서비스 간 동기식 이벤트 통신. 이벤트 카탈로그 9그룹, 구독 매트릭스, 페이로드 스키마.
- **v1.1:** 이벤트 7종 추가(player_moved, action_completed, item_given, objective_failed, companion_joined/moved/disbanded), ObjectiveWatcher + companion 구독 반영, 모듈 초기화 순서 갱신.

### simulation-scope.md
- **목적:** NPC 시뮬레이션 범위와 Zone 밖 NPC 처리 규칙 정의
- **핵심:** Active Zone(PC 중심 5×5, active_radius 설정 가능) 풀 시뮬레이션. Background Zone은 상태만 추적.
- **Zone 밖 NPC:** event_bound(백그라운드 처리 유지) vs desire_wandered(유예 턴 후 귀환). PC 접근 시 즉시 활성화.
- **연산:** Python+DB ~8ms/턴, LLM 1~3초. 병목은 항상 LLM.

---

## 40_operations/ (RUN)

### ci-cd.md
- **목적:** CI/CD 파이프라인 정의
- **핵심:** GitHub Actions로 push/PR to main 시 ruff check → pytest 자동 실행.
- **로컬:** 커밋 전 `ruff check src/ tests/` + `pytest -v` 수동 실행.

### instructions/ (구현 지시서)
- **목적:** Claude Code용 단계별 구현 지시서
- **내용:**
  - #00: 문서 세팅
  - #01: ModuleManager + GameModule ABC + GameContext
  - #02: EventBus 인프라
  - #03: geography 모듈 (기존 코드 래핑)
  - #04: engine.py 통합 (ModuleManager 연결)
  - #05: 설계 문서 배치
  - #06: 아이템/대화 문서 배치 + META 갱신
  - #07: models_v2.py (Phase 2 DB 스키마 ORM)
  - #08: NPC 모듈 (5블록 — Core/승격/기억/Service/Module)

---

### 예정 문서 (Phase 2)
- ~~npc-system.md~~ → ✅ 설계 완료 + 코드 구현 (#08)
- ~~relationship-system.md~~ → ✅ 설계 완료 (코드 미구현)
- ~~quest-system.md~~ → ✅ 설계 완료 v1.1 (코드 미구현)
- ~~quest-action-integration.md~~ → ✅ 설계 완료 v1.1 (코드 미구현)
- ~~companion-system.md~~ → ✅ 설계 완료 v1.1 (코드 미구현)
- ~~dialogue-system.md~~ → ✅ 설계 완료 (코드 미구현)
- ~~event-bus.md~~ → ✅ 설계 완료 v1.1 (코드 존재, event_types.py 부분 구현)
- ~~item-system.md~~ → ✅ 설계 완료 (코드 미구현)
- ~~db-schema-v2.md~~ → ✅ 설계 완료 + 코드 구현 (#07)
- ~~content-safety.md~~ → 초안 v0.3 (아이디어 단계)
