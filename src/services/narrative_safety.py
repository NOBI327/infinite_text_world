"""Content-Safety 연동 — 묘사 레벨 관리 + 폴백

narrative-service.md 섹션 6 대응. Alpha MVP 최소 구현.
"""

import logging

logger = logging.getLogger(__name__)

NARRATION_LEVELS = {
    "explicit": "詳細に描写せよ。",
    "moderate": "暗示的に描写し、直接的表現は避けよ。",
    "fade_out": "行為開始を1文で暗示し、場面転換せよ。",
}

FALLBACK_ORDER = ["explicit", "moderate", "fade_out", "template"]


class NarrationManager:
    """카테고리별 묘사 레벨 캐시"""

    def __init__(self, default_level: str = "moderate"):
        self.default_level = default_level
        self.effective_levels: dict[str, str] = {}

    def get_start_level(self, category: str) -> str:
        """카테고리별 시작 레벨 반환."""
        return self.effective_levels.get(category, self.default_level)

    def record_fallback(self, category: str, used_level: str) -> None:
        """폴백 경험 기록."""
        self.effective_levels[category] = used_level


class ContentSafetyFilter:
    """Content-Safety 필터 (Alpha 최소 구현)"""

    def __init__(self, narration_manager: NarrationManager):
        self._manager = narration_manager

    def get_scene_direction_prompt(self, scene_direction: dict | None) -> str:
        """scene_direction → 프롬프트 삽입 문자열.

        None이면 빈 문자열.
        """
        if scene_direction is None:
            return ""

        level = scene_direction.get("level", "moderate")
        instruction = NARRATION_LEVELS.get(level, "")
        if instruction:
            return f"\n[Scene Direction] {instruction}"
        return ""
