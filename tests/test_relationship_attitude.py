"""관계 → 태도 태그 파이프라인 테스트

지시서 #09-B 대응.
"""

from src.core.npc.models import HEXACO
from src.core.relationship.attitude import (
    apply_hexaco_modifiers,
    apply_memory_modifiers,
    generate_attitude_tags,
    generate_base_attitude,
)
from src.core.relationship.models import Relationship, RelationshipStatus
from src.core.relationship.npc_opinions import (
    build_npc_opinions,
    generate_npc_opinion_tags,
)


def _make_rel(**kwargs: object) -> Relationship:
    """테스트용 관계 팩토리"""
    defaults = {
        "relationship_id": "test-rel-001",
        "source_type": "player",
        "source_id": "player_001",
        "target_type": "npc",
        "target_id": "npc_test",
    }
    defaults.update(kwargs)
    return Relationship(**defaults)


# ── 1단계: 기본 태도 태그 ────────────────────────────────────


class TestBaseAttitude:
    def test_base_attitude_friendly(self) -> None:
        """affinity 35 → 'friendly'"""
        rel = _make_rel(affinity=35.0, trust=50.0)
        tags = generate_base_attitude(rel)
        assert "friendly" in tags

    def test_base_attitude_hostile(self) -> None:
        """affinity -60 → 'hostile'"""
        rel = _make_rel(affinity=-60.0, trust=10.0)
        tags = generate_base_attitude(rel)
        assert "hostile" in tags

    def test_base_attitude_trust_layers(self) -> None:
        """trust 70 → 'trusting'"""
        rel = _make_rel(affinity=0.0, trust=70.0)
        tags = generate_base_attitude(rel)
        assert "trusting" in tags


# ── 2단계: HEXACO 보정 ──────────────────────────────────────


class TestHexacoModifiers:
    def test_hexaco_reserved(self) -> None:
        """X=0.2, familiarity=3 → 'reserved' 추가"""
        rel = _make_rel(affinity=0.0, trust=50.0, familiarity=3)
        hexaco = HEXACO(X=0.2)
        tags = generate_base_attitude(rel)
        tags = apply_hexaco_modifiers(tags, hexaco, rel)
        assert "reserved" in tags

    def test_hexaco_chatty(self) -> None:
        """X=0.8, familiarity=10 → 'chatty' 추가"""
        rel = _make_rel(affinity=0.0, trust=50.0, familiarity=10)
        hexaco = HEXACO(X=0.8)
        tags = generate_base_attitude(rel)
        tags = apply_hexaco_modifiers(tags, hexaco, rel)
        assert "chatty" in tags

    def test_hexaco_confrontational(self) -> None:
        """A=0.2, affinity=-10 → 'confrontational' 추가"""
        rel = _make_rel(affinity=-10.0, trust=50.0)
        hexaco = HEXACO(A=0.2)
        tags = generate_base_attitude(rel)
        tags = apply_hexaco_modifiers(tags, hexaco, rel)
        assert "confrontational" in tags


# ── 3단계: 기억 보정 ────────────────────────────────────────


class TestMemoryModifiers:
    def test_memory_modifier(self) -> None:
        """memory_tags=['broke_promise'] → 'remembers_betrayal' 추가"""
        tags = ["neutral", "distrustful"]
        tags = apply_memory_modifiers(tags, ["broke_promise"])
        assert "remembers_betrayal" in tags

    def test_memory_modifier_duplicate(self) -> None:
        """동일 태그 중복 시 1개만"""
        tags = ["neutral", "distrustful", "remembers_betrayal"]
        tags = apply_memory_modifiers(tags, ["broke_promise"])
        assert tags.count("remembers_betrayal") == 1


# ── 전체 파이프라인 ──────────────────────────────────────────


class TestFullPipeline:
    def test_full_pipeline_tag_count(self) -> None:
        """최종 태그 수 2~7 범위 확인"""
        rel = _make_rel(
            affinity=35.0,
            trust=45.0,
            familiarity=8,
            status=RelationshipStatus.FRIEND,
        )
        hexaco = HEXACO(H=0.4, E=0.3, X=0.6, A=0.7, C=0.8, O=0.3)
        memory = ["paid_on_time", "paid_on_time", "discussed_weapon"]

        ctx = generate_attitude_tags(rel, hexaco, memory)
        assert 2 <= len(ctx.attitude_tags) <= 7

    def test_full_pipeline_example(self) -> None:
        """섹션 6.5의 대장장이 한스 예시 재현"""
        rel = _make_rel(
            target_id="npc_hans",
            affinity=35.0,
            trust=45.0,
            familiarity=8,
            status=RelationshipStatus.FRIEND,
        )
        hexaco = HEXACO(H=0.4, E=0.3, X=0.6, A=0.7, C=0.8, O=0.3)
        memory = ["paid_on_time", "paid_on_time", "discussed_weapon"]

        ctx = generate_attitude_tags(rel, hexaco, memory)

        expected = [
            "friendly",
            "cautious_trust",
            "respects_reliability",
            "reliable_customer",
        ]
        assert ctx.attitude_tags == expected
        assert ctx.target_npc_id == "npc_hans"
        assert ctx.relationship_status == "friend"


# ── NPC 의견 ────────────────────────────────────────────────


class TestNpcOpinions:
    def test_npc_opinion_fondly(self) -> None:
        """affinity 40 → 'speaks_fondly' 포함"""
        rel = _make_rel(
            source_type="npc",
            source_id="npc_a",
            target_id="npc_b",
            affinity=40.0,
            trust=50.0,
        )
        tags = generate_npc_opinion_tags(rel)
        assert "speaks_fondly" in tags

    def test_npc_opinion_distrustful(self) -> None:
        """trust 10 → 'distrustful' 포함"""
        rel = _make_rel(
            source_type="npc",
            source_id="npc_a",
            target_id="npc_b",
            affinity=0.0,
            trust=10.0,
        )
        tags = generate_npc_opinion_tags(rel)
        assert "distrustful" in tags

    def test_build_npc_opinions(self) -> None:
        """여러 관계 → 딕셔너리 구성 확인"""
        rels = [
            _make_rel(
                source_type="npc",
                source_id="npc_a",
                target_id="npc_b",
                affinity=40.0,
                trust=50.0,
            ),
            _make_rel(
                source_type="npc",
                source_id="npc_a",
                target_id="npc_c",
                affinity=-40.0,
                trust=10.0,
            ),
        ]
        opinions = build_npc_opinions("npc_a", rels)

        assert "npc_b" in opinions
        assert "npc_c" in opinions
        assert "speaks_fondly" in opinions["npc_b"]
        assert "distrustful" in opinions["npc_c"]
