# Narrative Service 설계

**버전**: 2.0
**작성일**: 2026-02-13
**상태**: 확정
**교체 대상**: docs/30_technical/narrative-service.md (v1.0)
**관련**: dialogue-system.md, quest-system.md, npc-system.md, relationship-system.md, worldbuilding-and-tone.md, content-safety.md, ai-provider.md, event-bus.md, architecture.md

---

## 1. 개요

### 1.1 목적

NarrativeService는 **모든 LLM 호출의 단일 관문(single gateway)**이다. 프롬프트 빌드, LLM 호출, 응답 파싱, content-safety 검증을 일관된 인터페이스로 제공한다.

### 1.2 핵심 원칙

- **단일 관문**: 게임 내 모든 LLM 호출은 NarrativeService를 경유
- **호출자 조립 원칙**: NarrativeService는 다른 서비스를 import하지 않는다. 호출자(dialogue, quest 등)가 컨텍스트를 조립하여 전달
- **4가지 책임**: 프롬프트 빌드 → LLM 호출 → 응답 파싱 → safety 검증
- **AIProvider 추상화 유지**: 기존 `services/ai/` 구조(base, factory, mock, gemini)와 호환
- **LLM 최소화**: 계산 가능한 것은 Python. LLM은 서술 생성만

### 1.3 아키텍처 위치

```
API Layer
    ↓
Service Layer ─── dialogue_service, quest_service, engine ...
    │                     │
    │                     │ 컨텍스트 조립 후 호출
    │                     ↓
    │              NarrativeService  ← 단일 관문
    │                     │
    │                     ↓
    │              AIProvider (base → gemini/openai/mock)
    ↓
Core Layer
    ↓
DB Layer
```

NarrativeService는 Service Layer에 위치한다. 다른 서비스를 import하지 않으며, AIProvider만 의존한다. 호출자가 NarrativeService에 필요한 모든 데이터를 dict/dataclass로 전달한다.

### 1.4 의존 방향

| 방향 | 예시 | 허용 |
|------|------|------|
| Service → NarrativeService | dialogue_service → narrative_service | ✅ |
| NarrativeService → AIProvider | narrative_service → ai_provider | ✅ |
| NarrativeService → Core | narrative_service → core_rule | ✅ |
| NarrativeService → 다른 Service | narrative_service → dialogue_service | ❌ |

---

## 2. LLM 호출 유형

### 2.1 Alpha MVP 호출 유형

| 호출 유형 | 입력 | 출력 | 호출 주체 | 응답 형식 |
|-----------|------|------|-----------|-----------|
| 탐색 서술 (look) | 노드 데이터, 감각, 오버레이 태그 | narrative 텍스트 | engine | text only |
| 이동 서술 (move) | 출발/도착 노드, 방향 | narrative 텍스트 | engine | text only |
| 대화 응답 | 대화 컨텍스트 전체 | narrative + META JSON | dialogue_service | dual (narrative + meta) |
| 퀘스트 시드 내용 생성 | 시드 조건, NPC 정보, 지역 정보 | 시드 서술 + 구조화 데이터 | quest_service | dual (narrative + meta) |
| NPC 한줄평 (impression_tag) | 대화 요약, 퀘스트 결과 | 짧은 태그 문자열 | dialogue_service (대화 종료 시) | text only |

### 2.2 호출 유형 열거

```python
class NarrativeRequestType(str, Enum):
    """LLM 호출 유형"""
    LOOK = "look"                       # 노드 탐색 서술
    MOVE = "move"                       # 이동 서술
    DIALOGUE = "dialogue"               # 대화 응답 (narrative + META)
    QUEST_SEED = "quest_seed"           # 퀘스트 시드 내용 생성
    IMPRESSION_TAG = "impression_tag"   # NPC 한줄평
```

---

## 3. NarrativeService 클래스 구조

### 3.1 공개 인터페이스

