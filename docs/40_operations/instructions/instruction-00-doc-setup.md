# 구현 지시서 #00: 설계 문서 배치 + INDEX.md 업데이트

**대상**: Claude Code  
**우선순위**: 0/4 (가장 먼저, 다른 지시서의 전제 조건)  
**예상 결과**: 신규 설계 문서 3개 배치, INDEX.md 업데이트, 구현 지시서 4개 배치

---

## 1. 목표

이번 NPC 설계 세션에서 생성된 문서 3개와 구현 지시서 4개를 프로젝트에 배치하고, INDEX.md를 업데이트한다.

---

## 2. 설계 문서 배치

아래 3개 파일을 지정된 경로에 복사한다. 파일 내용은 이미 존재하므로 그대로 복사만 하면 된다.

| 원본 (유저가 제공) | 배치 경로 |
|---------------------|-----------|
| npc-system.md | `docs/20_design/npc-system.md` |
| overlay-layer-system.md | `docs/20_design/overlay-layer-system.md` |
| module-architecture.md | `docs/30_technical/module-architecture.md` |

```bash
# 유저가 파일을 프로젝트 루트에 두었다면:
cp npc-system.md docs/20_design/
cp overlay-layer-system.md docs/20_design/
cp module-architecture.md docs/30_technical/
```

**파일이 없으면 유저에게 경로를 확인할 것.**

---

## 3. 구현 지시서 배치

디렉토리 생성 후 지시서 4개를 배치한다.

```bash
mkdir -p docs/40_operations/instructions/
```

| 파일 | 배치 경로 |
|------|-----------|
| instruction-01-module-manager.md | `docs/40_operations/instructions/` |
| instruction-02-event-bus.md | `docs/40_operations/instructions/` |
| instruction-03-geography-module.md | `docs/40_operations/instructions/` |
| instruction-04-engine-integration.md | `docs/40_operations/instructions/` |

---

## 4. INDEX.md 업데이트

`docs/INDEX.md`에 아래 항목을 추가한다. 기존 내용은 수정하지 않고 **추가만** 한다.

### 4.1 `20_design/` 섹션에 추가 (기존 항목 뒤에)

```markdown
### npc-system.md
- **목적:** NPC 전체 생명주기 설계 (배경인물 → 승격 → NPC)
- **핵심:** 배경 존재 3유형(거주형/유랑형/적대형), 승격 점수제(임계값 50), HEXACO 성격(0.0~1.0), 3계층 기억(핵심/최근/아카이브), 공리 숙련도(level^2.2 곡선).
- **자율 행동:** Phase A(스케줄) → Phase B(욕구 7종) → Phase C(완전 자율).

### overlay-layer-system.md
- **목적:** 맵 오버레이 시스템 설계 ("퀘스트가 월드를 오염시키는 구조")
- **핵심:** L2 Weather, L3 Territory, L4 Quest, L5 Event 오버레이. severity(0.0~1.0) 기반 영향권 확장/축소. 우선순위 병합 + 충돌 시 창발적 효과.
- **상호작용:** 대화 태그 주입, 조우 확률 변경, 경제 수정자 적용.
```

### 4.2 `30_technical/` 섹션에 추가 (기존 항목 뒤에)

```markdown
### module-architecture.md
- **목적:** 모듈식 개발 구조 설계
- **핵심:** Layer 0(Core) → Layer 1(기반: geography, time, npc, item) → Layer 2(오버레이) → Layer 3(상호작용) → Layer 4(고급). GameModule ABC + ModuleManager로 모듈 토글.
- **원칙:** 모듈 격리, 명시적 의존성, EventBus 통신, 점진적 복잡도 증가.
```

### 4.3 `40_operations/` 섹션에 추가 (기존 항목 뒤에)

