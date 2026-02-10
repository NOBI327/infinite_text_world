"""NPC 기억 시스템

npc-system.md 섹션 10 대응.
Alpha: Tier 1 + Tier 2. Tier 3 (embedding)은 Alpha 후.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

# ── 중요도 초기값 테이블 (섹션 10.5) ────────────────────────

IMPORTANCE_TABLE: Dict[str, float] = {
    "encounter": 0.2,  # 단순 조우
    "conversation": 0.3,  # 일반 대화
    "trade": 0.4,  # 거래
    "favor": 0.6,  # 호의 제공/수령
    "combat": 0.7,  # 공동 전투
    "life_threat": 0.9,  # 생명 구함/위협
    "betrayal": 0.95,  # 배신/약속 파기
}

# ── 관계 단계별 Tier 2 상한 (섹션 10.3) ─────────────────────

TIER2_CAPACITY: Dict[str, int] = {
    "stranger": 3,
    "acquaintance": 7,
    "friend": 15,
    "ally": 20,
    "rival": 20,
}

# ── Tier 1 상수 ──────────────────────────────────────────────

TIER1_FIXED_COUNT = 2  # 고정 슬롯 (교체 불가)
TIER1_ROTATING_COUNT = 3  # 교체 슬롯
TIER1_TOTAL = TIER1_FIXED_COUNT + TIER1_ROTATING_COUNT  # 5
TIER1_HIGH_IMPACT_THRESHOLD = 0.8  # 고임팩트 기억 기준


@dataclass
class NPCMemory:
    """NPC 기억 (npc-system.md 섹션 10.4)

    Core 레이어용 순수 데이터 클래스. DB ORM(NPCMemoryModel)과 별개.
    """

    memory_id: str
    npc_id: str

    # 계층
    tier: int  # 1, 2, 3

    # 내용
    memory_type: str  # "encounter", "trade", "combat", "quest", "betrayal", "favor"
    summary: str  # 1-2문장 요약

    # 감정/중요도
    emotional_valence: float = 0.0  # -1.0 ~ +1.0
    importance: float = 0.0  # 0.0 ~ 1.0

    # 벡터 검색용 (Tier 3, Alpha 후)
    embedding: Optional[bytes] = None

    # 메타
    turn_created: int = 0
    related_node: Optional[str] = None
    related_entity_id: Optional[str] = None

    # Tier 1 고정 여부
    is_fixed: bool = False
    fixed_slot: Optional[int] = None  # 1 또는 2 (고정 슬롯 번호)


def create_memory(
    npc_id: str,
    memory_type: str,
    summary: str,
    turn: int,
    importance: Optional[float] = None,
    emotional_valence: float = 0.0,
    memory_id: str = "",
    related_node: Optional[str] = None,
    related_entity_id: Optional[str] = None,
) -> NPCMemory:
    """기억 생성. importance 미지정 시 IMPORTANCE_TABLE에서 자동 계산.

    Args:
        npc_id: 대상 NPC ID
        memory_type: 상호작용 유형 (IMPORTANCE_TABLE 키)
        summary: 기억 요약 (1-2문장)
        turn: 생성 턴
        importance: 명시적 중요도. None이면 memory_type 기반 자동 할당.
        emotional_valence: 감정 극성 (-1.0 ~ +1.0)
        memory_id: 기억 ID. 빈 문자열이면 Service에서 할당.
        related_node: 관련 노드 ID
        related_entity_id: 관련 엔티티 ID

    Returns:
        NPCMemory (tier=2 기본값. Tier 1 배치는 assign_tier1_slot()로 별도 처리.)
    """
    if importance is None:
        importance = IMPORTANCE_TABLE.get(memory_type, 0.3)

    return NPCMemory(
        memory_id=memory_id,
        npc_id=npc_id,
        tier=2,
        memory_type=memory_type,
        summary=summary,
        emotional_valence=emotional_valence,
        importance=importance,
        turn_created=turn,
        related_node=related_node,
        related_entity_id=related_entity_id,
    )


def assign_tier1_slot(
    memories: List[NPCMemory],
    new_memory: NPCMemory,
) -> Optional[NPCMemory]:
    """Tier 1 슬롯에 고임팩트 기억 배치 (섹션 10.2)

    규칙:
    - 고정 슬롯 1: 첫 조우 기억 (is_fixed=True, fixed_slot=1)
    - 고정 슬롯 2: 첫 고임팩트 기억 (is_fixed=True, fixed_slot=2)
    - 교체 슬롯 3~5: 최근 고임팩트 기억. 꽉 차면 가장 오래된 것 강등.

    Args:
        memories: 현재 해당 NPC의 Tier 1 기억 목록
        new_memory: 배치할 새 기억 (importance >= 0.8)

    Returns:
        밀려난 기억 (→ Tier 2로 강등 대상). 빈 슬롯이 있으면 None.
    """
    # 고정 슬롯 확인
    fixed_slots = {m.fixed_slot for m in memories if m.is_fixed}

    # 고정 슬롯 1 비어있으면 첫 조우 기억으로 배치
    if 1 not in fixed_slots:
        new_memory.tier = 1
        new_memory.is_fixed = True
        new_memory.fixed_slot = 1
        return None

    # 고정 슬롯 2 비어있고, 고임팩트면 배치
    if 2 not in fixed_slots and new_memory.importance >= TIER1_HIGH_IMPACT_THRESHOLD:
        new_memory.tier = 1
        new_memory.is_fixed = True
        new_memory.fixed_slot = 2
        return None

    # 고임팩트가 아니면 Tier 1에 넣지 않음
    if new_memory.importance < TIER1_HIGH_IMPACT_THRESHOLD:
        return None

    # 교체 슬롯 처리
    rotating = [m for m in memories if not m.is_fixed]

    if len(rotating) < TIER1_ROTATING_COUNT:
        # 빈 교체 슬롯 있음
        new_memory.tier = 1
        return None

    # 교체 슬롯 꽉 참 → 가장 오래된 것 강등
    oldest = min(rotating, key=lambda m: m.turn_created)
    oldest.tier = 2
    oldest.is_fixed = False
    oldest.fixed_slot = None

    new_memory.tier = 1
    return oldest


def enforce_tier2_capacity(
    memories: List[NPCMemory],
    relationship_status: str,
) -> List[NPCMemory]:
    """Tier 2 용량 초과 시 가장 오래된 것 → Tier 3 강등 (섹션 10.3)

    Args:
        memories: 해당 NPC의 Tier 2 기억 목록
        relationship_status: 관계 단계 ("stranger", "acquaintance", "friend", "ally", "rival")

    Returns:
        Tier 3로 강등할 기억 리스트.
    """
    capacity = TIER2_CAPACITY.get(relationship_status, 3)
    tier2 = [m for m in memories if m.tier == 2]

    if len(tier2) <= capacity:
        return []

    # 오래된 순 정렬 → 초과분 강등
    tier2_sorted = sorted(tier2, key=lambda m: m.turn_created)
    excess_count = len(tier2) - capacity
    demoted = tier2_sorted[:excess_count]

    for m in demoted:
        m.tier = 3

    return demoted


def get_memories_for_context(
    all_memories: List[NPCMemory],
    relationship_status: str = "stranger",
) -> List[NPCMemory]:
    """LLM 컨텍스트용 기억 선택 (Tier 1 전부 + Tier 2 전부, Tier 3 제외)

    Args:
        all_memories: NPC의 전체 기억 목록
        relationship_status: 현재 관계 단계 (사용 예약, 현재는 필터링에 미사용)

    Returns:
        Tier 1 + Tier 2 기억 목록. turn_created 오름차순 정렬.
    """
    context_memories = [m for m in all_memories if m.tier in (1, 2)]
    context_memories.sort(key=lambda m: m.turn_created)
    return context_memories
