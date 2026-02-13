# 구현 지시서 #10: 대화 시스템 (Dialogue Module)

**발행일**: 2026-02-13
**발행자**: 사령탑 세션
**수행자**: Claude Code
**의존**: #08(NPC), #09(관계) 완료 전제

---

## 실행 전 필수 사항

1. `docs/INDEX.md`, `docs/SRC_INDEX.md` 를 읽고 현재 프로젝트 구조를 파악할 것
2. 각 블록 시작 전 참조 문서를 반드시 읽을 것
3. 각 블록은 **단독 실행/테스트 가능**해야 한다
4. 블록 순서: #10-0 → A → B → C → D → E (역순 금지)
5. `ruff check src/ tests/` + `pytest -v` 통과 후 다음 블록 진행

---

## 아키텍처 원칙 (위반 금지)

- 의존 방향: API → Service → Core → DB (역방향 금지)
- Service간 직접 호출 금지, EventBus 경유
- Core는 DB를 모른다 (SQLAlchemy import 금지)
- LLM 최소화: 계산 가능한 것은 Python, LLM은 서술 생성만
- print() 사용 금지, logging 모듈 사용

---

# #10-0: 메타 정비

## 목적
narrative-service.md 배치 + INDEX/SRC_INDEX 갱신

## 작업

### 0-1. narrative-service.md 배치

`docs/30_technical/narrative-service.md`를 새로 제공되는 v2.0 파일로 **교체**한다.

### 0-2. docs/INDEX.md 갱신

`30_technical/` 섹션의 narrative-service.md 항목을 갱신:

```
### narrative-service.md
- **목적:** 모든 LLM 호출의 단일 관문(single gateway) 설계
- **핵심:** 5종 호출 유형(look/move/dialogue/quest_seed/impression_tag), PromptBuilder 패턴, META JSON 파싱, content-safety 연동, 폴백 체인, 예산→토큰 매핑
- **상태:** 확정 (v2.0)
```

### 0-3. docs/SRC_INDEX.md 갱신

이 블록에서는 아직 코드를 작성하지 않으므로 SRC_INDEX 변경 없음. #10-E 완료 후 최종 갱신한다.

### 0-4. event_types.py 갱신

참조: `src/core/event_types.py`

기존 EventTypes 클래스에 아래 상수를 추가:

```python
# Dialogue events
DIALOGUE_STARTED = "dialogue_started"
DIALOGUE_ACTION_DECLARED = "dialogue_action_declared"
# DIALOGUE_ENDED는 이미 존재 확인할 것. 없으면 추가.

# Quest-Dialogue integration
QUEST_SEED_GENERATED = "quest_seed_generated"

# Attitude (이미 존재 확인)
ATTITUDE_REQUEST = "attitude_request"
ATTITUDE_RESPONSE = "attitude_response"
```

**기존 상수와 중복 여부를 반드시 확인**하고, 이미 존재하면 추가하지 않는다.

## 검증
- `ruff check src/`
- `pytest -v` (기존 테스트 깨지지 않음)

---

# #10-A: Dialogue Core 모델

## 목적
대화 시스템의 순수 Python 도메인 모델과 예산 계산 로직 구현

## 참조 문서
- `docs/20_design/dialogue-system.md` — 섹션 2(턴 구조), 섹션 7.3(HEXACO 변환), 섹션 9(데이터 모델)
- `docs/20_design/relationship-system.md` — RelationshipStatus 정의 참조

## 산출물

### A-1. `src/core/dialogue/__init__.py`

패키지 초기화 + re-export.

### A-2. `src/core/dialogue/models.py`

dialogue-system.md 섹션 9.1, 9.2 기반.

```python
"""대화 시스템 도메인 모델 (DB 무관)"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DialogueTurn:
    """대화 턴 1회"""
    turn_index: int
    pc_input: str
    npc_narrative: str          # LLM 서술 (플레이어에게 보여줌)
    raw_meta: dict              # LLM META 원본
    validated_meta: dict        # Python 검증 후 META

@dataclass
class DialogueSession:
    """대화 세션 단위 (인메모리 상태)"""
    session_id: str                     # UUID
    player_id: str
    npc_id: str
    node_id: str

    # 예산
    budget_total: int
    budget_remaining: int
    budget_phase: str                   # "open"|"winding"|"closing"|"final"

    # 상태
    status: str = "active"              # "active"|"ended_by_pc"|"ended_by_npc"
                                        # |"ended_by_budget"|"ended_by_system"
    started_turn: int = 0               # 게임 턴
    dialogue_turn_count: int = 0

    # 시드
    quest_seed: Optional[dict] = None
    seed_delivered: bool = False
    seed_result: Optional[str] = None   # "accepted"|"ignored"|None

    # 동행 (companion-system.md 연동 예비)
    companion_npc_id: Optional[str] = None

    # 누적 (세션 종료 시 일괄 처리)
    accumulated_affinity_delta: float = 0.0
    accumulated_trust_delta: float = 0.0
    accumulated_memory_tags: list[str] = field(default_factory=list)

    # 대화 이력
    history: list[DialogueTurn] = field(default_factory=list)

    # 컨텍스트 (세션 시작 시 조립)
    npc_context: dict = field(default_factory=dict)
    session_context: dict = field(default_factory=dict)


# --- 종료 상태 코드 ---
DIALOGUE_END_STATUSES = {
    "ended_by_pc",
    "ended_by_npc",
    "ended_by_budget",
    "ended_by_system",
}
```

### A-3. `src/core/dialogue/budget.py`

