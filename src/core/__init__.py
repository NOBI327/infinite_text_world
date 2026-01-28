"""ITW Core Engine"""
__version__ = "0.1.0-alpha"

from src.core.axiom_system import AxiomLoader, Axiom, AxiomVector, ResonanceType, DomainType
from src.core.world_generator import WorldGenerator, MapNode, NodeTier, Resource, SensoryData, Echo
from src.core.navigator import Navigator, Direction, LocationView, TravelResult, render_compass
from src.core.echo_system import EchoManager, EchoCategory, EchoType, EchoVisibility
from src.core.core_rule import CharacterSheet, StatType, CheckResult, CheckResultTier, ResolutionEngine
from src.core.engine import ITWEngine, PlayerState, ActionResult

__all__ = [
    "AxiomLoader",
    "Axiom",
    "AxiomVector",
    "ResonanceType",
    "DomainType",
    "WorldGenerator",
    "MapNode",
    "NodeTier",
    "Resource",
    "SensoryData",
    "Echo",
    "Navigator",
    "Direction",
    "LocationView",
    "TravelResult",
    "render_compass",
    "EchoManager",
    "EchoCategory",
    "EchoType",
    "EchoVisibility",
    "CharacterSheet",
    "StatType",
    "CheckResult",
    "CheckResultTier",
    "ResolutionEngine",
    "ITWEngine",
    "PlayerState",
    "ActionResult",
]
