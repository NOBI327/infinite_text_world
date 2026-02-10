"""배경인물 → NPC 승격 시스템

npc-system.md 섹션 4 대응.
"""

from typing import Dict

from src.core.npc.models import BackgroundEntity, HEXACO, NPCData

# ── 임계값 (섹션 4.1) ────────────────────────────────────────

PROMOTION_THRESHOLD: int = 50
WORLDPOOL_THRESHOLD: int = 15  # 30%

# ── 승격 점수 테이블 (섹션 4.2) ──────────────────────────────

PROMOTION_SCORE_TABLE: Dict[str, int] = {
    "encounter": 5,  # 단순 조우 (같은 공간)
    "greet": 15,  # 말 걸기 (인사 수준)
    "conversation": 30,  # 실질적 대화 (정보 교환)
    "trade": 20,  # 거래
    "joint_combat": 40,  # 공동 전투 (아군)
    "help": 35,  # 도움 주기/받기
    "ask_name": 50,  # 이름 묻기
    "combat_engaged": 20,  # 전투 발생 (적대형)
    "survived_combat": 15,  # 전투 중 생존 (적대형)
    "fled_combat": 25,  # 도주 성공 (적대형)
}


def calculate_new_score(current_score: int, action: str) -> int:
    """승격 점수 계산 (순수 함수)

    Args:
        current_score: 현재 승격 점수
        action: 행동 키 (PROMOTION_SCORE_TABLE 참조)

    Returns:
        새로운 승격 점수. 미등록 행동이면 변동 없음.
    """
    delta = PROMOTION_SCORE_TABLE.get(action, 0)
    return current_score + delta


def check_promotion_status(score: int) -> str:
    """승격 상태 판정

    Args:
        score: 현재 승격 점수

    Returns:
        "promoted" (≥50), "worldpool" (≥15), "none" (<15)
    """
    if score >= PROMOTION_THRESHOLD:
        return "promoted"
    if score >= WORLDPOOL_THRESHOLD:
        return "worldpool"
    return "none"


def build_npc_from_entity(entity: BackgroundEntity, hexaco: HEXACO) -> NPCData:
    """BackgroundEntity → NPCData 순수 변환 (섹션 4.3)

    UUID 생성, DB 저장, EventBus emit은 포함하지 않는다.
    npc_id는 빈 문자열 — Service 레이어에서 UUID를 할당한다.

    Args:
        entity: 승격 대상 배경 존재
        hexaco: 미리 생성된 HEXACO 인스턴스

    Returns:
        NPCData (npc_id="" 상태)
    """
    return NPCData(
        npc_id="",  # Service 레이어에서 할당
        full_name={},  # Service 레이어에서 naming.generate_name() 호출 후 설정
        given_name="",
        hexaco=hexaco,
        home_node=entity.home_node,
        current_node=entity.current_node,
        origin_type="promoted",
        origin_entity_type=entity.entity_type.value,
        role=entity.role,
    )
