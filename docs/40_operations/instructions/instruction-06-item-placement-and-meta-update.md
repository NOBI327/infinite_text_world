# 구현 지시서 #05: item-system 배치 + dialogue META 갱신 + INDEX 갱신

**목적**: 미처리 사항 3건 일괄 정리  
**난이도**: 낮음 (파일 배치 + 텍스트 편집)  
**예상 시간**: 10분  
**커밋 수**: 2

---

## 사전 확인

```bash
# 현재 상태 확인
cat docs/INDEX.md | head -5
ls docs/20_design/
```

---

## 커밋 1: item-system.md 배치

### 1-1. 파일 배치

item-system.md를 `docs/20_design/item-system.md`에 배치한다.

```bash
cp item-system.md docs/20_design/item-system.md
```

> 파일은 프로젝트 루트 또는 유저가 지정한 경로에 있다. 없으면 유저에게 경로를 확인하라.

### 1-2. 커밋

```bash
git add docs/20_design/item-system.md
git commit -m "docs: item-system.md 배치 (docs/20_design/)"
```

---

## 커밋 2: dialogue-system.md META 갱신 + INDEX/STATUS 갱신

### 2-1. dialogue-system.md 갱신

`docs/20_design/dialogue-system.md`에 아래 3곳을 편집한다.

#### (A) 섹션 4.2 전체 구조 — meta 블록에 두 필드 추가

`"npc_internal"` 블록 바로 **위에** (즉 `"resolution_comment": null,` 다음 줄에) 아래 두 필드를 추가:

```json
    "trade_request": null,

    "gift_offered": null,
```

수정 후 meta 블록의 끝부분이 이렇게 되어야 한다:

```json
    "resolution_comment": null,

    "trade_request": null,

    "gift_offered": null,

    "npc_internal": {
      "emotional_state": "anxious",
      "hidden_intent": null
    }
```

#### (B) 섹션 4.3 필드 상세 — npc_internal 설명 **앞에** 두 필드 상세 추가

`#### npc_internal` 바로 **앞에** 아래 내용을 삽입:

```markdown
#### trade_request (선택, 거래 발생 시)

| 필드 | 타입 | 설명 |
|------|------|------|
| `action` | str | "buy" \| "sell" \| "negotiate" \| "confirm" \| "reject" |
| `item_instance_id` | str | 거래 대상 아이템 instance ID |
| `proposed_price` | int \| null | PC/NPC 제안가 (negotiate 시) |
| `final_price` | int \| null | 최종 합의가 (confirm 시) |

Python 검증: action이 허용 값인지, 아이템이 실제 존재하는지, 통화 잔고 충분한지 확인. 상세는 item-system.md 섹션 6 참조.

#### gift_offered (선택, 선물 제공 시)

| 필드 | 타입 | 설명 |
|------|------|------|
| `item_instance_id` | str | 선물 아이템 instance ID |
| `npc_reaction` | str | NPC 반응 태그 ("grateful", "indifferent", "offended" 등) |

Python이 item-system.md의 `calculate_gift_affinity()`로 relationship_delta를 계산하고, 세션 종료 시 일괄 적용.
```

#### (C) 섹션 6.2 조건부 검증 테이블 — 마지막 행 뒤에 두 필드 추가

`resolution_comment.impression_tag` 행 **뒤에** 아래 행들을 추가:

```markdown
| `trade_request.action` | "buy" \| "sell" \| "negotiate" \| "confirm" \| "reject" | null 처리 |
| `trade_request.item_instance_id` | 아이템 존재 확인 | null 처리 (거래 무효) |
| `gift_offered.item_instance_id` | 아이템 존재 + PC 소유 확인 | null 처리 (선물 무효) |
```

#### (D) 섹션 11 변경 이력 추가

변경 이력 테이블에 행 추가:

```markdown
| 1.1 | 2026-02-10 | trade_request, gift_offered META 필드 추가 (item-system.md 연동) |
```

### 2-2. INDEX.md 갱신

`docs/INDEX.md`의 예정 문서 섹션에서:

**변경 전:**
```markdown
- item-system.md: 아이템 체계, 거래, 퀘스트 보상
```

**변경 후:**
```markdown
- ~~item-system.md: 아이템 체계, 거래, 퀘스트 보상~~ → ✅ 완료
```

그리고 `20_design/` 섹션에 item-system.md 항목을 추가:

```markdown
### item-system.md
- **목적:** 아이템 체계, 거래, 선물, 인벤토리, 내구도 시스템 설계
- **핵심:** Prototype(불변) + Instance(가변) 분리, axiom_tags 매핑, bulk 기반 인벤토리(50+EXEC 보정), 4종 분류(EQUIPMENT/CONSUMABLE/MATERIAL/MISC).
- **거래:** 관계/HEXACO H 보정 거래가, A(관용성) 기반 흥정 3단계(accept/counter/reject), browse→거래대화 자동진입.
- **확장:** PrototypeRegistry 동적 등록, 초기 43종 → 수천 종 스케일.
```

> 위치는 dialogue-system.md 항목 바로 뒤.

### 2-3. STATUS.md 갱신

`docs/STATUS.md`에 item-system.md 상태를 반영한다. 구체적 형식은 기존 STATUS.md 패턴을 따른다.

> STATUS.md의 정확한 형식은 파일을 열어서 기존 패턴을 확인한 후 맞춰라.

### 2-4. 커밋

```bash
git add docs/20_design/dialogue-system.md docs/INDEX.md docs/STATUS.md
git commit -m "docs: dialogue META 갱신(trade/gift) + INDEX/STATUS에 item-system 반영"
```

---

## 완료 체크리스트

- [ ] `docs/20_design/item-system.md` 존재
- [ ] `docs/20_design/dialogue-system.md` 섹션 4.2에 trade_request, gift_offered 필드 있음
- [ ] `docs/20_design/dialogue-system.md` 섹션 4.3에 두 필드 상세 있음
- [ ] `docs/20_design/dialogue-system.md` 섹션 6.2에 두 필드 검증 규칙 있음
- [ ] `docs/INDEX.md`에 item-system.md 항목 있음
- [ ] `docs/INDEX.md` 예정 문서에서 item-system ✅ 완료 표시
- [ ] `docs/STATUS.md`에 item-system 반영
