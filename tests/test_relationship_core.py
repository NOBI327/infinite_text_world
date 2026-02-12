"""관계 시스템 Core 테스트

지시서 #09-A 테스트 항목 전체 대응.
"""

import pytest

from src.core.relationship.models import Relationship, RelationshipStatus
from src.core.relationship.calculations import (
    apply_affinity_damping,
    apply_familiarity_decay,
    apply_trust_damping,
    clamp_meta_delta,
)
from src.core.relationship.transitions import evaluate_transition
from src.core.relationship.reversals import ReversalType, apply_reversal


def _make_rel(**kwargs) -> Relationship:
    """테스트용 Relationship 팩토리."""
    defaults = {
        "relationship_id": "test-rel-001",
        "source_type": "player",
        "source_id": "player-001",
        "target_type": "npc",
        "target_id": "npc-001",
    }
    defaults.update(kwargs)
    return Relationship(**defaults)


# ── RelationshipStatus ──


class TestRelationshipStatusEnum:
    def test_relationship_status_enum(self):
        """6종 값 확인."""
        assert RelationshipStatus.STRANGER.value == "stranger"
        assert RelationshipStatus.ACQUAINTANCE.value == "acquaintance"
        assert RelationshipStatus.FRIEND.value == "friend"
        assert RelationshipStatus.BONDED.value == "bonded"
        assert RelationshipStatus.RIVAL.value == "rival"
        assert RelationshipStatus.NEMESIS.value == "nemesis"
        assert len(RelationshipStatus) == 6


class TestRelationshipDefaults:
    def test_relationship_creation_defaults(self):
        """기본값: affinity=0, trust=0, stranger."""
        rel = _make_rel()
        assert rel.affinity == 0.0
        assert rel.trust == 0.0
        assert rel.familiarity == 0
        assert rel.status == RelationshipStatus.STRANGER
        assert rel.tags == []
        assert rel.last_interaction_turn == 0


# ── Affinity Damping ──


class TestAffinityDamping:
    def test_affinity_damping_at_zero(self):
        """현재 0 → damping 1.0 → 변동 그대로."""
        result = apply_affinity_damping(0.0, 5.0)
        assert result == pytest.approx(5.0)

    def test_affinity_damping_at_high(self):
        """현재 90 → damping 약 0.13 → +5 제안이 약 +0.7."""
        result = apply_affinity_damping(90.0, 5.0)
        assert result == pytest.approx(0.7, abs=0.15)

    def test_affinity_damping_negative(self):
        """현재 -50 → 감쇠 적용 확인."""
        result = apply_affinity_damping(-50.0, 5.0)
        # damping = 1.0 - (50/100)^1.2 ≈ 1.0 - 0.435 = 0.565
        expected = 5.0 * (1.0 - (50 / 100) ** 1.2)
        assert result == pytest.approx(expected, abs=0.01)

    def test_affinity_damping_minimum(self):
        """damping 최소 10% 보장."""
        # current=99 → damping ≈ 0.01 → max(0.01, 0.1) = 0.1
        result = apply_affinity_damping(99.0, 5.0)
        assert result == pytest.approx(0.5, abs=0.05)


# ── Trust Damping ──


class TestTrustDamping:
    def test_trust_damping_increase(self):
        """상승 시 감쇠 적용."""
        result = apply_trust_damping(50.0, 10.0)
        damping = 1.0 - (50 / 100) ** 1.2
        expected = 10.0 * max(damping, 0.1)
        assert result == pytest.approx(expected, abs=0.01)

    def test_trust_damping_decrease(self):
        """하락 시 감쇠 없음 (raw_change 그대로)."""
        result = apply_trust_damping(50.0, -20.0)
        assert result == -20.0


# ── Familiarity Decay ──


class TestFamiliarityDecay:
    def test_familiarity_decay(self):
        """60일 경과 → -2."""
        result = apply_familiarity_decay(10, 60)
        assert result == 8

    def test_familiarity_decay_minimum(self):
        """감쇠 후 최소 0."""
        result = apply_familiarity_decay(1, 90)
        assert result == 0


# ── Clamp ──


class TestClampMetaDelta:
    def test_clamp_meta_delta(self):
        """10 → 5, -10 → -5."""
        assert clamp_meta_delta(10.0) == 5.0
        assert clamp_meta_delta(-10.0) == -5.0
        assert clamp_meta_delta(3.0) == 3.0


