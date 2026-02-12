# Content Safety 설계 메모

**버전**: 0.3 (초안)  
**작성일**: 2026-02-12  
**상태**: 아이디어 단계  
**위치**: docs/10_product/  
**관련**: narrative-service (미작성), dialogue-system.md, relationship-system.md

---

## 1. 기본 원칙

### 페이드 아웃 정책

유저 행동을 **차단하지 않는다.** 행위 발생을 인정하되 묘사를 건너뛰고, 결과만 전달한다.

```
차단 (금지)     → 유저 도전 욕구 유발, 경계 탐색 시작
부드러운 거절   → 유저 의도 부정, 위화감
페이드 아웃 (채택) → 행위 인정 + 묘사 생략 + 결과 전달. 유저가 행간에서 만족
```

### 세계 내 반응 원칙

모든 결과는 **시스템 차단이 아닌 세계의 자연스러운 반응**으로 처리한다. 관계 수치, NPC 성격, 상황 맥락이 결과를 결정한다.

### 적용 범위

이 시스템은 **fade_out 대상 카테고리에 해당하는 행위에만 발동**한다. 통상 서술(이동, 대화, 전투, 탐색 등)은 이 시스템을 경유하지 않으며, 추가 비용이 전혀 없다.

---

## 2. 묘사 레벨 시스템

### 2.1 3단계 묘사 레벨

| 레벨 | LLM 지시 | 유저 경험 | 비고 |
|------|----------|----------|------|
| `explicit` | 상세하게 묘사하라 | 직접적 묘사 | LLM 능력에 의존 |
| `moderate` | 암시적으로 묘사하되 직접적 표현은 피하라 | 행간 묘사 | 대부분의 상용 LLM 가능 |
| `fade_out` | 행위 시작 암시 1문장 후 장면 전환하라 | 스킵 + 결과만 | 어떤 LLM이든 가능 |

유저가 레벨을 선택한다. 기본값: `moderate`.

### 2.2 fade_out 대상 카테고리 (구체 정의는 별도)

| 카테고리 | 예시 | 비고 |
|----------|------|------|
| `intimate` | 성적 행위 | 관계 수준에 따라 성공/거절 분기 |
| `graphic_violence` | 고문, 잔혹 행위 | 전투와 구분 필요 |
| `substance` | 약물 사용 등 | 해당 시 |

카테고리 목록과 판정 기준의 구체 설계는 별도 문서에서 진행한다.

---

## 3. 시스템 흐름

### 3.1 발동 판정

이 시스템은 **기존 LLM 호출 흐름에 분기 1개를 추가**하는 것이지, 별도 파이프라인이 아니다.

```
PC 행동 선언
  → LLM: action_interpretation 반환 (기존 호출, 변경 없음)
  → META에 action_tag 포함 ("intimate", "combat", "explore", ...)
  → Python: action_tag가 fade_out 대상 카테고리인가?
    │
    ├─ 아니오 (99% 케이스)
    │   → 통상 서술 요청. 이 시스템 경유하지 않음. 추가 비용 0.
    │
    └─ 예 (1% 케이스)
        → NarrationManager.generate() 호출
        → 유저 레벨에 맞는 scene_direction 지시를 프롬프트에 추가 (~20토큰)
        → LLM 서술 생성 → 결과 처리
```

### 3.2 LLM 프롬프트 지시 (발동 시에만)

```json
{
  "scene_direction": {
    "level": "moderate",
    "category": "intimate",
    "instruction": "암시적으로 묘사하되 직접적 표현은 피하라."
  }
}
```

### 3.3 결과 처리

fade_out 대상 행위도 **기존 시스템의 결과 처리를 그대로 사용**한다.

| 시스템 | 처리 |
|--------|------|
| relationship | affinity/trust 변동, attitude_tag 부여 |
| npc_memory | 기억 저장 (행위 태그, 상세 묘사 아님) |
| game_time | 턴/시간 경과 |
| status | 기분/컨디션 태그 부여 |

---

## 4. 폴백 체인

### 4.1 핵심 구조

유저 설정 레벨로 LLM에 요청 → 거부 시 한 단계 낮춰서 재시도 → 최종 폴백은 Python 템플릿.

```
explicit → (거부) → moderate → (거부) → fade_out → (거부) → Python 템플릿
```

LLM 교체에 자동 적응한다. Claude는 moderate까지, 로컬 모델은 explicit까지 되더라도 같은 코드가 각 LLM의 한계선에서 멈춘다.

### 4.2 구현 구조

```python
NARRATION_LEVELS = {
    "explicit": "상세하게 묘사하라.",
    "moderate": "암시적으로 묘사하되 직접적 표현은 피하라.",
    "fade_out": "행위 시작 암시 1문장 후 장면 전환하라.",
}

FALLBACK_ORDER = ["explicit", "moderate", "fade_out", "template"]


async def generate_with_fallback(
    context: dict,
    start_level: str,
) -> tuple[str, str]:
    """묘사 생성. 거부 시 레벨을 낮춰가며 재시도.
    반환: (서술 텍스트, 실제 사용된 레벨)
    """
    current = FALLBACK_ORDER.index(start_level)
    
    while current < len(FALLBACK_ORDER):
        level = FALLBACK_ORDER[current]
        
        if level == "template":
            return FADE_OUT_TEMPLATE.format(**context), "template"
        
        context["scene_direction"] = {
            "level": level,
            "instruction": NARRATION_LEVELS[level],
        }
        response = await llm_generate(context)
        
        if response and not is_refusal(response):
            return response, level
        
        current += 1
    
    return FADE_OUT_TEMPLATE.format(**context), "template"
```