```python
class NarrativeService:
    """모든 LLM 호출의 단일 관문"""

    def __init__(self, ai_provider: AIProvider, config: NarrativeConfig):
        self._ai = ai_provider
        self._config = config
        self._prompt_builder = PromptBuilder(config)
        self._parser = ResponseParser()
        self._safety = ContentSafetyFilter(config)
        self._narration_manager = NarrationManager(config.default_narration_level)

    # --- 탐색/이동 (기존, text only) ---

    async def generate_look(
        self, node_data: dict, player_state: dict
    ) -> str:
        """look 액션 서술 생성"""

    async def generate_move(
        self, from_node: dict, to_node: dict, direction: str
    ) -> str:
        """move 액션 서술 생성"""

    # --- 대화 (신규, dual output) ---

    async def generate_dialogue_response(
        self, dialogue_context: DialoguePromptContext
    ) -> NarrativeResult:
        """대화 턴 1회의 LLM 응답 생성.
        dialogue_service가 컨텍스트를 조립하여 전달한다.
        반환: narrative(플레이어용) + validated_meta(Python용)
        """

    # --- 퀘스트 시드 (신규, dual output) ---

    async def generate_quest_seed(
        self, seed_context: QuestSeedPromptContext
    ) -> NarrativeResult:
        """퀘스트 시드 내용 생성.
        quest_service가 컨텍스트를 조립하여 전달한다.
        """

    # --- NPC 한줄평 (신규, text only) ---

    async def generate_impression_tag(
        self, summary: str, quest_result: dict | None
    ) -> str:
        """대화 종료 시 NPC 한줄평 태그 생성"""
```

### 3.2 내부 공통 호출 메서드

모든 공개 메서드는 내부적으로 `_call_llm()`을 사용한다.

```python
async def _call_llm(
    self,
    request_type: NarrativeRequestType,
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    expect_json: bool = False,
) -> str:
    """LLM 호출 + 폴백 처리.

    Args:
        request_type: 호출 유형 (로깅/폴백 분기용)
        prompt: user 프롬프트
        system_prompt: system 프롬프트
        max_tokens: 최대 토큰
        expect_json: True면 JSON 파싱을 기대하는 호출

    Returns:
        LLM 응답 원문 (파싱 전)

    Raises:
        없음. 실패 시 폴백 텍스트를 반환한다.
    """
```

---

## 4. 프롬프트 빌더 패턴

### 4.1 PromptBuilder 구조

호출 유형별로 프롬프트를 조립한다. 대화용이 가장 복잡하다.

```python
class PromptBuilder:
    """호출 유형별 프롬프트 조립"""

    def build_look(self, node_data: dict, player_state: dict) -> BuiltPrompt:
        """look 프롬프트 조립"""

    def build_move(self, from_node: dict, to_node: dict, direction: str) -> BuiltPrompt:
        """move 프롬프트 조립"""

    def build_dialogue(self, ctx: DialoguePromptContext) -> BuiltPrompt:
        """대화 프롬프트 조립 (가장 복잡)"""

    def build_quest_seed(self, ctx: QuestSeedPromptContext) -> BuiltPrompt:
        """퀘스트 시드 프롬프트 조립"""

    def build_impression_tag(self, summary: str, quest_result: dict | None) -> BuiltPrompt:
        """NPC 한줄평 프롬프트 조립"""


@dataclass
class BuiltPrompt:
    """조립 완료된 프롬프트"""
    system_prompt: str
    user_prompt: str
    max_tokens: int
    expect_json: bool = False
```

### 4.2 look/move 프롬프트 (기존 유지)

기존 v1.0과 동일한 구조. worldbuilding-and-tone.md 섹션 10.1의 템플릿을 사용한다.

```
[System]
あなたはITW（Infinite Text World）の語り手です。
... (worldbuilding-and-tone.md 섹션 10.1 참조)

[User]
場所: {node_name}
支配Axiom: {dominant_axiom}
Tier: {tier}
時間帯: {time_of_day}
天気: {weather}
感覚データ: {sensory_data}
環境タグ: {narrative_tags}

3〜5文で描写を生成してください。
```

max_tokens: look=300, move=150

### 4.3 대화 프롬프트 (신규, 가장 복잡)

dialogue_service가 `DialoguePromptContext`를 조립하여 NarrativeService에 전달한다. NarrativeService는 이를 프롬프트 문자열로 변환만 한다.

#### DialoguePromptContext 구조

