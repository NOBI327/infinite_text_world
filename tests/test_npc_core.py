"""NPC Core 도메인 모델, HEXACO, 톤 태그 테스트"""

from src.core.npc.models import (
    BackgroundEntity,
    EntityType,
    HEXACO,
)
from src.core.npc.hexaco import (
    ROLE_HEXACO_TEMPLATES,
    generate_hexaco,
    get_behavior_modifier,
)
from src.core.npc.tone import (
    calculate_emotion,
    derive_manner_tags,
)


# ── EntityType ────────────────────────────────────────────────


def test_entity_type_enum():
    """EntityType 3종 값 확인"""
    assert EntityType.RESIDENT == "resident"
    assert EntityType.WANDERER == "wanderer"
    assert EntityType.HOSTILE == "hostile"
    assert len(EntityType) == 3


# ── BackgroundEntity ──────────────────────────────────────────


def test_background_entity_creation():
    """BackgroundEntity 기본 생성"""
    entity = BackgroundEntity(
        entity_id="e-001",
        entity_type=EntityType.RESIDENT,
        current_node="3_5",
        home_node="3_5",
        role="innkeeper",
    )
    assert entity.entity_id == "e-001"
    assert entity.entity_type == EntityType.RESIDENT
    assert entity.promotion_score == 0
    assert entity.promoted is False
    assert entity.slot_id is None


# ── HEXACO 생성 ───────────────────────────────────────────────


def test_hexaco_generate_with_seed():
    """동일 seed -> 동일 결과"""
    h1 = generate_hexaco("innkeeper", seed=42)
    h2 = generate_hexaco("innkeeper", seed=42)
    assert h1 == h2


def test_hexaco_generate_clamp():
    """모든 값이 0.0~1.0 범위"""
    for role in list(ROLE_HEXACO_TEMPLATES) + ["unknown_role"]:
        for seed in range(100):
            hexaco = generate_hexaco(role, seed=seed)
            for factor in ("H", "E", "X", "A", "C", "O"):
                val = getattr(hexaco, factor)
                assert 0.0 <= val <= 1.0, f"{role} seed={seed} {factor}={val}"


def test_hexaco_known_role():
    """innkeeper 템플릿 기반 생성 확인 (X > 0.5 등)

    innkeeper 템플릿: X=0.8, A=0.7 — ±0.15 보정 후에도 높을 확률이 압도적.
    seed 고정으로 확인.
    """
    hexaco = generate_hexaco("innkeeper", seed=7)
    # X 기본 0.8 - 보정 범위 0.65~0.95 → 거의 항상 > 0.5
    assert hexaco.X > 0.5


def test_hexaco_unknown_role():
    """미등록 역할 -> 중립 0.5 기반"""
    hexaco = generate_hexaco("dragon_tamer", seed=0)
    # 중립 0.5 기준 ±0.15이므로 0.35~0.65 범위
    for factor in ("H", "E", "X", "A", "C", "O"):
        val = getattr(hexaco, factor)
        assert 0.35 <= val <= 0.65, f"{factor}={val} out of neutral range"


# ── 행동 수정자 ───────────────────────────────────────────────


def test_behavior_modifier_high():
    """H=0.8 -> lie_chance 낮음"""
    hexaco = HEXACO(H=0.8)
    lie_chance = get_behavior_modifier(hexaco, "H", "lie_chance")
    assert lie_chance == 0.05


def test_behavior_modifier_low():
    """H=0.2 -> lie_chance 높음"""
    hexaco = HEXACO(H=0.2)
    lie_chance = get_behavior_modifier(hexaco, "H", "lie_chance")
    assert lie_chance == 0.40


# ── 톤 태그 ───────────────────────────────────────────────────


def test_derive_manner_tags():
    """X=0.9 -> 'verbose', 'energetic' 포함"""
    hexaco = HEXACO(X=0.9)
    tags = derive_manner_tags(hexaco)
    assert "verbose" in tags
    assert "energetic" in tags


# ── 감정 계산 ─────────────────────────────────────────────────


def test_calculate_emotion_basic():
    """'betrayed' -> 'angry', intensity 높음"""
    hexaco = HEXACO()  # 중립
    emotion, intensity = calculate_emotion("betrayed", affinity=0.0, hexaco=hexaco)
    assert emotion == "angry"
    assert intensity >= 0.7


def test_calculate_emotion_hexaco_modulation():
    """A=0.8 -> angry 강도 약화"""
    hexaco_agreeable = HEXACO(A=0.8)
    hexaco_neutral = HEXACO(A=0.5)

    _, intensity_agreeable = calculate_emotion(
        "betrayed", affinity=0.0, hexaco=hexaco_agreeable
    )
    _, intensity_neutral = calculate_emotion(
        "betrayed", affinity=0.0, hexaco=hexaco_neutral
    )

    assert intensity_agreeable < intensity_neutral