```markdown
### instructions/ (구현 지시서)
- **목적:** Claude Code용 단계별 구현 지시서
- **내용:**
  - #01: ModuleManager + GameModule ABC + GameContext
  - #02: EventBus 인프라
  - #03: geography 모듈 (기존 코드 래핑)
  - #04: engine.py 통합 (ModuleManager 연결)
```

### 4.4 `🔜 예정 문서` 섹션 업데이트

기존 예정 문서 목록에서 완료된 항목을 표시한다:

```markdown
### 🔜 예정 문서 (Phase 2)
- ~~npc-system.md: NPC 승격, HEXACO 성격, 기억 구조~~ → ✅ 완료
- relationship-system.md: 관계 축, 상태 전이
- quest-system.md: 퀘스트 자연발생, 연작 구조
- dialogue-system.md: AI 대화 컨텍스트, 이중 출력
- event-bus.md: 서비스 간 이벤트 통신 패턴
```

---

## 5. STATUS.md 업데이트

`docs/STATUS.md` (또는 프로젝트 루트의 STATUS.md)의 "설계 미완" 섹션에서 NPC 시스템을 "설계 완료"로 이동:

**"설계 완료 (문서 존재, 코드 미구현)" 섹션에 추가:**

```markdown
### NPC 시스템 (docs/20_design/npc-system.md)
- 배경 존재 3유형 (거주형/유랑형/적대형) - 미구현
- 승격 점수제 (임계값 50) - 미구현
- HEXACO 성격 (0.0~1.0) - 미구현
- 3계층 기억 (핵심/최근/아카이브) - 미구현
- 공리 숙련도 (level^2.2) - 미구현
- 자율 행동 (Phase A/B/C) - 미구현

### 오버레이 시스템 (docs/20_design/overlay-layer-system.md)
- Weather/Territory/Quest/Event 오버레이 - 미구현
- severity 기반 영향권 - 미구현
- 오버레이 병합/충돌 처리 - 미구현

### 모듈 아키텍처 (docs/30_technical/module-architecture.md)
- ModuleManager - 미구현
- GameModule ABC - 미구현
- EventBus - 미구현
- geography 모듈 - 미구현
```

**"설계 미완" 섹션에서 제거:**

```
- NPC 시스템 (npc-system.md 미작성) → 삭제 (작성 완료됨)
```

---

## 6. 검증

```bash
# 파일 존재 확인
ls docs/20_design/npc-system.md
ls docs/20_design/overlay-layer-system.md
ls docs/30_technical/module-architecture.md
ls docs/40_operations/instructions/instruction-01-module-manager.md
ls docs/40_operations/instructions/instruction-02-event-bus.md
ls docs/40_operations/instructions/instruction-03-geography-module.md
ls docs/40_operations/instructions/instruction-04-engine-integration.md

# INDEX.md에 새 항목 포함 확인
grep "npc-system" docs/INDEX.md
grep "overlay-layer-system" docs/INDEX.md
grep "module-architecture" docs/INDEX.md
grep "instructions" docs/INDEX.md
```

---

## 7. 체크리스트

- [ ] `docs/20_design/npc-system.md` 배치
- [ ] `docs/20_design/overlay-layer-system.md` 배치
- [ ] `docs/30_technical/module-architecture.md` 배치
- [ ] `docs/40_operations/instructions/` 디렉토리 생성
- [ ] 구현 지시서 4개 배치
- [ ] `docs/INDEX.md` 업데이트 (신규 3개 + 지시서 + 예정 문서 표시)
- [ ] STATUS.md 업데이트 (설계 완료로 이동)
- [ ] 커밋: `docs: add NPC system, overlay, module architecture designs + implementation instructions`

---

## 8. 주의사항

- 기존 INDEX.md 내용을 **삭제하지 않는다**. 추가만 한다.
- 설계 문서 내용을 수정하지 않는다. 있는 그대로 복사.
- 이 지시서 자체도 `docs/40_operations/instructions/`에 배치한다 (instruction-00-doc-setup.md).