```python
@dataclass
class DialoguePromptContext:
    """대화 LLM 호출에 필요한 모든 데이터.
    dialogue_service가 조립하여 NarrativeService에 전달한다.
    NarrativeService는 이 데이터를 프롬프트 문자열로 변환만 한다.
    """

    # --- NPC Context (세션 내내 고정) ---
    npc_name: str
    npc_race: str                          # "human" | "dwarf" | "elf" | "oni"
    npc_role: str                          # "blacksmith", "innkeeper", ...
    hexaco_summary: str                    # HEXACO 자연어 변환 결과
    manner_tags: list[str]                 # ["verbose", "gentle", ...]
    attitude_tags: list[str]               # ["friendly", "cautious_trust", ...]
    relationship_status: str               # "friend", "stranger", ...
    familiarity: int
    npc_memories: list[str]                # Tier 1 + Tier 2 관련 항목
    npc_opinions: dict[str, list[str]]     # 같은 노드 NPC에 대한 의견
    node_environment: str                  # 현재 노드 환경 요약

    # --- Session Context (세션 내내 고정, 조건부) ---
    constraints: dict                      # PC 보유 공리/스탯/아이템
    quest_seed: dict | None                # 시드 활성 시: 유형, 컨텍스트 태그
    active_quests: list[dict] | None       # 퀘스트 진행 시: 요약, 목표
    expired_seeds: list[dict] | None       # 만료 시드 있을 시
    chain_context: dict | None             # 체이닝 시: 이전 퀘스트 요약
    companion_context: dict | None         # 동행 NPC 있을 시

    # --- Turn Context (매 턴 갱신) ---
    budget_phase: str                      # "open" | "winding" | "closing" | "final"
    budget_remaining: int
    budget_total: int
    seed_delivered: bool
    phase_instruction: str                 # 위상별 LLM 지시
    accumulated_delta: float               # 누적 호감 변동 힌트

    # --- Conversation History ---
    history: list[dict]                    # [{"role": "pc"|"npc", "text": "..."}]

    # --- Current Input ---
    pc_input: str

    # --- Content Safety (해당 시) ---
    scene_direction: dict | None           # {"level": "moderate", "instruction": "..."}
```

#### 프롬프트 조립 순서

```
[System Prompt]
  ├─ 역할 정의: "あなたはITWのNPCとして会話します。"
  ├─ META JSON 스키마 정의 (dialogue-system.md 섹션 4.2 구조)
  ├─ 출력 형식 규칙: "반드시 { \"narrative\": ..., \"meta\": { ... } } 형태로 응답하라"
  ├─ 일반 행동 규칙 (worldbuilding-and-tone.md 섹션 6.2 금지 사항)
  └─ content-safety scene_direction (해당 시에만 ~20토큰 추가)

[NPC Context]
  ├─ NPC 프로필 (이름, 종족, 직업, 위치)
  ├─ HEXACO 성격 (자연어 변환 — hexaco_summary)
  ├─ 태도 태그 (attitude_tags)
  ├─ 관계 상태, familiarity
  ├─ NPC 기억 (npc_memories)
  ├─ 같은 노드 NPC 의견 (npc_opinions)
  └─ 현재 노드 환경

[Session Context]
  ├─ constraints (항상): PC 보유 공리/스탯/아이템
  ├─ quest_seed (시드 활성 시)
  ├─ active_quests (퀘스트 진행 시)
  ├─ expired_seeds (만료 시드 있을 시)
  ├─ chain_context (체이닝 시)
  └─ companion_context (동행 NPC 있을 시)

[Turn Context]
  ├─ budget_phase, budget_remaining
  ├─ seed_delivered
  ├─ phase_instruction
  └─ accumulated_delta

[Conversation History]
  ├─ PC: "..."
  ├─ NPC: "..."  ← narrative만, meta 제외
  └─ ...

[Current Input]
  └─ PC: "{pc_input}"
```

#### 대화 max_tokens: 예산 → 토큰 매핑

dialogue-system.md의 예산(budget) 값에 따라 1회 LLM 호출의 max_tokens를 조절한다. 예산이 적을수록 NPC 발언도 짧아져야 자연스럽다.

