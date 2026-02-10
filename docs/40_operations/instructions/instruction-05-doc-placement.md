# 구현 지시서 #05: 설계 문서 배치 및 인덱스 갱신

**유형**: 파일 배치 (코딩 없음)
**난이도**: 낮음
**예상 시간**: 5분

---

## 목적

미배치된 설계 문서 4건을 프로젝트에 배치하고, INDEX.md와 STATUS.md를 갱신한다.

## 사전 준비

1. `docs/INDEX.md` 읽기 — 현재 문서 구조 확인
2. `docs/20_design/` 디렉토리 확인 — 기존 파일 목록
3. `docs/30_technical/` 디렉토리 확인 — 기존 파일 목록

---

## 작업 순서

### 커밋 1: 이전 세션 설계 문서 배치

**파일 배치:**
- `relationship-system.md` → `docs/20_design/relationship-system.md`
- `simulation-scope.md` → `docs/30_technical/simulation-scope.md`

**파일 소스:** 이 지시서와 같은 디렉토리에 첨부된 파일을 사용한다.
만약 첨부되지 않았다면 유저에게 파일 위치를 확인한다.

```bash
git add docs/20_design/relationship-system.md docs/30_technical/simulation-scope.md
git commit -m "docs: add relationship-system and simulation-scope design docs"
git push
```

### 커밋 2: 퀘스트 시스템 설계 문서 배치

**파일 배치:**
- `quest-system.md` → `docs/20_design/quest-system.md`

```bash
git add docs/20_design/quest-system.md
git commit -m "docs: add quest-system design doc"
git push
```

### 커밋 3: 대화 시스템 설계 문서 배치

**파일 배치:**
- `dialogue-system.md` → `docs/20_design/dialogue-system.md`

```bash
git add docs/20_design/dialogue-system.md
git commit -m "docs: add dialogue-system design doc"
git push
```

### 커밋 4: INDEX.md + STATUS.md 갱신

**파일 교체:**
- `INDEX.md` → `docs/INDEX.md`
- `STATUS.md` → `docs/STATUS.md` (또는 프로젝트 루트, 현재 위치에 따라)

**INDEX.md 변경 내용:**
- `20_design/` 섹션에 추가: relationship-system.md, quest-system.md, dialogue-system.md
- `30_technical/` 섹션에 추가: simulation-scope.md
- 하단 예정 문서: relationship/quest/dialogue에 ✅ 완료 표시
- 예정 문서에 item-system.md, db-schema-v2.md 추가

**STATUS.md 변경 내용:**
- "설계 완료" 섹션에 관계/퀘스트/대화/시뮬레이션 범위 추가
- "설계 미완" 섹션 갱신 (relationship/quest/dialogue 제거, item/db-schema-v2/event-bus 남김)
- "다음 작업 후보" 갱신
- 자동 생성일 갱신: 2026-02-10

```bash
git add docs/INDEX.md docs/STATUS.md
git commit -m "docs: update INDEX and STATUS with new design docs"
git push
```

---

## 검증

각 커밋 후:
1. 파일이 올바른 경로에 존재하는지 `ls` 로 확인
2. 마지막 커밋 후 `git log --oneline -5` 로 커밋 이력 확인

---

## 주의사항

- **코딩 작업 없음** — 파일 복사와 git 커밋만 수행
- STATUS.md의 위치가 프로젝트 루트인지 docs/ 안인지 확인 후 배치
- 기존 파일을 덮어쓰지 않도록 주의 (INDEX.md, STATUS.md는 의도적 교체)
