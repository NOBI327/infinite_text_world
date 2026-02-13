"""NarrativeService 타입 정의

narrative-service.md 섹션 2.2, 3.1, 4.3, 4.4, 5.3 대응.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NarrativeRequestType(str, Enum):
    """LLM 호출 유형"""

    LOOK = "look"
    MOVE = "move"
    DIALOGUE = "dialogue"
    QUEST_SEED = "quest_seed"
    IMPRESSION_TAG = "impression_tag"


@dataclass
class NarrativeConfig:
    """NarrativeService 설정"""

    default_narration_level: str = "moderate"


@dataclass
class BuiltPrompt:
    """조립 완료된 프롬프트"""

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
    """이중 출력 (narrative + meta) 호출의 반환 타입"""

    narrative: str
    raw_meta: dict
    parse_success: bool
    actual_narration_level: Optional[str] = None
