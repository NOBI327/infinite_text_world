"""Objective 관련 로직 — hint_type 매핑, 대체 목표 생성, fallback"""

import logging
import uuid
from typing import Any

from .models import Objective, Quest

logger = logging.getLogger(__name__)

# === hint_type → objective_type 매핑 ===
HINT_TYPE_MAP: dict[str, str] = {
    "find_npc": "talk_to_npc",
    "escort_to": "escort",
    "fetch_item": "deliver",
    "deliver_item": "deliver",
    "investigate_area": "reach_node",
    "resolve_problem": "resolve_check",
    "go_to": "reach_node",
}

# === 퀘스트 유형별 fallback 목표 ===
FALLBACK_OBJECTIVES: dict[str, list[dict[str, str]]] = {
    "deliver": [{"type": "deliver", "description": "의뢰 물품을 납품처에 전달하라"}],
    "escort": [{"type": "escort", "description": "대상을 목표지에 호위하라"}],
    "investigate": [{"type": "reach_node", "description": "해당 지역을 조사하라"}],
    "resolve": [{"type": "resolve_check", "description": "문제를 해결하라"}],
    "negotiate": [{"type": "talk_to_npc", "description": "관련자와 대화하라"}],
    "bond": [{"type": "talk_to_npc", "description": "대상과 교류하라"}],
    "rivalry": [{"type": "resolve_check", "description": "위협에 대응하라"}],
}

# === 대체 목표 템플릿 ===
REPLACEMENT_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "target_dead": [
        {
            "type": "deliver",
            "description_template": "유품을 의뢰주에게 전달하라",
            "origin": "auto_fallback",
        },
        {
            "type": "resolve_check",
            "description_template": "사인을 조사하라",
            "origin": "auto_fallback",
        },
    ],
    "target_missing": [
        {
            "type": "reach_node",
            "description_template": "주변을 추가로 탐색하라",
            "origin": "auto_fallback",
        },
        {
            "type": "talk_to_npc",
            "description_template": "목격자를 찾아 대화하라",
            "origin": "auto_fallback",
        },
    ],
    "item_unobtainable": [
        {
            "type": "deliver",
            "description_template": "대체품을 의뢰주에게 전달하라",
            "origin": "auto_fallback",
        },
    ],
    # time_expired: 자동 대체 없음
}

CLIENT_CONSULT_TEMPLATE: dict[str, str] = {
    "type": "talk_to_npc",
    "description_template": "의뢰주에게 상황을 보고하라",
    "origin": "client_consult",
}


def map_hint_to_objective_type(hint_type: str) -> str | None:
    """LLM hint_type → objective_type 매핑. 인식 불가 시 None."""
    return HINT_TYPE_MAP.get(hint_type)


def create_fallback_objectives(quest_type: str, quest_id: str) -> list[Objective]:
    """LLM 제안 검증 실패 시 퀘스트 유형별 fallback 목표 생성."""
    fallbacks = FALLBACK_OBJECTIVES.get(quest_type, [])
    result: list[Objective] = []

    for fb in fallbacks:
        obj = Objective(
            objective_id=f"obj_{uuid.uuid4().hex[:12]}",
            quest_id=quest_id,
            description=fb["description"],
            objective_type=fb["type"],
        )
        result.append(obj)

    if not result:
        result.append(
            Objective(
                objective_id=f"obj_{uuid.uuid4().hex[:12]}",
                quest_id=quest_id,
                description="퀘스트를 완료하라",
                objective_type="resolve_check",
            )
        )

    return result


def generate_replacement_objectives(
    failed_obj: Objective,
    quest: Quest,
    context: dict[str, Any],
) -> list[Objective]:
    """실패한 목표에 대한 대체 목표 후보 생성.

    항상 client_consult(의뢰주 보고)가 첫 번째.
    fail_reason에 따라 auto_fallback 추가.
    """
    result: list[Objective] = []

    # client_consult는 항상 첫 번째
    client_npc_id = context.get("client_npc_id", "")
    consult_obj = Objective(
        objective_id=f"obj_{uuid.uuid4().hex[:12]}",
        quest_id=quest.quest_id,
        description=CLIENT_CONSULT_TEMPLATE["description_template"],
        objective_type=CLIENT_CONSULT_TEMPLATE["type"],
        target={"npc_id": client_npc_id} if client_npc_id else {},
        is_replacement=True,
        replaced_objective_id=failed_obj.objective_id,
        replacement_origin="client_consult",
    )
    result.append(consult_obj)

    # fail_reason별 자동 대체
    fail_reason = failed_obj.fail_reason or ""
    templates = REPLACEMENT_TEMPLATES.get(fail_reason, [])

    for tmpl in templates:
        obj = Objective(
            objective_id=f"obj_{uuid.uuid4().hex[:12]}",
            quest_id=quest.quest_id,
            description=tmpl["description_template"],
            objective_type=tmpl["type"],
            is_replacement=True,
            replaced_objective_id=failed_obj.objective_id,
            replacement_origin=tmpl["origin"],
        )
        result.append(obj)

    return result


def validate_objectives_hint(
    hints: list[dict],
    quest_type: str,
    quest_id: str,
) -> list[Objective]:
    """LLM의 objectives_hint를 검증하여 Objective 리스트 생성.

    1. hint_type → objective_type 매핑
    2. 매핑 실패 → 해당 hint 스킵
    3. 결과가 비어있으면 fallback 생성
    """
    result: list[Objective] = []

    for hint in hints:
        hint_type = hint.get("hint_type", "")
        obj_type = map_hint_to_objective_type(hint_type)
        if obj_type is None:
            logger.warning("Unrecognized hint_type: %s, skipping", hint_type)
            continue

        description = hint.get("description", "")
        target = hint.get("target", {})

        obj = Objective(
            objective_id=f"obj_{uuid.uuid4().hex[:12]}",
            quest_id=quest_id,
            description=description,
            objective_type=obj_type,
            target=target if isinstance(target, dict) else {},
        )
        result.append(obj)

    if not result:
        logger.warning(
            "All hints failed validation for quest_type=%s, using fallback",
            quest_type,
        )
        return create_fallback_objectives(quest_type, quest_id)

    return result