```python
DIALOGUE_TOKEN_MAP = {
    "open": 500,       # 자유 대화, 충분한 토큰
    "winding": 400,    # 약간 줄임
    "closing": 300,    # 핵심만
    "final": 200,      # 인사만
}

def get_dialogue_max_tokens(budget_phase: str) -> int:
    return DIALOGUE_TOKEN_MAP.get(budget_phase, 400)
```

### 4.4 퀘스트 시드 프롬프트 (신규)

quest_service가 `QuestSeedPromptContext`를 조립하여 전달한다.

```python
@dataclass
class QuestSeedPromptContext:
    """퀘스트 시드 LLM 호출에 필요한 데이터.
    quest_service가 조립하여 전달한다.
    """
    seed_type: str                # "personal" | "rumor" | "request" | "warning"
    seed_tier: int                # 1(대), 2(중), 3(소)
    context_tags: list[str]       # ["missing_person", "family", ...]
    npc_name: str
    npc_role: str
    npc_hexaco_summary: str
    region_info: str              # 지역 환경 요약
    existing_seeds: list[str]     # 이미 활성 시드 태그 (중복 방지)
```

```
[System]
あなたはITWのクエストシード生成器です。
NPC情報と地域情報をもとに、自然な依頼・噂・警告を生成してください。

Tier指示:
  Tier 1(大): 複数NPCが関わる大規模な物語。伏線を2~3本設置せよ。
  Tier 2(中): 個人的な事情が絡む中規模の物語。伏線を1~2本設置せよ。
  Tier 3(小): 単発の頼みごと。伏線不要。

出力形式: { "narrative": "...", "meta": { "title_hint": "...", "quest_type_hint": "...", "urgency_hint": "...", "context_tags": [...] } }

[User]
シード種別: {seed_type}
Tier: {seed_tier}
NPC: {npc_name} ({npc_role})
性格: {npc_hexaco_summary}
地域: {region_info}
コンテキストタグ: {context_tags}
既存シード(重複回避): {existing_seeds}
```

max_tokens: 400

### 4.5 NPC 한줄평 프롬프트 (신규)

대화 종료 시 또는 퀘스트 완료 시, 짧은 태그 문자열을 생성한다.

```
[System]
NPCの立場から、PCの行動に対する一言評価タグを生成してください。
20文字以内の短いタグ1つだけを返してください。

[User]
対話要約: {summary}
クエスト結果: {quest_result}  ← 해당 시에만

例: "grateful_but_bewildered", "reliable_customer", "distrustful_of_methods"
```

max_tokens: 50

---

## 5. META JSON 파싱

### 5.1 파싱 규약

대화 응답과 퀘스트 시드 응답은 `narrative` + `meta`의 이중 구조를 반환한다. LLM 출력에서 이 둘을 분리하는 규약을 정의한다.

#### 기대 형식

```json
{
  "narrative": "한스가 걱정스러운 표정으로 ...",
  "meta": {
    "dialogue_state": { ... },
    "relationship_delta": { ... },
    "memory_tags": [ ... ],
    ...
  }
}
```

#### 파싱 전략

```python
class ResponseParser:
    """LLM 응답 파싱"""

    def parse_dual(self, raw: str) -> tuple[str, dict]:
        """narrative + meta 이중 구조 파싱.

        Returns:
            (narrative, meta) 튜플

        파싱 실패 시:
            narrative = raw 전체 (서술로 간주)
            meta = 빈 dict (기본값으로 폴백)
        """

    def parse_text(self, raw: str) -> str:
        """text only 응답. 그대로 반환."""
```

#### 파싱 단계

```
1. JSON 추출 시도
   ├─ 전체가 JSON → json.loads()
   ├─ ```json ... ``` 블록 → 추출 후 json.loads()
   └─ 실패 → raw 전체를 narrative로, meta = {}

2. narrative 추출
   ├─ parsed["narrative"] 존재 → 사용
   └─ 미존재 → raw 전체

3. meta 추출
   ├─ parsed["meta"] 존재 → 사용
   └─ 미존재 → {}
```

### 5.2 META 검증