dialogue-system.md 섹션 2.3 기반. 예산 계산 + 위상 판정 + 위상별 LLM 지시문.

```python
"""대화 턴 예산 계산 및 위상 관리"""

BASE_BUDGET: dict[str, int] = {
    "stranger": 3,
    "acquaintance": 4,
    "friend": 6,
    "bonded": 8,
    "rival": 4,
    "nemesis": 6,
}

def calculate_budget(
    relationship_status: str,
    npc_hexaco_x: float,
    has_quest_seed: bool,
) -> int:
    """대화 턴 예산 계산. 최소 2턴."""
    base = BASE_BUDGET.get(relationship_status, 3)
    if npc_hexaco_x >= 0.7:
        base += 1
    elif npc_hexaco_x <= 0.3:
        base -= 1
    if has_quest_seed:
        base += 2
    return max(2, base)

def get_budget_phase(remaining: int, total: int) -> str:
    """예산 잔여 비율 → 위상 결정"""
    if total <= 0:
        return "final"
    ratio = remaining / total
    if ratio > 0.6:
        return "open"
    elif ratio > 0.3:
        return "winding"
    elif remaining > 0:
        return "closing"
    else:
        return "final"

# 위상별 LLM 지시문 (일본어 — 게임 출력 언어)
PHASE_INSTRUCTIONS: dict[str, str] = {
    "open": "",  # 지시 없음
    "winding": "NPCはそろそろ他の用事を意識し始めている。",
    "closing": "NPCは会話を切り上げようとしている。核心だけ伝えろ。",
    "final": "これが最後の発言だ。挨拶して終われ。",
}

def get_phase_instruction(phase: str, seed_delivered: bool, has_seed: bool) -> str:
    """위상별 LLM 지시문 반환. winding에서 시드 미전달 시 강제 지시 추가."""
    base = PHASE_INSTRUCTIONS.get(phase, "")
    if phase == "winding" and has_seed and not seed_delivered:
        base += " 時間が足りない。シードを今すぐ伝えろ。"
    return base
```

### A-4. `src/core/dialogue/hexaco_descriptors.py`

dialogue-system.md 섹션 7.3 기반. HEXACO 수치 → 자연어 변환.

```python
"""HEXACO 수치 → 자연어 변환 (LLM 프롬프트용)"""

HEXACO_DESCRIPTORS: dict[str, list[tuple[float, float, str]]] = {
    "H": [
        (0.0, 0.3, "利益に敏感で実利的だ"),
        (0.3, 0.7, "普通レベルの誠実さ"),
        (0.7, 1.0, "正直で謙虚だ"),
    ],
    "E": [
        (0.0, 0.3, "大胆で感情に揺れない"),
        (0.3, 0.7, "普通レベルの感受性"),
        (0.7, 1.0, "心配性で感情的だ"),
    ],
    "X": [
        (0.0, 0.3, "寡黙で一人を好む"),
        (0.3, 0.7, "普通レベルの社交性"),
        (0.7, 1.0, "外向的でおしゃべりだ"),
    ],
    "A": [
        (0.0, 0.3, "批判的で対立を恐れない"),
        (0.3, 0.7, "普通レベルの寛容さ"),
        (0.7, 1.0, "寛大で協力的だ"),
    ],
    "C": [
        (0.0, 0.3, "衝動的で即興的だ"),
        (0.3, 0.7, "普通レベルの勤勉さ"),
        (0.7, 1.0, "体系的で慎重だ"),
    ],
    "O": [
        (0.0, 0.3, "伝統的で慣れたものを好む"),
        (0.3, 0.7, "普通レベルの開放性"),
        (0.7, 1.0, "好奇心が強く新しいものを好む"),
    ],
}

def hexaco_to_natural_language(hexaco_values: dict[str, float]) -> str:
    """HEXACO dict → 자연어 성격 묘사 문자열.
    
    Args:
        hexaco_values: {"H": 0.8, "E": 0.3, "X": 0.7, "A": 0.6, "C": 0.5, "O": 0.4}
    
    Returns:
        "このNPCは正直で謙虚(H)、大胆で感情に揺れない(E)、外向的でおしゃべり(X)..."
    """
    parts: list[str] = []
    for factor in ("H", "E", "X", "A", "C", "O"):
        value = hexaco_values.get(factor, 0.5)
        for low, high, desc in HEXACO_DESCRIPTORS.get(factor, []):
            if low <= value < high or (high == 1.0 and value == 1.0):
                parts.append(f"{desc}({factor})")
                break
    return "このNPCは" + "、".join(parts) + "。"
```

### A-5. 테스트: `tests/core/dialogue/test_dialogue_models.py`

```
테스트 항목:
1. DialogueSession 기본 생성 + 필드 기본값 확인
2. DialogueTurn 생성
3. calculate_budget — 관계별 기본값, HEXACO 보정, 시드 보정, 최소 2턴
4. get_budget_phase — 경계값 (0.6, 0.3, 0) 테스트
5. get_phase_instruction — 기본 지시 + 시드 미전달 강제 지시
6. hexaco_to_natural_language — 정상 변환, 경계값(0.0, 0.3, 0.7, 1.0)
```

최소 12개 테스트 케이스.

## 검증
- `ruff check src/ tests/`
- `pytest tests/core/dialogue/ -v`
- `pytest -v` (전체 테스트 통과)

---

# #10-B: META 검증 + Constraints 검증

## 목적
LLM 반환 META JSON의 Python 사후 검증 파이프라인 구현

