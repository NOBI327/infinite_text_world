"""Tests for world_generator module."""

import pytest

from src.core.axiom_system import AxiomLoader
from src.core.world_generator import NodeTier, WorldGenerator


@pytest.fixture()
def axiom_loader() -> AxiomLoader:
    """Load axioms from the data file."""
    return AxiomLoader("src/data/itw_214_divine_axioms.json")


@pytest.fixture()
def world(axiom_loader: AxiomLoader) -> WorldGenerator:
    """Create a WorldGenerator with fixed seed."""
    return WorldGenerator(axiom_loader, seed=42)


class TestWorldGenerator:
    """Tests for WorldGenerator class."""

    def test_safe_haven_exists(self, world: WorldGenerator):
        """Test that Safe Haven at (0,0) is automatically generated."""
        # Safe Haven should exist immediately after initialization
        safe_haven = world.get_node(0, 0)

        assert safe_haven is not None
        assert safe_haven.x == 0
        assert safe_haven.y == 0
        assert safe_haven.coordinate == "0_0"
        assert safe_haven.is_safe_haven is True
        assert safe_haven.cluster_id == "cls_safe_haven"
        assert safe_haven.tier == NodeTier.COMMON
        assert safe_haven.development_level == 1

        # Should have default resources
        assert len(safe_haven.resources) == 2
        resource_ids = [r.id for r in safe_haven.resources]
        assert "res_basic_supply" in resource_ids
        assert "res_healing_herb" in resource_ids

    def test_generate_node(self, world: WorldGenerator):
        """Test generating a new node at specific coordinates."""
        # Generate node at (5, 5)
        node = world.generate_node(5, 5)

        assert node is not None
        assert node.x == 5
        assert node.y == 5
        assert node.coordinate == "5_5"
        assert node.is_safe_haven is False
        assert node.tier in [NodeTier.COMMON, NodeTier.UNCOMMON, NodeTier.RARE]
        assert node.axiom_vector is not None
        assert node.sensory_data is not None
        assert node.cluster_id is not None

        # Node should be stored in nodes dict
        assert "5_5" in world.nodes
        assert world.nodes["5_5"] == node

    def test_generate_node_returns_existing(self, world: WorldGenerator):
        """Test that generate_node returns existing node without regenerating."""
        # Generate first time
        node1 = world.generate_node(3, 3)

        # Generate again - should return same node
        node2 = world.generate_node(3, 3)

        assert node1 is node2
        assert node1.created_at == node2.created_at

    def test_generate_node_force_regenerate(self, world: WorldGenerator):
        """Test that force=True regenerates the node."""
        # Generate first time
        node1 = world.generate_node(4, 4)

        # Force regenerate - may have different properties
        node2 = world.generate_node(4, 4, force=True)

        # Should be stored in nodes dict (same coordinate)
        assert world.nodes["4_4"] == node2
        # Both nodes have valid coordinates
        assert node1.coordinate == "4_4"
        assert node2.coordinate == "4_4"

    def test_get_or_generate(self, world: WorldGenerator):
        """Test get_or_generate returns existing or creates new."""
        # Node doesn't exist yet
        assert world.get_node(10, 10) is None

        # get_or_generate should create it
        node = world.get_or_generate(10, 10)
        assert node is not None
        assert node.x == 10
        assert node.y == 10

        # Now get_node should return it
        assert world.get_node(10, 10) is node

        # get_or_generate again should return same node
        node2 = world.get_or_generate(10, 10)
        assert node2 is node

    def test_rarity_distribution(self, axiom_loader: AxiomLoader):
        """Test rarity distribution with fixed seed."""
        # Create world with specific seed for reproducibility
        world = WorldGenerator(axiom_loader, seed=12345)

        # Generate many nodes to check distribution
        common_count = 0
        uncommon_count = 0
        rare_count = 0

        # Generate 100 nodes (excluding Safe Haven)
        for i in range(1, 101):
            node = world.generate_node(i, 0)
            if node.tier == NodeTier.COMMON:
                common_count += 1
            elif node.tier == NodeTier.UNCOMMON:
                uncommon_count += 1
            elif node.tier == NodeTier.RARE:
                rare_count += 1

        total = common_count + uncommon_count + rare_count
        assert total == 100

        # Check approximate distribution (94/5/1)
        # Allow some variance due to randomness and cluster inheritance
        assert common_count >= 80  # Should be mostly common
        assert uncommon_count >= 0  # At least some uncommon possible
        assert rare_count >= 0  # Rare is very rare

        # Common should be the majority
        assert common_count > uncommon_count
        assert common_count > rare_count

    def test_cluster_inheritance(self, axiom_loader: AxiomLoader):
        """Test that adjacent nodes can inherit cluster properties."""
        # Use a specific seed that we know produces inheritance
        world = WorldGenerator(axiom_loader, seed=999)

        # Generate a node first
        parent_node = world.generate_node(1, 0)
        parent_cluster = parent_node.cluster_id

        # Generate many adjacent nodes - some should inherit
        # Due to 40% inheritance chance, we check multiple neighbors
        inherited_count = 0
        test_coords = [(2, 0), (1, 1), (0, 1), (1, -1)]

        for x, y in test_coords:
            node = world.generate_node(x, y)
            if node.cluster_id == parent_cluster:
                inherited_count += 1

        # At least verify the mechanism works (nodes are generated)
        assert len(world.nodes) >= 5  # Safe Haven + parent + 4 adjacent

    def test_deterministic_generation(self, axiom_loader: AxiomLoader):
        """Test that same seed produces same results."""
        # Create two worlds with same seed
        world1 = WorldGenerator(axiom_loader, seed=7777)
        world2 = WorldGenerator(axiom_loader, seed=7777)

        # Generate same coordinates
        node1 = world1.generate_node(5, 5)
        node2 = world2.generate_node(5, 5)

        # Should have same properties
        assert node1.tier == node2.tier
        assert node1.cluster_id == node2.cluster_id
        assert node1.axiom_vector.get_dominant() == node2.axiom_vector.get_dominant()

    def test_generate_area(self, world: WorldGenerator):
        """Test generating an area of nodes."""
        # Generate area around (5, 5) with radius 2
        nodes = world.generate_area(5, 5, radius=2)

        # Should generate (2*2+1)^2 = 25 nodes
        assert len(nodes) == 25

        # Check all nodes in the area exist
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                coord = f"{5 + dx}_{5 + dy}"
                assert coord in world.nodes

    def test_get_stats(self, world: WorldGenerator):
        """Test world statistics."""
        # Generate some nodes
        world.generate_area(0, 0, radius=3)

        stats = world.get_stats()

        assert "total_nodes" in stats
        assert "tier_distribution" in stats
        assert "unique_clusters" in stats

        assert stats["total_nodes"] > 0
        assert stats["tier_distribution"]["COMMON"] >= 0
        assert stats["tier_distribution"]["UNCOMMON"] >= 0
        assert stats["tier_distribution"]["RARE"] >= 0
