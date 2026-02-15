"""LLM 프롬프트용 퀘스트 컨텍스트 빌더"""

import logging

from .models import Quest, QuestSeed

logger = logging.getLogger(__name__)


# === 티어별 LLM 지시 ===
TIER_INSTRUCTIONS: dict[int, str] = {
    3: "복선 없이 완결적 서술. 간단한 사건으로 마무리하라.",
    2: "1~2개 복선을 설치하라. 표면 아래 더 큰 이야기가 있음을 암시하라.",
    1: "다수 복선을 설치하라. 미해결 요소를 남기고, 스케일 확장을 암시하라.",
}

FINALE_INSTRUCTION = (
    "이것은 체인의 최종 퀘스트이다. 반드시 다음을 지켜라:\n"
    "1. unresolved_threads의 모든 미해결 복선을 이번 퀘스트 안에서 해소하라.\n"
    "2. 새로운 복선을 설치하지 마라.\n"
    "3. 체인 전체를 관통하는 결말을 제시하라.\n"
    "4. PC 경향을 반영한 최종 도전을 설계하라."
)


def build_seed_context(seed: QuestSeed, tier_instruction: str) -> dict:
    """시드 발생 시 LLM 프롬프트에 주입할 컨텍스트."""
    return {
        "quest_seed": {
            "active": True,
            "seed_type": seed.seed_type,
            "seed_tier": seed.seed_tier,
            "context_tags": seed.context_tags,
            "instruction": tier_instruction,
        }
    }


def build_activation_context(
    seed: QuestSeed,
    npc_personality: dict,
    relationship_status: str,
) -> dict:
    """퀘스트 활성화 시 LLM에 전달할 컨텍스트."""
    return {
        "quest_generation": {
            "seed_type": seed.seed_type,
            "context_tags": seed.context_tags,
            "npc_personality": npc_personality,
            "relationship_status": relationship_status,
            "instruction": (
                "시드 정보를 기반으로 퀘스트를 생성하라. "
                "NPC의 성격과 관계 상태에 맞는 의뢰 형태를 구성하라."
            ),
        }
    }


def build_expired_seed_context(seed: QuestSeed) -> dict:
    """만료 시드 참조 시 LLM 컨텍스트."""
    return {
        "expired_seed": {
            "seed_type": seed.seed_type,
            "context_tags": seed.context_tags,
            "expiry_result": seed.expiry_result,
            "instruction": (
                "이 시드는 만료되었다. 만료 결과를 반영한 서술을 생성하라. "
                "PC가 개입하지 않았을 때의 자연스러운 결말을 보여주라."
            ),
        }
    }


def build_failure_report_context(
    quest: Quest,
    failed_objective_description: str,
    fail_reason: str,
) -> dict:
    """의뢰주 보고 대화 시 LLM 컨텍스트."""
    return {
        "quest_failure_report": {
            "quest_id": quest.quest_id,
            "failed_objective": failed_objective_description,
            "fail_reason": fail_reason,
            "instruction": (
                "PC가 실패한 목표를 의뢰주에게 보고하는 상황이다. "
                "NPC의 반응을 성격과 관계에 맞게 서술하라."
            ),
        }
    }


def build_quest_update_context(
    quest_id: str,
    objective_description: str,
    remaining: int,
    quest_completed: bool,
) -> dict:
    """대화 중 목표 달성/실패 시 다음 LLM 턴에 주입."""
    instruction = "목표가 달성되었다. "
    if quest_completed:
        instruction += "퀘스트가 완료되었다. 결말을 서술하라."
    else:
        instruction += f"남은 목표가 {remaining}개 있다. 다음 목표를 안내하라."

    return {
        "quest_update": {
            "quest_id": quest_id,
            "objective_completed": objective_description,
            "remaining_objectives": remaining,
            "quest_completed": quest_completed,
            "instruction": instruction,
        }
    }