## 참조 문서
- `docs/20_design/dialogue-system.md` — 섹션 5(Constraints), 섹션 6(검증 파이프라인)

## 산출물

### B-1. `src/core/dialogue/validation.py`

dialogue-system.md 섹션 6.2 기반. 모든 검증은 **보정 우선, 재생성 금지** 원칙.

```python
"""META JSON 사후 검증 파이프라인"""
import logging

logger = logging.getLogger(__name__)

# --- 기본값 ---
DEFAULT_DIALOGUE_STATE = {
    "wants_to_continue": True,
    "end_conversation": False,
    "topic_tags": [],
}

DEFAULT_RELATIONSHIP_DELTA = {
    "affinity": 0,
    "reason": "none",
}

def validate_meta(raw_meta: dict) -> dict:
    """META 전체 검증. 보정된 meta dict 반환.
    
    항상 검증:
    - dialogue_state: 필수 필드 존재 → 없으면 기본값
    - relationship_delta.affinity: -5 ~ +5 클램핑
    - memory_tags: list[str], 각 50자 이내
    
    조건부 검증:
    - quest_seed_response: "accepted"|"ignored"|null
    - action_interpretation: constraints 검증은 별도 함수
    - trade_request: action 허용값 확인
    - gift_offered: item 존재 확인 (ID만 검증, 실제 DB 조회는 Service 책임)
    """

def validate_dialogue_state(state: dict | None) -> dict:
    """dialogue_state 필수 필드 검증 + 기본값"""

def validate_relationship_delta(delta: dict | None) -> dict:
    """affinity -5~+5 클램핑"""

def validate_memory_tags(tags: list | None) -> list[str]:
    """문자열 배열, 각 50자 이내 보정"""

def validate_quest_seed_response(response: str | None) -> str | None:
    """'accepted'|'ignored'|None만 허용"""

def validate_trade_request(trade: dict | None) -> dict | None:
    """action 허용값 검증. 불허 시 None"""

def validate_gift_offered(gift: dict | None) -> dict | None:
    """기본 구조 검증. 불허 시 None"""
```

### B-2. `src/core/dialogue/constraints.py`

dialogue-system.md 섹션 5.3 기반.

```python
"""Constraints 검증 — PC 보유 자원 대조"""
import logging

logger = logging.getLogger(__name__)

def validate_action_interpretation(
    interpretation: dict | None,
    pc_axioms: list[str],
    pc_items: list[str],
    pc_stats: dict[str, int],
) -> dict | None:
    """LLM의 action_interpretation을 PC 보유 자원과 대조.
    
    - 미보유 axiom 참조 modifier → 제거
    - 미보유 item 참조 modifier → 제거
    - modifier value → -2.0 ~ 2.0 클램핑
    - stat → WRITE|READ|EXEC|SUDO 검증, 불허 시 EXEC
    
    interpretation이 None이면 None 반환.
    """
```

### B-3. 테스트: `tests/core/dialogue/test_dialogue_validation.py`

```
테스트 항목:
1. validate_meta — 정상 META 통과
2. validate_meta — 필수 필드 누락 시 기본값 적용
3. validate_dialogue_state — None → 기본값
4. validate_relationship_delta — 클램핑 (-10 → -5, +10 → +5)
5. validate_memory_tags — 50자 초과 잘라냄, 비문자열 제거
6. validate_quest_seed_response — "accepted", "ignored", None, 불허값
7. validate_action_interpretation — 미보유 axiom 제거
8. validate_action_interpretation — 미보유 item 제거
9. validate_action_interpretation — modifier 클램핑
10. validate_action_interpretation — 잘못된 stat → EXEC
11. validate_action_interpretation — None 입력 → None 반환
12. validate_trade_request — 불허 action
13. validate_gift_offered — 구조 불량 시 None
```

최소 13개 테스트 케이스.

## 검증
- `ruff check src/ tests/`
- `pytest tests/core/dialogue/ -v`
- `pytest -v`

---

# #10-C: NarrativeService v2 확장

## 목적
기존 narrative_service.py를 v2.0 설계(단일 관문)로 확장. 대화/퀘스트시드/한줄평 호출 유형 추가.

## 참조 문서
- `docs/30_technical/narrative-service.md` (v2.0) — **전문 필독**
- `docs/30_technical/ai-provider.md` — AIProvider 인터페이스
- `docs/10_product/content-safety.md` — 묘사 레벨, 폴백
- `docs/10_product/worldbuilding-and-tone.md` — 톤, 프롬프트 템플릿 (섹션 10.1)
- `src/services/narrative_service.py` — 기존 코드 확인
- `src/services/ai/base.py` — 현재 AIProvider 시그니처 확인

## ⚠️ 사령탑 지시: AIProvider 인터페이스 변경

narrative-service.md v2.0은 "AIProvider 인터페이스 변경 없음"이라고 기술하나, 현재 코드의 `AIProvider.generate()` 시그니처는 `(prompt, context)` 형태이다.
v2.0이 요구하는 `(prompt, system_prompt, max_tokens)` 시그니처와 불일치한다.

**해결 방법**: `AIProvider.generate()` 시그니처를 확장한다.

```python
# 변경 전 (현재)
async def generate(self, prompt: str, context: dict | None = None) -> str:

# 변경 후
async def generate(
    self,
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 1000,
    context: dict | None = None,  # 하위 호환용, deprecated
) -> str:
```

