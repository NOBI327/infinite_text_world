"""NPC 승격 시스템, 슬롯 관리, 명명 시스템 테스트"""

from src.core.npc.models import BackgroundEntity, EntityType, HEXACO
from src.core.npc.promotion import (
    PROMOTION_SCORE_TABLE,
    build_npc_from_entity,
    calculate_new_score,
    check_promotion_status,
)
from src.core.npc.slots import (
    calculate_slot_count,
    should_reset_slot,
)
from src.core.npc.naming import (
    NPCNameSeed,
    generate_name,
)


# ── 승격 점수 테이블 ─────────────────────────────────────────


def test_promotion_score_table():
    """전체 10종 행동 점수 확인"""
    expected = {
        "encounter": 5,
        "greet": 15,
        "conversation": 30,
        "trade": 20,
        "joint_combat": 40,
        "help": 35,
        "ask_name": 50,
        "combat_engaged": 20,
        "survived_combat": 15,
        "fled_combat": 25,
    }
    assert PROMOTION_SCORE_TABLE == expected
    assert len(PROMOTION_SCORE_TABLE) == 10


# ── 승격 상태 판정 ───────────────────────────────────────────


def test_check_promotion_status_none():
    """14점 → 'none'"""
    assert check_promotion_status(14) == "none"
    assert check_promotion_status(0) == "none"


def test_check_promotion_status_worldpool():
    """15점 → 'worldpool'"""
    assert check_promotion_status(15) == "worldpool"
    assert check_promotion_status(49) == "worldpool"


def test_check_promotion_status_promoted():
    """50점 → 'promoted'"""
    assert check_promotion_status(50) == "promoted"
    assert check_promotion_status(100) == "promoted"


# ── build_npc_from_entity ────────────────────────────────────


def test_build_npc_from_entity():
    """BackgroundEntity → NPCData 변환, 필드 매핑 확인"""
    entity = BackgroundEntity(
        entity_id="e-001",
        entity_type=EntityType.RESIDENT,
        current_node="3_5",
        home_node="3_5",
        role="innkeeper",
    )
    hexaco = HEXACO(H=0.6, E=0.5, X=0.8, A=0.7, C=0.5, O=0.5)

    npc = build_npc_from_entity(entity, hexaco)

    # npc_id는 Service 레이어에서 할당하므로 빈 문자열
    assert npc.npc_id == ""
    assert npc.home_node == "3_5"
    assert npc.current_node == "3_5"
    assert npc.origin_type == "promoted"
    assert npc.origin_entity_type == "resident"
    assert npc.role == "innkeeper"
    assert npc.hexaco == hexaco


# ── calculate_new_score ──────────────────────────────────────


def test_calculate_new_score():
    """점수 계산 순수 함수 테스트"""
    assert calculate_new_score(0, "encounter") == 5
    assert calculate_new_score(10, "greet") == 25
    assert calculate_new_score(10, "unknown_action") == 10  # 미등록 행동


# ── 슬롯 시스템 ──────────────────────────────────────────────


def test_slot_count_calculation():
    """inn → 4 + size 보정"""
    assert calculate_slot_count("inn", 0) == 4
    assert calculate_slot_count("inn", 2) == 5
    assert calculate_slot_count("inn", 4) == 6
    assert calculate_slot_count("inn", 5) == 6  # 5 // 2 = 2
    # 미등록 시설 → 기본 2
    assert calculate_slot_count("unknown_facility", 0) == 2


def test_should_reset_slot_protected():
    """promotion_score > 0 → False (보호)"""
    assert should_reset_slot(promotion_score=10, turns_since_reset=100) is False
    assert should_reset_slot(promotion_score=1, turns_since_reset=24) is False


def test_should_reset_slot_expired():
    """24턴 경과 → True"""
    assert should_reset_slot(promotion_score=0, turns_since_reset=24) is True
    assert should_reset_slot(promotion_score=0, turns_since_reset=30) is True
    # 경과 부족 → False
    assert should_reset_slot(promotion_score=0, turns_since_reset=23) is False


# ── 명명 시스템 ──────────────────────────────────────────────


def test_generate_name_with_seed():
    """동일 rng_seed → 동일 이름"""
    seed = NPCNameSeed(
        region_name="타르고스 영지",
        biome_descriptor="언덕",
        facility_type="smithy",
        role="blacksmith",
        gender="M",
    )
    name1 = generate_name(seed, rng_seed=42)
    name2 = generate_name(seed, rng_seed=42)
    assert name1.given_name == name2.given_name
    assert name1.occupation == name2.occupation


def test_generate_name_structure():
    """given_name, occupation 존재 확인"""
    seed = NPCNameSeed(
        region_name="타르고스 영지",
        biome_descriptor="언덕",
        facility_type="inn",
        role="innkeeper",
        gender="F",
    )
    name = generate_name(seed, rng_seed=7)
    assert name.given_name != ""
    assert name.occupation == "여관주인"
    assert name.facility_name == "여관"
    assert name.region_name == "타르고스 영지"
    assert name.gender == "F"