파싱 후 meta dict를 dialogue-system.md 섹션 6의 검증 규칙에 따라 검증한다. 검증은 NarrativeService가 아닌 **호출자(dialogue_service)**의 책임이다. NarrativeService는 파싱만 담당한다.

```
NarrativeService 책임: raw → (narrative, meta) 분리
dialogue_service 책임: meta 검증 (클램핑, 기본값, constraints 대조)
```

이 분리가 중요한 이유: 검증 규칙은 호출 유형마다 다르다. 대화 META 검증과 퀘스트 시드 META 검증은 규칙이 다르며, 각 호출자가 자신의 도메인 규칙을 적용해야 한다.

### 5.3 NarrativeResult

```python
@dataclass
class NarrativeResult:
    """이중 출력 (narrative + meta) 호출의 반환 타입"""
    narrative: str                # 플레이어에게 보여줄 서술
    raw_meta: dict                # LLM이 반환한 meta 원본 (검증 전)
    parse_success: bool           # JSON 파싱 성공 여부
    actual_narration_level: str | None  # content-safety 적용된 실제 레벨
```

---

## 6. Content-Safety 연동

### 6.1 적용 범위

content-safety.md의 핵심 원칙: **통상 서술은 이 시스템을 경유하지 않는다.** fade_out 대상 카테고리(intimate, graphic_violence, substance)에 해당하는 행위에만 발동한다.

| 호출 유형 | content-safety 적용 | 이유 |
|-----------|:------------------:|------|
| look / move | ✗ | 통상 서술. 추가 비용 0 |
| dialogue (통상) | ✗ | 일반 대화. 추가 비용 0 |
| dialogue (fade_out 대상) | ✅ | META의 action_tag로 판정 |
| quest_seed | ✗ | 시드 생성은 안전 범위 |
| impression_tag | ✗ | 짧은 태그. 안전 범위 |

### 6.2 발동 흐름

dialogue_service가 META에서 `action_tag`를 확인하고, fade_out 대상이면 `scene_direction`을 `DialoguePromptContext`에 포함하여 NarrativeService에 전달한다.

```
dialogue_service:
  LLM 응답의 META → action_tag 확인
  → fade_out 대상 카테고리?
    ├─ 아니오 (99%) → 다음 턴 통상 진행
    └─ 예 (1%) → DialoguePromptContext.scene_direction 설정
       → NarrativeService.generate_dialogue_response() 호출
       → PromptBuilder가 system prompt에 scene_direction 지시 추가 (~20토큰)
```

### 6.3 폴백 체인

content-safety.md 섹션 4의 폴백 체인을 NarrativeService 내부에서 처리한다.

```
유저 설정 레벨로 LLM 요청
  → 거부 시 한 단계 낮춰서 재시도
  → 최종 폴백은 Python 템플릿

explicit → (거부) → moderate → (거부) → fade_out → (거부) → Python 템플릿
```

```python
NARRATION_LEVELS = {
    "explicit": "상세하게 묘사하라.",
    "moderate": "암시적으로 묘사하되 직접적 표현은 피하라.",
    "fade_out": "행위 시작 암시 1문장 후 장면 전환하라.",
}

FALLBACK_ORDER = ["explicit", "moderate", "fade_out", "template"]
```

### 6.4 카테고리별 레벨 캐싱

content-safety.md 섹션 4.3의 `NarrationManager`를 NarrativeService 내부에 통합한다. 거부 경험을 카테고리별로 기억하여, 동일 카테고리 재발동 시 이미 작동하는 레벨로 시작한다.

```python
class NarrationManager:
    """content-safety 묘사 레벨 관리"""

    def __init__(self, default_level: str = "moderate"):
        self.default_level = default_level
        self.effective_levels: dict[str, str] = {}
        # 카테고리별 실제 작동 레벨 캐시
        # 초기값 없음 — 각 카테고리 첫 발동 시 default_level로 시작

    def get_start_level(self, category: str) -> str:
        return self.effective_levels.get(category, self.default_level)

    def record_fallback(self, category: str, used_level: str) -> None:
        self.effective_levels[category] = used_level
```

---

## 7. 폴백 정책

### 7.1 통합 폴백 체인