- 기존 `context` 파라미터는 하위 호환을 위해 남기되, 새 코드에서는 사용하지 않는다.
- `MockProvider`, `GeminiProvider` 등 기존 구현체도 시그니처를 맞춘다.
- **기존 테스트가 깨지지 않도록** 주의.

## ⚠️ 사령탑 지시: npc_race Alpha 범위

`DialoguePromptContext.npc_race` 주석을 `# Alpha: "human" only` 로 변경한다. 이종족 예시("dwarf", "elf", "oni")는 제거.

## 산출물

### C-1. `src/services/ai/base.py` 수정

위 시그니처 변경 적용.

### C-2. `src/services/ai/mock.py` 수정

시그니처 맞춤. `system_prompt`, `max_tokens` 파라미터 추가, 기존 동작 유지.
**대화 호출 시 mock 응답**: expect_json 여부를 알 수 없으므로, prompt에 "JSON"이 포함되면 mock JSON 응답을 반환하는 분기를 추가한다.

```python
MOCK_DIALOGUE_RESPONSE = json.dumps({
    "narrative": "NPCが短く答える。「...そうだな。」",
    "meta": {
        "dialogue_state": {"wants_to_continue": True, "end_conversation": False, "topic_tags": []},
        "relationship_delta": {"affinity": 0, "reason": "none"},
        "memory_tags": [],
        "quest_seed_response": None,
        "quest_details": None,
        "action_interpretation": None,
        "resolution_comment": None,
        "trade_request": None,
        "gift_offered": None,
        "npc_internal": {"emotional_state": "neutral", "hidden_intent": None},
    }
}, ensure_ascii=False)
```

### C-3. `src/services/ai/gemini.py` 수정

시그니처 맞춤. `system_prompt`를 Gemini API의 system instruction으로 전달. `max_tokens`를 generation_config에 반영.

### C-4. `src/services/narrative_types.py` (신규)

narrative-service.md 섹션 2.2, 3.1, 4.3, 4.4, 5.3 기반.

```python
"""NarrativeService 타입 정의"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class NarrativeRequestType(str, Enum):
    LOOK = "look"
    MOVE = "move"
    DIALOGUE = "dialogue"
    QUEST_SEED = "quest_seed"
    IMPRESSION_TAG = "impression_tag"

@dataclass
class NarrativeConfig:
    default_narration_level: str = "moderate"  # content-safety 기본 레벨

@dataclass
class BuiltPrompt:
    system_prompt: str
    user_prompt: str
    max_tokens: int
    expect_json: bool = False

@dataclass
class DialoguePromptContext:
    """dialogue_service가 조립하여 NarrativeService에 전달."""
    # NPC Context
    npc_name: str
    npc_race: str = "human"  # Alpha: "human" only
    npc_role: str = ""
    hexaco_summary: str = ""
    manner_tags: list[str] = field(default_factory=list)
    attitude_tags: list[str] = field(default_factory=list)
    relationship_status: str = "stranger"
    familiarity: int = 0
    npc_memories: list[str] = field(default_factory=list)
    npc_opinions: dict[str, list[str]] = field(default_factory=dict)
    node_environment: str = ""
    
    # Session Context
    constraints: dict = field(default_factory=dict)
    quest_seed: Optional[dict] = None
    active_quests: Optional[list[dict]] = None
    expired_seeds: Optional[list[dict]] = None
    chain_context: Optional[dict] = None
    companion_context: Optional[dict] = None
    
    # Turn Context
    budget_phase: str = "open"
    budget_remaining: int = 0
    budget_total: int = 0
    seed_delivered: bool = False
    phase_instruction: str = ""
    accumulated_delta: float = 0.0
    
    # History + Input
    history: list[dict] = field(default_factory=list)
    pc_input: str = ""
    
    # Content Safety
    scene_direction: Optional[dict] = None

@dataclass
class QuestSeedPromptContext:
    """quest_service가 조립하여 NarrativeService에 전달."""
    seed_type: str = ""
    seed_tier: int = 3
    context_tags: list[str] = field(default_factory=list)
    npc_name: str = ""
    npc_role: str = ""
    npc_hexaco_summary: str = ""
    region_info: str = ""
    existing_seeds: list[str] = field(default_factory=list)

@dataclass
class NarrativeResult:
    narrative: str
    raw_meta: dict
    parse_success: bool
    actual_narration_level: Optional[str] = None
```

### C-5. `src/services/narrative_parser.py` (신규)

narrative-service.md 섹션 5 기반.

```python
"""LLM 응답 파싱 — narrative + META 분리"""
import json
import re
import logging

logger = logging.getLogger(__name__)

class ResponseParser:
    """LLM 응답 파싱"""

    def parse_dual(self, raw: str) -> tuple[str, dict, bool]:
        """narrative + meta 이중 구조 파싱.
        
        Returns:
            (narrative, meta, parse_success)
        
        파싱 단계:
        1. 전체 JSON 시도 → json.loads()
        2. ```json ... ``` 블록 추출 시도
        3. 실패 → (raw 전체, {}, False)
        """

    def parse_text(self, raw: str) -> str:
        """text only 응답. 그대로 반환. 앞뒤 공백 strip."""
```

구현 시 주의:
- JSON 추출에 정규표현식 사용: `` ```json\s*(.*?)\s*``` `` (re.DOTALL)
- parsed에서 "narrative" 키 없으면 raw 전체를 narrative로
- parsed에서 "meta" 키 없으면 빈 dict

### C-6. `src/services/narrative_safety.py` (신규)

narrative-service.md 섹션 6 기반. Alpha MVP에서는 최소 구현.

