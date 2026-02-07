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

### module-architecture.md
- **목적:** 모듈식 개발 구조 설계
- **핵심:** Layer 0(Core) → Layer 1(기반: geography, time, npc, item) → Layer 2(오버레이) → Layer 3(상호작용) → Layer 4(고급). GameModule ABC + ModuleManager로 모듈 토글.
- **원칙:** 모듈 격리, 명시적 의존성, EventBus 통신, 점진적 복잡도 증가.

---

## 40_operations/ (RUN)

### ci-cd.md
- **목적:** CI/CD 파이프라인 정의
- **핵심:** GitHub Actions로 push/PR to main 시 ruff check → pytest 자동 실행.
- **로컬:** 커밋 전 `ruff check src/ tests/` + `pytest -v` 수동 실행.

### instructions/ (구현 지시서)
- **목적:** Claude Code용 단계별 구현 지시서
- **내용:**
  - #01: ModuleManager + GameModule ABC + GameContext
  - #02: EventBus 인프라
  - #03: geography 모듈 (기존 코드 래핑)
  - #04: engine.py 통합 (ModuleManager 연결)

---

### 🔜 예정 문서 (Phase 2)
- ~~npc-system.md: NPC 승격, HEXACO 성격, 기억 구조~~ → ✅ 완료
- relationship-system.md: 관계 축, 상태 전이
- quest-system.md: 퀘스트 자연발생, 연작 구조
- dialogue-system.md: AI 대화 컨텍스트, 이중 출력
- event-bus.md: 서비스 간 이벤트 통신 패턴