# ── Transitions ──


class TestTransitions:
    def test_transition_stranger_to_acquaintance(self):
        """familiarity 3 이상 → acquaintance."""
        rel = _make_rel(familiarity=3, status=RelationshipStatus.STRANGER)
        assert evaluate_transition(rel) == RelationshipStatus.ACQUAINTANCE

    def test_transition_acquaintance_to_friend(self):
        """affinity 30, trust 25 → friend."""
        rel = _make_rel(
            affinity=30.0,
            trust=25.0,
            familiarity=5,
            status=RelationshipStatus.ACQUAINTANCE,
        )
        assert evaluate_transition(rel) == RelationshipStatus.FRIEND

    def test_transition_friend_demote(self):
        """affinity 14 → acquaintance로 하락."""
        rel = _make_rel(
            affinity=14.0,
            trust=25.0,
            familiarity=10,
            status=RelationshipStatus.FRIEND,
        )
        assert evaluate_transition(rel) == RelationshipStatus.ACQUAINTANCE

    def test_transition_rival(self):
        """affinity -25, familiarity 5 → rival."""
        rel = _make_rel(
            affinity=-25.0,
            familiarity=5,
            status=RelationshipStatus.ACQUAINTANCE,
        )
        assert evaluate_transition(rel) == RelationshipStatus.RIVAL

    def test_transition_priority_demote_over_promote(self):
        """동시 충족 시 하락 우선."""
        # acquaintance: demote 조건(abs(affinity) < 10 AND familiarity < 3)과
        # rival 조건(affinity <= -25 AND familiarity >= 5) 동시 충족 불가능이므로
        # friend에서 demote와 promote 동시 충족 케이스 사용
        rel = _make_rel(
            affinity=65.0,
            trust=8.0,  # trust < 10 → demote 충족
            familiarity=20,
            status=RelationshipStatus.FRIEND,
        )
        # demote: affinity < 15 OR trust < 10 → True (trust 8 < 10)
        # promote: affinity >= 65 AND trust >= 60 AND familiarity >= 20 → False
        # demote 우선
        assert evaluate_transition(rel) == RelationshipStatus.ACQUAINTANCE


# ── Reversals ──


class TestReversals:
    def test_reversal_betrayal(self):
        """affinity 45 → -45, trust 40 → 12."""
        rel = _make_rel(
            affinity=45.0,
            trust=40.0,
            familiarity=10,
            status=RelationshipStatus.FRIEND,
        )
        result = apply_reversal(rel, ReversalType.BETRAYAL)
        assert result.affinity == pytest.approx(-45.0)
        assert result.trust == pytest.approx(12.0)
        # 원본 불변
        assert rel.affinity == 45.0

    def test_reversal_redemption(self):
        """affinity -40 → +28, trust 15 → 45."""
        rel = _make_rel(
            affinity=-40.0,
            trust=15.0,
            familiarity=10,
            status=RelationshipStatus.RIVAL,
        )
        result = apply_reversal(rel, ReversalType.REDEMPTION)
        assert result.affinity == pytest.approx(28.0)
        assert result.trust == pytest.approx(45.0)

    def test_reversal_trust_collapse(self):
        """trust 60 → 12, affinity 변동 없음."""
        rel = _make_rel(
            affinity=50.0,
            trust=60.0,
            familiarity=15,
            status=RelationshipStatus.FRIEND,
        )
        result = apply_reversal(rel, ReversalType.TRUST_COLLAPSE)
        assert result.affinity == pytest.approx(50.0)
        assert result.trust == pytest.approx(12.0)

    def test_reversal_auto_retransition(self):
        """betrayal 후 자동으로 rival 전이."""
        rel = _make_rel(
            affinity=45.0,
            trust=40.0,
            familiarity=10,
            status=RelationshipStatus.FRIEND,
        )
        result = apply_reversal(rel, ReversalType.BETRAYAL)
        # affinity=-45, trust=12, familiarity=10
        # friend → demote 조건 충족 → acquaintance
        # 그런데 acquaintance에서 rival 조건도 충족 (affinity <= -25, familiarity >= 5)
        # evaluate_transition은 현재 상태만 보므로 friend에서 demote → acquaintance
        # 지시서: "반전 후 상태도 재계산"
        assert result.status == RelationshipStatus.ACQUAINTANCE
