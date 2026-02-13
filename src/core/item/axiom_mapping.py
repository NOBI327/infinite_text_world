"""Axiom 태그 매핑 — 자유 태그 → Divine Axiom 연결"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AxiomTagInfo:
    """태그 매핑 정보"""

    tag: str  # "Ignis"
    domain: str  # "Primordial"
    resonance: str  # "Destruction"
    axiom_ids: tuple[str, ...]  # ("AXM_042", "AXM_043")
    description: str  # "화염, 연소, 열"


class AxiomTagMapping:
    """axiom_tag_mapping.json 로더"""

    def __init__(self) -> None:
        self._mapping: dict[str, AxiomTagInfo] = {}

    def load_from_json(self, path: str | Path) -> int:
        """매핑 파일 로드. 반환: 로드된 태그 수."""
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw: dict[str, dict] = json.load(f)

        count = 0
        for tag_name, info in raw.items():
            try:
                self._mapping[tag_name] = AxiomTagInfo(
                    tag=tag_name,
                    domain=info["domain"],
                    resonance=info["resonance"],
                    axiom_ids=tuple(info.get("axiom_ids", [])),
                    description=info.get("description", ""),
                )
                count += 1
            except KeyError as e:
                logger.warning("Failed to load axiom tag: %s — %s", tag_name, e)

        logger.info("Loaded %d axiom tag mappings from %s", count, path)
        return count

    def get(self, tag: str) -> Optional[AxiomTagInfo]:
        """태그 정보 조회."""
        return self._mapping.get(tag)

    def get_domain(self, tag: str) -> Optional[str]:
        """태그의 Domain 반환."""
        info = self._mapping.get(tag)
        return info.domain if info else None

    def get_resonance(self, tag: str) -> Optional[str]:
        """태그의 Resonance 반환."""
        info = self._mapping.get(tag)
        return info.resonance if info else None

    def get_all_tags(self) -> list[str]:
        """등록된 모든 태그명 반환."""
        return list(self._mapping.keys())
