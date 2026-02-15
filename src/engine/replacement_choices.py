"""대체 목표 선택지 시스템 메시지 포맷.

objective_failed 처리 후 PC에게 대체 목표를 안내하는 시스템 메시지 생성.
Alpha에서는 대체 목표 전부를 active 상태로 두고, PC가 어떤 행동을 하든
ObjectiveWatcher가 매칭한다. 선택지는 가이드일 뿐.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_replacement_choices(
    failed_description: str,
    replacements: list[Any],
) -> str:
    """대체 목표 선택지를 시스템 메시지로 포맷.

    Args:
        failed_description: 실패한 목표의 설명
        replacements: 대체 Objective 리스트 (description 속성 필요)

    Returns:
        시스템 메시지 문자열
    """
    if not replacements:
        return f"[시스템] {failed_description}"

    lines = [f"[시스템] {failed_description}"]
    for i, repl in enumerate(replacements, 1):
        desc = getattr(repl, "description", str(repl))
        lines.append(f"  {i}. {desc}")
    lines.append("(또는 다른 행동을 자유롭게 선언할 수 있다)")

    return "\n".join(lines)
