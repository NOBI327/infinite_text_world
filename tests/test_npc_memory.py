"""NPC 기억 시스템 테스트"""

from src.core.npc.memory import (
    NPCMemory,
    assign_tier1_slot,
    create_memory,
    enforce_tier2_capacity,
    get_memories_for_context,
)


# ── importance 자동 할당 ─────────────────────────────────────


def test_importance_auto_assign():
    """memory_type='betrayal' → importance=0.95"""
    mem = create_memory(
        npc_id="npc-1",
        memory_type="betrayal",
        summary="플레이어가 약속을 어겼다.",
        turn=10,
    )
    assert mem.importance == 0.95
    assert mem.memory_type == "betrayal"


def test_create_memory_defaults():
    """기본값 확인 (valence=0.0, tier=2 등)"""
    mem = create_memory(
        npc_id="npc-1",
        memory_type="encounter",
        summary="처음 만났다.",
        turn=1,
    )
    assert mem.emotional_valence == 0.0
    assert mem.tier == 2
    assert mem.is_fixed is False
    assert mem.fixed_slot is None
    assert mem.importance == 0.2


# ── Tier 1 고정 슬롯 ─────────────────────────────────────────


def test_tier1_fixed_slots():
    """고정 슬롯(1,2)은 교체 불가"""
    # 고정 슬롯 1, 2가 채워진 상태
    fixed1 = NPCMemory(
        memory_id="m-1",
        npc_id="npc-1",
        tier=1,
        memory_type="encounter",
        summary="첫 조우",
        turn_created=1,
        importance=0.5,
        is_fixed=True,
        fixed_slot=1,
    )
    fixed2 = NPCMemory(
        memory_id="m-2",
        npc_id="npc-1",
        tier=1,
        memory_type="combat",
        summary="첫 고임팩트",
        turn_created=2,
        importance=0.9,
        is_fixed=True,
        fixed_slot=2,
    )
    rotating1 = NPCMemory(
        memory_id="m-3",
        npc_id="npc-1",
        tier=1,
        memory_type="favor",
        summary="호의",
        turn_created=3,
        importance=0.8,
    )

    tier1_memories = [fixed1, fixed2, rotating1]

    # 새 고임팩트 기억 추가 (교체 슬롯 여유 있음)
    new_mem = NPCMemory(
        memory_id="m-4",
        npc_id="npc-1",
        tier=2,
        memory_type="betrayal",
        summary="배신",
        turn_created=5,
        importance=0.95,
    )
    evicted = assign_tier1_slot(tier1_memories, new_mem)

    # 고정 슬롯은 건드리지 않고, 교체 슬롯에 빈자리가 있어 강등 없음
    assert evicted is None
    assert new_mem.tier == 1
    assert fixed1.is_fixed is True
    assert fixed2.is_fixed is True


# ── Tier 1 교체 ──────────────────────────────────────────────


def test_tier1_replacement():
    """교체 슬롯 3개 꽉 찬 상태에서 새 기억 → 가장 오래된 것 반환"""
    fixed1 = NPCMemory(
        memory_id="m-1",
        npc_id="npc-1",
        tier=1,
        memory_type="encounter",
        summary="첫 조우",
        turn_created=1,
        importance=0.5,
        is_fixed=True,
        fixed_slot=1,
    )
    fixed2 = NPCMemory(
        memory_id="m-2",
        npc_id="npc-1",
        tier=1,
        memory_type="combat",
        summary="첫 고임팩트",
        turn_created=2,
        importance=0.9,
        is_fixed=True,
        fixed_slot=2,
    )
    rot1 = NPCMemory(
        memory_id="m-3",
        npc_id="npc-1",
        tier=1,
        memory_type="favor",
        summary="호의1",
        turn_created=10,
        importance=0.8,
    )
    rot2 = NPCMemory(
        memory_id="m-4",
        npc_id="npc-1",
        tier=1,
        memory_type="favor",
        summary="호의2",
        turn_created=20,
        importance=0.85,
    )
    rot3 = NPCMemory(
        memory_id="m-5",
        npc_id="npc-1",
        tier=1,
        memory_type="combat",
        summary="전투",
        turn_created=30,
        importance=0.9,
    )

    tier1_memories = [fixed1, fixed2, rot1, rot2, rot3]

    new_mem = NPCMemory(
        memory_id="m-6",
        npc_id="npc-1",
        tier=2,
        memory_type="betrayal",
        summary="배신",
        turn_created=40,
        importance=0.95,
    )
    evicted = assign_tier1_slot(tier1_memories, new_mem)

    # rot1 (turn=10, 가장 오래된 교체 슬롯)이 밀려남
    assert evicted is not None
    assert evicted.memory_id == "m-3"
    assert evicted.tier == 2  # Tier 2로 강등됨
    assert new_mem.tier == 1


# ── Tier 2 용량 ──────────────────────────────────────────────


def test_tier2_capacity_stranger():
    """stranger → 상한 3, 4개 기억 시 1개 강등 대상"""
    memories = [
        NPCMemory(
            memory_id=f"m-{i}",
            npc_id="npc-1",
            tier=2,
            memory_type="encounter",
            summary=f"기억 {i}",
            turn_created=i,
        )
        for i in range(4)
    ]

    demoted = enforce_tier2_capacity(memories, "stranger")
    assert len(demoted) == 1
    # 가장 오래된 것(turn=0)이 강등
    assert demoted[0].memory_id == "m-0"
    assert demoted[0].tier == 3


def test_tier2_capacity_friend():
    """friend → 상한 15, 4개 기억은 초과하지 않음"""
    memories = [
        NPCMemory(
            memory_id=f"m-{i}",
            npc_id="npc-1",
            tier=2,
            memory_type="encounter",
            summary=f"기억 {i}",
            turn_created=i,
        )
        for i in range(4)
    ]

    demoted = enforce_tier2_capacity(memories, "friend")
    assert len(demoted) == 0


# ── 컨텍스트 기억 선택 ───────────────────────────────────────


def test_get_memories_for_context():
    """Tier 1+2만 반환, Tier 3 제외"""
    m1 = NPCMemory(
        memory_id="m-1",
        npc_id="npc-1",
        tier=1,
        memory_type="encounter",
        summary="T1",
        turn_created=1,
        is_fixed=True,
        fixed_slot=1,
    )
    m2 = NPCMemory(
        memory_id="m-2",
        npc_id="npc-1",
        tier=2,
        memory_type="trade",
        summary="T2",
        turn_created=5,
    )
    m3 = NPCMemory(
        memory_id="m-3",
        npc_id="npc-1",
        tier=3,
        memory_type="encounter",
        summary="T3 archived",
        turn_created=2,
    )

    result = get_memories_for_context([m1, m2, m3])

    assert len(result) == 2
    assert all(m.tier in (1, 2) for m in result)
    # turn_created 오름차순
    assert result[0].turn_created <= result[1].turn_created