```python
"""Content-Safety 연동 — 묘사 레벨 관리 + 폴백"""
import logging

logger = logging.getLogger(__name__)

NARRATION_LEVELS = {
    "explicit": "詳細に描写せよ。",
    "moderate": "暗示的に描写し、直接的表現は避けよ。",
    "fade_out": "行為開始を1文で暗示し、場面転換せよ。",
}

FALLBACK_ORDER = ["explicit", "moderate", "fade_out", "template"]

class NarrationManager:
    """카테고리별 묘사 레벨 캐시"""

    def __init__(self, default_level: str = "moderate"):
        self.default_level = default_level
        self.effective_levels: dict[str, str] = {}

    def get_start_level(self, category: str) -> str:
        return self.effective_levels.get(category, self.default_level)

    def record_fallback(self, category: str, used_level: str) -> None:
        self.effective_levels[category] = used_level


class ContentSafetyFilter:
    """Content-Safety 필터 (Alpha 최소 구현)"""

    def __init__(self, narration_manager: NarrationManager):
        self._manager = narration_manager

    def get_scene_direction_prompt(self, scene_direction: dict | None) -> str:
        """scene_direction → 프롬프트 삽입 문자열.
        None이면 빈 문자열."""
```

### C-7. `src/services/narrative_prompts.py` (신규)

narrative-service.md 섹션 4 기반. 호출 유형별 프롬프트 조립.

```python
"""호출 유형별 프롬프트 빌더"""
import logging
from .narrative_types import (
    BuiltPrompt, DialoguePromptContext, QuestSeedPromptContext, NarrativeConfig
)
from .narrative_safety import ContentSafetyFilter

logger = logging.getLogger(__name__)

class PromptBuilder:
    def __init__(self, config: NarrativeConfig, safety: ContentSafetyFilter):
        self._config = config
        self._safety = safety

    def build_look(self, node_data: dict, player_state: dict) -> BuiltPrompt:
        """look 프롬프트. max_tokens=300."""

    def build_move(self, from_node: dict, to_node: dict, direction: str) -> BuiltPrompt:
        """move 프롬프트. max_tokens=150."""

    def build_dialogue(self, ctx: DialoguePromptContext) -> BuiltPrompt:
        """대화 프롬프트 (가장 복잡).
        
        조립 순서:
        1. System: 역할 + META 스키마 + 출력 규칙 + 행동 규칙 + scene_direction
        2. User: NPC Context → Session Context → Turn Context → History → Current Input
        
        max_tokens: DIALOGUE_TOKEN_MAP[budget_phase]
        expect_json: True
        """

    def build_quest_seed(self, ctx: QuestSeedPromptContext) -> BuiltPrompt:
        """퀘스트 시드 프롬프트. max_tokens=400. expect_json=True."""

    def build_impression_tag(self, summary: str, quest_result: dict | None) -> BuiltPrompt:
        """NPC 한줄평 프롬프트. max_tokens=50."""
```

대화 프롬프트 빌드 시 `DIALOGUE_TOKEN_MAP`:
```python
DIALOGUE_TOKEN_MAP = {
    "open": 500,
    "winding": 400,
    "closing": 300,
    "final": 200,
}
```

**프롬프트 텍스트**: narrative-service.md 섹션 4.2~4.5의 프롬프트 예시를 그대로 사용한다. 게임 출력 언어는 일본어이므로 프롬프트도 일본어로 작성한다.

### C-8. `src/services/narrative_service.py` 리팩터

기존 파일을 v2.0 구조로 리팩터한다.

**핵심 변경**:
- `__init__`에 PromptBuilder, ResponseParser, NarrationManager, ContentSafetyFilter 추가
- 기존 `generate_look()`, `generate_move()` 로직을 PromptBuilder 경유로 변경
- 신규 메서드 추가: `generate_dialogue_response()`, `generate_quest_seed()`, `generate_impression_tag()`
- 내부 `_call_llm()` 공통 메서드 추가 (폴백 체인 포함)
- 기존 `generate_narrative()` 메서드가 있다면 `generate_look()`으로 이름 변경 (하위 호환 주의)

**기존 코드를 먼저 읽고** 변경 범위를 최소화할 것. 기존 테스트가 깨지면 안 된다.

```python
class NarrativeService:
    def __init__(self, ai_provider: AIProvider, config: NarrativeConfig | None = None):
        self._ai = ai_provider
        self._config = config or NarrativeConfig()
        self._narration_manager = NarrationManager(self._config.default_narration_level)
        self._safety = ContentSafetyFilter(self._narration_manager)
        self._prompt_builder = PromptBuilder(self._config, self._safety)
        self._parser = ResponseParser()

    # 기존 (호환 유지)
    async def generate_look(self, node_data: dict, player_state: dict) -> str: ...
    async def generate_move(self, from_node: dict, to_node: dict, direction: str) -> str: ...

    # 신규
    async def generate_dialogue_response(self, ctx: DialoguePromptContext) -> NarrativeResult: ...
    async def generate_quest_seed(self, ctx: QuestSeedPromptContext) -> NarrativeResult: ...
    async def generate_impression_tag(self, summary: str, quest_result: dict | None = None) -> str: ...

    # 내부
    async def _call_llm(
        self, request_type: NarrativeRequestType, prompt: str,
        system_prompt: str, max_tokens: int, expect_json: bool = False
    ) -> str: ...
```

폴백 체인 (`_call_llm` 내부):
```
1단계: 통상 호출 → 성공 시 반환
2단계: 간소화 프롬프트 재시도 → 성공 시 반환
3단계: Python 템플릿 반환
```

