"""LLM 응답 파싱 — narrative + META 분리

narrative-service.md 섹션 5 대응.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


class ResponseParser:
    """LLM 응답 파싱"""

    def parse_dual(self, raw: str) -> tuple[str, dict, bool]:
        """narrative + meta 이중 구조 파싱.

        Returns:
            (narrative, meta, parse_success)

        파싱 단계:
        1. 전체 JSON 시도 → json.loads()
        2. ```json ... ``` 블록 추출 시도
        3. 실패 → (raw 전체, {}, False)
        """
        # 1단계: 전체 JSON 시도
        parsed = self._try_parse_json(raw.strip())
        if parsed is not None:
            return self._extract_dual(parsed, raw)

        # 2단계: ```json 블록 추출
        json_block = self._extract_json_block(raw)
        if json_block is not None:
            parsed = self._try_parse_json(json_block)
            if parsed is not None:
                return self._extract_dual(parsed, raw)

        # 3단계: 실패
        logger.warning("Failed to parse dual response, using raw as narrative")
        return (raw.strip(), {}, False)

    def parse_text(self, raw: str) -> str:
        """text only 응답. 그대로 반환. 앞뒤 공백 strip."""
        return raw.strip()

    def _try_parse_json(self, text: str) -> dict | None:
        """JSON 파싱 시도. 실패 시 None."""
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
            return None
        except (json.JSONDecodeError, TypeError):
            return None

    def _extract_json_block(self, text: str) -> str | None:
        """```json ... ``` 블록 추출."""
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        return None

    def _extract_dual(self, parsed: dict, raw: str) -> tuple[str, dict, bool]:
        """파싱된 dict에서 narrative + meta 추출."""
        narrative = parsed.get("narrative")
        if not isinstance(narrative, str) or not narrative:
            narrative = raw.strip()

        meta = parsed.get("meta")
        if not isinstance(meta, dict):
            meta = {}

        return (narrative, meta, True)