모든 LLM 호출에 적용되는 단계별 폴백:

```
[1단계] 통상 LLM 호출
  → 성공 → 응답 반환

[2단계] 재시도 (간소화 프롬프트)
  → system prompt만 유지, 컨텍스트 축소
  → 성공 → 응답 반환

[3단계] Python 템플릿
  → 호출 유형별 기본 서술 반환
```

content-safety 발동 시에는 섹션 6.3의 레벨 폴백이 1단계 내에서 먼저 동작하고, 그래도 실패하면 2단계 → 3단계로 진행한다.

### 7.2 호출 유형별 템플릿 (3단계)

```python
FALLBACK_TEMPLATES = {
    NarrativeRequestType.LOOK: "あなたは{node_name}にいる。周囲を見渡す。",
    NarrativeRequestType.MOVE: "{direction}に進む。",
    NarrativeRequestType.DIALOGUE: "{npc_name}が短く答える。「...そうだな。」",
    NarrativeRequestType.QUEST_SEED: None,  # 시드 생성 실패 → 시드 없음으로 처리
    NarrativeRequestType.IMPRESSION_TAG: "neutral",
}
```

퀘스트 시드 생성 실패 시 폴백 서술이 아니라 **시드 자체를 생성하지 않은 것으로 처리**한다. 5% 확률 판정은 이미 통과했지만, LLM이 내용을 만들지 못하면 시드가 존재하지 않는 것과 같다.

### 7.3 간소화 프롬프트 (2단계)

2단계에서는 컨텍스트를 최소화하여 토큰을 줄이고 성공 확률을 높인다.

```python
def simplify_prompt(built: BuiltPrompt, request_type: NarrativeRequestType) -> BuiltPrompt:
    """2단계 폴백용 간소화 프롬프트 생성"""
    # system prompt 유지
    # user prompt에서 history, npc_opinions, chain_context 등 제거
    # 핵심 정보만 남김: NPC 이름, 상황, PC 입력
```

---

## 8. AIProvider 추상화 유지

### 8.1 기존 구조

```
services/ai/
  ├─ base.py         # AIProvider 추상 클래스
  ├─ factory.py      # provider 생성 팩토리
  ├─ mock.py         # 테스트용 mock
  └─ gemini.py       # Gemini API 구현
```

### 8.2 NarrativeService와의 연동

NarrativeService는 `AIProvider.generate()` 인터페이스만 사용한다. Provider 교체 시 NarrativeService 변경 불필요.

```python
# NarrativeService는 이 인터페이스만 사용
class AIProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1000,
    ) -> str:
        """LLM 호출. 반환: 응답 텍스트"""
```

### 8.3 인터페이스 변경 없음

v2.0에서 AIProvider 인터페이스 변경은 **없다**. NarrativeService가 내부적으로 프롬프트 조립/파싱/폴백을 처리하므로, AIProvider는 단순 텍스트 입출력만 담당한다.

---

## 9. 호출 흐름 상세

### 9.1 dialogue_service → NarrativeService 흐름

대화 시스템이 NarrativeService를 호출하는 전체 흐름:

```
[dialogue_service]

1. 세션 시작
   ├─ EventBus: dialogue_started 발행
   ├─ EventBus: attitude_request 발행 → attitude_response 수신
   ├─ quest 모듈: quest_seed_generated 수신 (해당 시)
   └─ DialoguePromptContext 초기 조립

2. 대화 루프 (매 턴)
   ├─ PC 입력 수신
   ├─ budget_phase 계산, phase_instruction 결정
   ├─ DialoguePromptContext 갱신 (Turn Context 부분)
   │
   ├─ narrative_service.generate_dialogue_response(ctx) 호출
   │     │
   │     │  [NarrativeService 내부]
   │     ├─ PromptBuilder.build_dialogue(ctx) → BuiltPrompt
   │     ├─ _call_llm(DIALOGUE, prompt, system, max_tokens, expect_json=True)
   │     │     ├─ AIProvider.generate() 호출
   │     │     ├─ 실패 시 → 간소화 재시도 → 템플릿 폴백
   │     │     └─ 응답 원문 반환
   │     ├─ ResponseParser.parse_dual(raw) → (narrative, raw_meta)
   │     └─ NarrativeResult 반환
   │
   ├─ dialogue_service: raw_meta 검증 (섹션 5.2)
   │     ├─ relationship_delta 클램핑 (-5~+5)
   │     ├─ quest_seed_response 처리
   │     ├─ action_interpretation 검증 (constraints 대조)
   │     └─ memory_tags 수집
   ├─ narrative를 PC에게 출력
   └─ 종료 판정

3. 세션 종료
   └─ EventBus: dialogue_ended 발행
```