폴백 템플릿:
```python
FALLBACK_TEMPLATES = {
    NarrativeRequestType.LOOK: "あなたは{node_name}にいる。周囲を見渡す。",
    NarrativeRequestType.MOVE: "{direction}に進む。",
    NarrativeRequestType.DIALOGUE: '{{"narrative": "{npc_name}が短く答える。「...そうだな。」", "meta": {{"dialogue_state": {{"wants_to_continue": true, "end_conversation": false, "topic_tags": []}}, "relationship_delta": {{"affinity": 0, "reason": "none"}}, "memory_tags": []}}}}',
    NarrativeRequestType.QUEST_SEED: None,
    NarrativeRequestType.IMPRESSION_TAG: "neutral",
}
```

### C-9. 테스트: `tests/services/test_narrative_service_v2.py`

```
테스트 항목:
1. ResponseParser.parse_dual — 정상 JSON
2. ResponseParser.parse_dual — ```json 블록
3. ResponseParser.parse_dual — 파싱 실패 → (raw, {}, False)
4. ResponseParser.parse_text — 정상
5. NarrationManager — 기본 레벨, 폴백 기록
6. PromptBuilder.build_dialogue — DialoguePromptContext → BuiltPrompt (expect_json=True)
7. PromptBuilder.build_quest_seed — expect_json=True
8. PromptBuilder.build_impression_tag — max_tokens=50
9. NarrativeService.generate_dialogue_response — MockProvider로 정상 흐름
10. NarrativeService.generate_impression_tag — MockProvider로 정상 흐름
11. NarrativeService.generate_look — 기존 호환 (리그레션)
12. NarrativeService._call_llm — 폴백 체인 (Provider 실패 시 템플릿 반환)
```

최소 12개 테스트 케이스. **MockProvider 사용**. 실제 LLM 호출 없음.

### C-10. 기존 테스트 호환

기존 `tests/` 에 narrative_service 관련 테스트가 있다면, 시그니처 변경에 맞춰 수정한다. **기존 테스트를 삭제하지 말고 수정**할 것.

## 검증
- `ruff check src/ tests/`
- `pytest tests/services/test_narrative_service_v2.py -v`
- `pytest -v` (전체 테스트 통과 — 기존 테스트 포함)

---

# #10-D: Dialogue Service (DB + EventBus)

## 목적
대화 세션 생명주기 관리, DB 영속화, EventBus 통신, NarrativeService 호출 통합

## 참조 문서
- `docs/20_design/dialogue-system.md` — 섹션 3(생명주기), 섹션 8(EventBus)
- `docs/30_technical/narrative-service.md` — 섹션 9.1(호출 흐름)
- `docs/30_technical/db-schema-v2.md` — dialogue_sessions, dialogue_turns 테이블
- `src/db/models_v2.py` — DialogueSessionModel, DialogueTurnModel 확인
- `src/services/npc_service.py` — 참고: Service 패턴
- `src/services/relationship_service.py` — 참고: EventBus 연동 패턴

## 산출물

### D-1. `src/services/dialogue_service.py` (신규)

```python
"""대화 세션 관리 Service — Core↔DB 연결, EventBus 통신"""
import logging
import uuid
from sqlalchemy.orm import Session

from src.core.dialogue.models import DialogueSession, DialogueTurn
from src.core.dialogue.budget import calculate_budget, get_budget_phase, get_phase_instruction
from src.core.dialogue.validation import validate_meta
from src.core.dialogue.constraints import validate_action_interpretation
from src.core.dialogue.hexaco_descriptors import hexaco_to_natural_language
from src.core.event_bus import EventBus
from src.core.event_types import EventTypes
from src.db.models_v2 import DialogueSessionModel, DialogueTurnModel
from src.services.narrative_service import NarrativeService
from src.services.narrative_types import DialoguePromptContext, NarrativeResult

logger = logging.getLogger(__name__)