### 4.3 카테고리별 레벨 캐싱

거부 경험을 **카테고리별로 따로 기억**한다. intimate에서 거부당했다고 graphic_violence까지 레벨이 내려가는 것을 방지한다.

```python
class NarrationManager:
    def __init__(self, user_level: str):
        self.user_level = user_level
        
        # 카테고리별 실제 작동 레벨 (거부 경험에 따라 학습)
        self.effective_levels: dict[str, str] = {}
        # 초기값 없음 — 각 카테고리 첫 발동 시 user_level로 시작
    
    async def generate(self, context: dict, category: str) -> str:
        # 이 카테고리의 작동 레벨 (캐싱 없으면 유저 설정값)
        start_level = self.effective_levels.get(category, self.user_level)
        
        result, used_level = await generate_with_fallback(context, start_level)
        
        # 거부로 레벨이 내려갔으면 이 카테고리만 기억
        if used_level != start_level:
            self.effective_levels[category] = used_level
            # 유저에게 1회 알림 (카테고리별):
            # "[현재 LLM에서는 이 유형의 장면이 moderate 레벨로 서술됩니다]"
        
        return result
```

이 구조에서 거부는 **LLM 교체 직후 × 카테고리당 1~2회**만 발생하고, 이후 동일 카테고리에서는 0회로 수렴한다. 다른 카테고리에는 영향 없음.

---

## 5. 성능 영향 분석

| 상황 | 빈도 | 추가 LLM 호출 | 추가 토큰 |
|------|------|:------------:|:--------:|
| 통상 행동 (이동, 대화, 전투, 탐색 등) | ~99% | 0 | 0 |
| fade_out 대상 + 캐싱 적중 | ~0.9% | 0 | ~20 (지시 1줄) |
| fade_out 대상 + 첫 거부 (LLM당 카테고리당 1~2회) | ~0.1% | 1회 재시도 | ~20 |

통상 서술은 이 시스템을 경유하지 않으므로 **게임 전체 성능에 영향 없음**.

---

## 6. 관계 수준에 따른 분기

fade_out 대상 행위라도 **NPC의 반응은 관계 시스템이 결정**한다.

```
관계 충분 (bonded 등):
  → 묘사 레벨에 따른 서술 (도입 + 레벨별 묘사/스킵 + 결과)
  → affinity/trust 변동, mood 태그

관계 부족:
  → NPC가 성격(HEXACO)에 맞게 거절
  → 이것도 시스템 차단이 아닌 세계 내 반응
  → affinity/trust 감소, attitude_tag 변경
```

---

## 7. SaaS 대비

### 7.1 BYOK vs SaaS 차이

| 항목 | BYOK (현재) | SaaS (미래) |
|------|-----------|-----------|
| 묘사 레벨 상한 | 유저 자유 | 서비스 측 제한 |
| LLM 윤리 블록 | 유저 책임 | 서비스 제공자 책임 |
| 서술 거부 시 폴백 | 권장 | 필수 |
| 로깅/감사 | 불필요 | 필요 가능 |
| 연령 제한 | 불필요 | 필요 |

### 7.2 SaaS 레벨 상한

서비스 측에서 최대 허용 레벨을 설정한다. 유저 설정과 서비스 상한 중 낮은 쪽이 적용된다.

```python
SERVICE_MAX_LEVEL = "moderate"  # SaaS 정책으로 결정

def resolve_level(user_level: str, service_max: str) -> str:
    order = ["fade_out", "moderate", "explicit"]
    user_idx = order.index(user_level)
    max_idx = order.index(service_max)
    return order[min(user_idx, max_idx)]
```

SaaS에서 상한이 `moderate`이면 explicit 요청은 LLM에 도달하기 전에 차단되므로 **API 거부가 원천 발생하지 않는다**.

---

## 8. 확장 아이디어

### 소환 아이템

- 사용 시 NPC를 생성하는 아이템 (사역마, 소환수 등)
- item → use → npc_created 단방향 변환
- 생성된 NPC는 companion 시스템으로 동행
- 내구도 = 소환 횟수 또는 지속 턴
- 우선순위: Beta 이후

---

## 9. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 0.1 | 2026-02-12 | 초안: 페이드 아웃 정책, 시스템 구조, SaaS 대비 메모 |
| 0.2 | 2026-02-12 | 묘사 레벨 3단계, 폴백 체인, 레벨 캐싱, SaaS 레벨 상한 추가 |
| 0.3 | 2026-02-12 | 카테고리별 캐싱으로 변경, 통상 서술 비경유 명시, 성능 영향 분석 추가 |