### 9.2 quest_service → NarrativeService 흐름

```
[quest_service]

1. quest_seed_generated 이벤트 발행 전, 시드 내용 생성이 필요할 때:
   ├─ QuestSeedPromptContext 조립
   ├─ narrative_service.generate_quest_seed(ctx) 호출
   │     │
   │     │  [NarrativeService 내부]
   │     ├─ PromptBuilder.build_quest_seed(ctx) → BuiltPrompt
   │     ├─ _call_llm(QUEST_SEED, ..., expect_json=True)
   │     ├─ ResponseParser.parse_dual(raw) → (narrative, raw_meta)
   │     └─ NarrativeResult 반환
   │
   ├─ quest_service: raw_meta 검증
   │     ├─ quest_type_hint 유효성
   │     ├─ context_tags 정합성
   │     └─ 검증 실패 시 fallback 기본값 적용
   └─ EventBus: quest_seed_generated 발행 (시드 정보 포함)
```

### 9.3 look/move (기존 유지)

```
[engine]

PC: "look"
  → narrative_service.generate_look(node_data, player_state)
        │
        │  [NarrativeService 내부]
        ├─ PromptBuilder.build_look(node_data, player_state) → BuiltPrompt
        ├─ _call_llm(LOOK, ..., expect_json=False)
        └─ 텍스트 반환 (또는 폴백 템플릿)
  → PC에게 출력
```

---

## 10. 파일 구조

```
src/services/
  ├─ narrative_service.py        # NarrativeService 본체
  ├─ narrative_types.py          # NarrativeRequestType, NarrativeResult,
  │                              # DialoguePromptContext, QuestSeedPromptContext,
  │                              # BuiltPrompt, NarrativeConfig
  ├─ narrative_prompts.py        # PromptBuilder (프롬프트 조립 로직)
  ├─ narrative_parser.py         # ResponseParser (JSON 파싱)
  ├─ narrative_safety.py         # ContentSafetyFilter, NarrationManager
  └─ ai/                         # 기존 AIProvider 구조 (변경 없음)
       ├─ base.py
       ├─ factory.py
       ├─ mock.py
       └─ gemini.py
```

---

## 11. 검증 체크리스트

| # | 검증 항목 | 결과 |
|---|----------|------|
| 1 | dialogue_service가 NarrativeService를 호출하는 흐름이 명확한가? | ✅ 섹션 9.1 |
| 2 | META JSON 파싱 규약이 dialogue-system.md와 일치하는가? | ✅ 섹션 5 — dialogue-system.md 섹션 4.2 구조 준수 |
| 3 | content-safety.md의 폴백 체인이 반영되었는가? | ✅ 섹션 6.3, 6.4 — 레벨 폴백 + 카테고리 캐싱 |
| 4 | AIProvider 인터페이스 변경 없이 확장 가능한가? | ✅ 섹션 8.3 — 인터페이스 변경 없음 |
| 5 | Service간 직접 호출이 발생하지 않는가? | ✅ 섹션 1.4 — 호출자가 컨텍스트를 조립하여 전달 |
| 6 | look/move 기존 기능이 깨지지 않는 구조인가? | ✅ 섹션 4.2, 9.3 — 기존 인터페이스 유지 |

---

## 12. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | — | 최초 작성: look/move 서술 생성만 담당 |
| 2.0 | 2026-02-13 | 전면 재설계: 단일 관문 확장, 대화/퀘스트시드/한줄평 호출 유형 추가, 프롬프트 빌더 패턴, META JSON 파싱 규약, content-safety 연동, 폴백 체인, 예산→토큰 매핑 |
