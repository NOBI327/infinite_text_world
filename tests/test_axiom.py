"""Tests for axiom_system module."""

import pytest

from src.core.axiom_system import AxiomLoader, AxiomVector, DomainType


@pytest.fixture()
def axiom_loader() -> AxiomLoader:
    """Load axioms from the data file."""
    return AxiomLoader("src/data/itw_214_divine_axioms.json")


class TestAxiomLoader:
    """Tests for AxiomLoader class."""

    def test_load_axioms(self, axiom_loader: AxiomLoader):
        """Test that axioms are loaded successfully from JSON."""
        all_axioms = axiom_loader.get_all()

        # Should have loaded axioms
        assert len(all_axioms) > 0

        # Check that axioms have required fields
        axiom = all_axioms[0]
        assert axiom.id is not None
        assert axiom.code is not None
        assert axiom.name_latin is not None
        assert axiom.name_kr is not None
        assert axiom.domain is not None
        assert axiom.resonance is not None
        assert axiom.tier in [1, 2, 3]

    def test_get_by_code(self, axiom_loader: AxiomLoader):
        """Test getting axiom by code."""
        # Get first axiom to know a valid code
        all_axioms = axiom_loader.get_all()
        first_axiom = all_axioms[0]

        # Query by code
        result = axiom_loader.get_by_code(first_axiom.code)

        assert result is not None
        assert result.code == first_axiom.code
        assert result.id == first_axiom.id

        # Non-existent code should return None
        result_none = axiom_loader.get_by_code("axiom_nonexistent_xyz")
        assert result_none is None

    def test_get_by_domain(self, axiom_loader: AxiomLoader):
        """Test filtering axioms by domain."""
        # Get axioms by domain
        primordial_axioms = axiom_loader.get_by_domain(DomainType.PRIMORDIAL)

        # Should have some axioms in PRIMORDIAL domain
        assert len(primordial_axioms) > 0

        # All returned axioms should be PRIMORDIAL
        for axiom in primordial_axioms:
            assert axiom.domain == DomainType.PRIMORDIAL

        # Test another domain
        material_axioms = axiom_loader.get_by_domain(DomainType.MATERIAL)
        assert len(material_axioms) > 0
        for axiom in material_axioms:
            assert axiom.domain == DomainType.MATERIAL


class TestAxiomVector:
    """Tests for AxiomVector class."""

    def test_axiom_vector_add(self):
        """Test adding weights to axiom vector."""
        vector = AxiomVector()

        # Add initial weight
        vector.add("axiom_ignis", 0.5)
        assert vector.get("axiom_ignis") == pytest.approx(0.5)

        # Add more weight (should accumulate)
        vector.add("axiom_ignis", 0.3)
        assert vector.get("axiom_ignis") == pytest.approx(0.8)

        # Add different axiom
        vector.add("axiom_aqua", 0.4)
        assert vector.get("axiom_aqua") == pytest.approx(0.4)

        # Non-existent axiom should return 0
        assert vector.get("axiom_nonexistent") == 0

    def test_axiom_vector_add_clamp(self):
        """Test that weights are clamped to 0-1 range."""
        vector = AxiomVector()

        # Add weight that exceeds 1
        vector.add("axiom_test", 0.8)
        vector.add("axiom_test", 0.5)
        assert vector.get("axiom_test") == pytest.approx(1.0)

        # Add negative weight (should clamp to 0)
        vector2 = AxiomVector()
        vector2.add("axiom_neg", -0.5)
        assert vector2.get("axiom_neg") == pytest.approx(0.0)

    def test_axiom_vector_merge(self):
        """Test merging two axiom vectors."""
        vector1 = AxiomVector()
        vector1.add("axiom_ignis", 0.8)
        vector1.add("axiom_terra", 0.4)

        vector2 = AxiomVector()
        vector2.add("axiom_ignis", 0.2)
        vector2.add("axiom_aqua", 0.6)

        # Merge with 50:50 ratio
        merged = vector1.merge_with(vector2, ratio=0.5)

        # axiom_ignis: 0.8 * 0.5 + 0.2 * 0.5 = 0.5
        assert merged.get("axiom_ignis") == pytest.approx(0.5)

        # axiom_terra: 0.4 * 0.5 + 0 * 0.5 = 0.2
        assert merged.get("axiom_terra") == pytest.approx(0.2)

        # axiom_aqua: 0 * 0.5 + 0.6 * 0.5 = 0.3
        assert merged.get("axiom_aqua") == pytest.approx(0.3)

    def test_axiom_vector_merge_different_ratio(self):
        """Test merging with different ratio."""
        vector1 = AxiomVector()
        vector1.add("axiom_a", 1.0)

        vector2 = AxiomVector()
        vector2.add("axiom_a", 0.0)

        # Merge with 0.7:0.3 ratio (70% from vector1)
        merged = vector1.merge_with(vector2, ratio=0.7)

        # axiom_a: 1.0 * 0.7 + 0.0 * 0.3 = 0.7
        assert merged.get("axiom_a") == pytest.approx(0.7)

    def test_axiom_vector_get_dominant(self):
        """Test getting dominant axiom from vector."""
        vector = AxiomVector()
        vector.add("axiom_low", 0.2)
        vector.add("axiom_high", 0.9)
        vector.add("axiom_mid", 0.5)

        dominant = vector.get_dominant()
        assert dominant == "axiom_high"

    def test_axiom_vector_empty_dominant(self):
        """Test getting dominant from empty vector."""
        vector = AxiomVector()
        assert vector.get_dominant() is None

    def test_axiom_vector_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        vector = AxiomVector()
        vector.add("axiom_ignis", 0.8)
        vector.add("axiom_aqua", 0.3)

        # Serialize
        data = vector.to_dict()
        assert data == {"axiom_ignis": 0.8, "axiom_aqua": 0.3}

        # Deserialize
        restored = AxiomVector.from_dict(data)
        assert restored.get("axiom_ignis") == pytest.approx(0.8)
        assert restored.get("axiom_aqua") == pytest.approx(0.3)
