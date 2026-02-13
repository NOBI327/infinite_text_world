"""아이템 시스템 Core — 순수 Python, DB 무관"""

from .models import ItemType, ItemPrototype, ItemInstance
from .registry import PrototypeRegistry
from .axiom_mapping import AxiomTagInfo, AxiomTagMapping

__all__ = [
    "ItemType",
    "ItemPrototype",
    "ItemInstance",
    "PrototypeRegistry",
    "AxiomTagInfo",
    "AxiomTagMapping",
]