class DialogueService:
    """대화 세션 관리"""

    def __init__(
        self,
        db: Session,
        event_bus: EventBus,
        narrative_service: NarrativeService,
    ):
        self._db = db
        self._bus = event_bus
        self._narrative = narrative_service
        self._active_session: DialogueSession | None = None
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독 등록"""
        self._bus.subscribe(EventTypes.ATTITUDE_RESPONSE, self._on_attitude_response)
        self._bus.subscribe(EventTypes.QUEST_SEED_GENERATED, self._on_quest_seed_generated)
        # check_result는 Alpha에서 미구현, 예비 구독만

    # === 공개 API ===

    async def start_session(
        self,
        player_id: str,
        npc_id: str,
        node_id: str,
        game_turn: int,
        # 호출자가 조립한 NPC/관계/기억 데이터
        npc_data: dict,
        relationship_data: dict,
        npc_memories: list[str],
        pc_constraints: dict,
    ) -> DialogueSession:
        """대화 세션 시작.
        
        1. 예산 계산
        2. dialogue_started 발행 → quest 시드 판정, attitude 수신
        3. DialogueSession 생성
        4. DB에 세션 레코드 생성
        """

    async def process_turn(
        self,
        pc_input: str,
    ) -> dict:
        """대화 턴 1회 처리.
        
        Returns:
            {"narrative": str, "session_status": str, "turn_index": int}
        
        흐름:
        1. budget_phase 계산
        2. PC 종료 의사 감지 (간단한 키워드: "bye", "goodbye", "じゃあ", "さよなら" 등)
        3. DialoguePromptContext 조립
        4. narrative_service.generate_dialogue_response(ctx) 호출
        5. META 검증 (validate_meta + validate_action_interpretation)
        6. 누적 delta 갱신
        7. 종료 판정
        8. DialogueTurn 저장 (DB)
        9. budget 차감
        """

    async def end_session(self, reason: str = "ended_by_pc") -> dict:
        """세션 종료 + 일괄 처리.
        
        Returns:
            {"session_id": str, "total_turns": int, "affinity_delta": float, ...}
        
        흐름:
        1. 누적 delta 감쇠 곡선 적용 (relationship_system의 damping과 별개, 
           여기서는 단순 합산 전달. 감쇠는 relationship_service 책임)
        2. dialogue_ended 이벤트 발행 (accumulated_deltas, memory_tags, seed_result 포함)
        3. DB 세션 레코드 갱신 (status, ended_turn, total_affinity_delta 등)
        4. active_session 해제
        """

    def get_active_session(self) -> DialogueSession | None:
        """현재 활성 세션 반환"""
        return self._active_session

    # === EventBus 핸들러 ===

    def _on_attitude_response(self, event) -> None:
        """태도 태그 수신 → 활성 세션의 npc_context에 반영"""

    def _on_quest_seed_generated(self, event) -> None:
        """퀘스트 시드 수신 → 활성 세션에 시드 주입"""

    # === 내부 ===

    def _build_prompt_context(self, pc_input: str) -> DialoguePromptContext:
        """활성 세션 데이터 → DialoguePromptContext 조립"""

    def _check_pc_end_intent(self, pc_input: str) -> bool:
        """PC 종료 의사 간단 감지 (키워드 기반)"""

    def _check_npc_end_intent(self, validated_meta: dict) -> bool:
        """META의 end_conversation, wants_to_continue 확인"""

    # === ORM ↔ Core 변환 ===

    def _session_to_orm(self, session: DialogueSession) -> DialogueSessionModel:
        """Core → ORM"""

    def _turn_to_orm(self, turn: DialogueTurn, session_id: str) -> DialogueTurnModel:
        """Core → ORM"""
```

**주의 사항**:
- DialogueService는 NarrativeService를 **DI로 주입**받는다. 이것은 Service→Service 직접 호출이 아니라, NarrativeService가 공유 인프라(LLM 관문)이므로 허용된다.
- 다른 도메인 서비스(npc_service, relationship_service)는 직접 호출하지 않는다. 필요한 데이터는 **모듈(#10-E)이 조립하여 start_session에 전달**한다.

### D-2. 테스트: `tests/services/test_dialogue_service.py`

```
테스트 항목:
1. start_session — 세션 생성, 예산 계산, DB 레코드 생성
2. start_session — dialogue_started 이벤트 발행 확인
3. process_turn — 정상 대화 턴 (MockProvider)
4. process_turn — budget 차감 + phase 전환
5. process_turn — PC 종료 의사 감지
6. process_turn — NPC 종료 의사 (end_conversation: true)
7. process_turn — budget 0 → 하드 종료
8. end_session — dialogue_ended 이벤트 발행 (delta, memory_tags 포함)
9. end_session — DB 갱신
10. _on_attitude_response — 태도 태그 반영
11. _on_quest_seed_generated — 시드 주입
12. 시드 전달 시나리오 — seed_delivered 추적
```

최소 12개 테스트 케이스. MockProvider + in-memory SQLite 사용.

## 검증
- `ruff check src/ tests/`
- `pytest tests/services/test_dialogue_service.py -v`
- `pytest -v`

---

# #10-E: DialogueModule 래핑 + API

## 목적
DialogueService를 GameModule 인터페이스로 래핑하고, API 엔드포인트 추가

## 참조 문서
- `docs/20_design/dialogue-system.md` — 섹션 1.3(모듈 위치), 섹션 8(EventBus)
- `src/modules/npc/module.py` — 참고: 모듈 래핑 패턴
- `src/modules/relationship/module.py` — 참고: 모듈 래핑 패턴
- `src/modules/base.py` — GameModule, GameContext, Action
- `src/api/game.py` — 기존 API 라우터

## 산출물

### E-1. `src/modules/dialogue/__init__.py`

패키지 초기화.

### E-2. `src/modules/dialogue/module.py`

```python
"""DialogueModule — GameModule 인터페이스"""
import logging
from src.modules.base import GameModule, GameContext, Action
from src.services.dialogue_service import DialogueService

logger = logging.getLogger(__name__)

class DialogueModule(GameModule):
    name = "dialogue"
    dependencies = ["npc_core", "relationship"]

    def __init__(self, dialogue_service: DialogueService):
        self._service = dialogue_service

    def on_enable(self, event_bus) -> None:
        """EventBus 구독은 DialogueService가 이미 처리"""
        pass

    def on_disable(self) -> None:
        pass

    def on_turn(self, context: GameContext) -> None:
        """대화 중에는 다른 모듈의 턴이 처리되지 않으므로, 여기서는 아무것도 안 함"""
        pass

    def on_node_enter(self, context: GameContext) -> None:
        """노드 진입 시 대화 가능 NPC 정보를 context.extra에 추가"""
        # npc_core 모듈이 이미 context.extra["npc_core"]에 NPC 목록을 넣음
        # dialogue 모듈은 대화 가능 상태(active_session 없음)만 표시
        context.extra["dialogue"] = {
            "active_session": self._service.get_active_session() is not None,
        }

    def get_available_actions(self, context: GameContext) -> list[Action]:
        """talk 액션 반환 (활성 세션 없을 때만)"""
        if self._service.get_active_session() is not None:
            # 대화 중: say, end_talk 액션
            return [
                Action(name="say", display_name="Say", module_name="dialogue",
                       description="대화 중 발언", params={"text": "str"}),
                Action(name="end_talk", display_name="End Talk", module_name="dialogue",
                       description="대화 종료"),
            ]
        else:
            return [
                Action(name="talk", display_name="Talk", module_name="dialogue",
                       description="NPC와 대화 시작", params={"npc_id": "str"}),
            ]
```

### E-3. `src/api/game.py` 확장

기존 game.py에 대화 관련 액션 핸들링을 추가한다.

**talk 액션**: `POST /game/action` 에서 `action: "talk"` 처리
```python
# action == "talk"
# params: {"npc_id": "..."}
# → DialogueModule 경유 → DialogueService.start_session()
# → 첫 턴은 NPC 인사 (자동 생성) 또는 PC 입력 대기
```

**say 액션**: `POST /game/action` 에서 `action: "say"` 처리
```python
# action == "say"
# params: {"text": "..."}
# → DialogueService.process_turn(text)
# → narrative 반환
```

**end_talk 액션**: `POST /game/action` 에서 `action: "end_talk"` 처리
```python
# → DialogueService.end_session("ended_by_pc")
```

**구현 방식**: 기존 game.py의 액션 디스패치 구조를 확인하고, 같은 패턴으로 추가한다. 구조가 if-elif 체인이면 그대로 확장. 별도 핸들러 패턴이면 그에 맞춤.

### E-4. `src/main.py` 수정

lifespan에서 DialogueService, DialogueModule 초기화 + ModuleManager 등록.

```python
# 기존 NarrativeService 초기화 이후에:
dialogue_service = DialogueService(
    db=session,
    event_bus=module_manager.event_bus,
    narrative_service=narrative_service,
)
dialogue_module = DialogueModule(dialogue_service)
module_manager.register(dialogue_module)
module_manager.enable("dialogue")
```

**기존 초기화 코드를 먼저 읽고** 패턴을 맞출 것. NarrativeService 초기화가 변경되었으므로 (NarrativeConfig 추가) main.py도 맞춰야 한다.

### E-5. SRC_INDEX.md 최종 갱신

#10 시리즈에서 추가/수정된 모든 파일을 SRC_INDEX.md에 반영:

```
# 추가 항목:
core/dialogue/__init__.py
core/dialogue/models.py
core/dialogue/budget.py
core/dialogue/hexaco_descriptors.py
core/dialogue/validation.py
core/dialogue/constraints.py
services/narrative_types.py
services/narrative_prompts.py
services/narrative_parser.py
services/narrative_safety.py
services/dialogue_service.py
modules/dialogue/__init__.py
modules/dialogue/module.py

# 수정 항목:
services/ai/base.py (시그니처 변경)
services/ai/mock.py (시그니처 + mock dialogue 응답)
services/ai/gemini.py (시그니처 + system_prompt)
services/narrative_service.py (v2 리팩터)
core/event_types.py (대화 이벤트 추가)
api/game.py (talk/say/end_talk 액션)
main.py (DialogueService/Module 초기화)
```

의존 흐름 요약에도 추가:
```
modules/dialogue/module.py → services/dialogue_service.py → core/dialogue/* + services/narrative_service.py + db/models_v2.py
```

### E-6. 테스트: `tests/modules/dialogue/test_dialogue_module.py`

```
테스트 항목:
1. DialogueModule 생성 + 의존성 확인 (["npc_core", "relationship"])
2. get_available_actions — 세션 없을 때: talk
3. get_available_actions — 세션 있을 때: say, end_talk
4. on_node_enter — context.extra["dialogue"] 설정
```

### E-7. 테스트: `tests/api/test_dialogue_api.py`

```
테스트 항목:
1. POST /game/action {action: "talk", params: {npc_id: "..."}} → 세션 시작
2. POST /game/action {action: "say", params: {text: "..."}} → 대화 턴
3. POST /game/action {action: "end_talk"} → 세션 종료
4. talk → 존재하지 않는 NPC → 에러
5. say → 활성 세션 없을 때 → 에러
6. 전체 대화 시나리오 (start → say × 3 → end_talk) 통합 테스트
```

최소 6개 API 테스트 케이스. TestClient + in-memory SQLite + MockProvider.

## 검증
- `ruff check src/ tests/`
- `pytest -v` (전체 테스트 통과)
- `pytest --cov` (커버리지 70%+)

---

# 블록 실행 요약

| 순서 | 블록 | 핵심 산출물 | 예상 테스트 수 |
|------|------|------------|--------------|
| 1 | #10-0 | 메타 정비, event_types 갱신 | 0 (기존 통과) |
| 2 | #10-A | core/dialogue/ (models, budget, hexaco_desc) | 12+ |
| 3 | #10-B | core/dialogue/ (validation, constraints) | 13+ |
| 4 | #10-C | services/ (narrative v2 확장 — types, parser, safety, prompts, service 리팩터) | 12+ |
| 5 | #10-D | services/dialogue_service.py | 12+ |
| 6 | #10-E | modules/dialogue/, API, main.py, SRC_INDEX | 10+ |
| **합계** | | | **59+** |

투입 순서: **0 → A → B → C → D → E**. 각 블록 완료 후 `pytest -v` 통과 확인 후 다음 진행.
