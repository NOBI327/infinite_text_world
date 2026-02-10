"""HEXACO → 톤 태그 변환

npc-system.md 섹션 9 대응.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from src.core.npc.models import HEXACO


@dataclass
class ToneContext:
    """Python이 계산하여 LLM에 전달하는 톤 컨텍스트 (섹션 9.2)"""

    # 감정 상태
    emotion: str = "neutral"  # "neutral", "happy", "angry", "fearful", "sad"
    emotion_intensity: float = 0.0  # 0.0 ~ 1.0

    # 말투 태그 (HEXACO에서 도출)
    manner_tags: List[str] = field(default_factory=list)

    # 태도 태그 (관계 + HEXACO 조합)
    attitude_tags: List[str] = field(default_factory=list)

    # 의도
    intent: str = "inform"  # "inform", "request", "refuse", "warn", ...


def derive_manner_tags(hexaco: HEXACO) -> List[str]:
    """HEXACO에서 말투 태그 도출 (섹션 9.3)"""
    tags: List[str] = []

    # Extraversion -> 말의 양/에너지
    if hexaco.X > 0.7:
        tags.extend(["verbose", "energetic"])
    elif hexaco.X < 0.3:
        tags.extend(["terse", "quiet"])

    # Agreeableness -> 어조
    if hexaco.A > 0.7:
        tags.extend(["gentle", "polite"])
    elif hexaco.A < 0.3:
        tags.extend(["blunt", "confrontational"])

    # Honesty-Humility -> 표현 방식
    if hexaco.H > 0.7:
        tags.extend(["direct", "sincere"])
    elif hexaco.H < 0.3:
        tags.extend(["evasive", "flattering"])

    # Conscientiousness -> 구조화
    if hexaco.C > 0.7:
        tags.extend(["formal", "precise"])
    elif hexaco.C < 0.3:
        tags.extend(["casual", "rambling"])

    # Emotionality -> 감정 표현
    if hexaco.E > 0.7:
        tags.extend(["expressive", "dramatic"])
    elif hexaco.E < 0.3:
        tags.extend(["stoic", "matter-of-fact"])

    # Openness -> 어휘/비유
    if hexaco.O > 0.7:
        tags.extend(["colorful", "metaphorical"])
    elif hexaco.O < 0.3:
        tags.extend(["plain", "literal"])

    return tags


# ── 감정 계산 (섹션 9.4) ─────────────────────────────────────

EVENT_EMOTION_MAP: Dict[str, str] = {
    "greeting": "neutral",
    "helped": "happy",
    "betrayed": "angry",
    "threatened": "fearful",
    "lost_item": "sad",
    "insulted": "angry",
    "complimented": "happy",
}


def calculate_emotion(
    event: str,
    affinity: float,
    hexaco: HEXACO,
) -> Tuple[str, float]:
    """상황 + 관계(affinity) + 성격 -> 감정 계산 (섹션 9.4)

    Args:
        event: 이벤트 키 (e.g. "betrayed", "helped")
        affinity: 관계 호감도 (-100 ~ +100). 모듈 간 직접 의존 방지를 위해
                  Relationship 객체 대신 float로 받는다.
        hexaco: HEXACO dataclass 인스턴스

    Returns:
        (emotion, intensity) 튜플. intensity 0.0~1.0 클램프.
    """
    base_emotion = EVENT_EMOTION_MAP.get(event, "neutral")
    intensity = 0.5

    # 이벤트별 기본 강도
    if event in ("betrayed", "threatened"):
        intensity = 0.8
    elif event in ("helped", "complimented"):
        intensity = 0.6

    # HEXACO 보정
    if base_emotion == "angry" and hexaco.A > 0.7:
        intensity *= 0.7  # 온화한 성격은 분노 약화
    if base_emotion == "fearful" and hexaco.E < 0.3:
        intensity *= 0.5  # 냉정한 성격은 공포 약화
    if base_emotion == "happy" and hexaco.X > 0.7:
        intensity *= 1.2  # 외향적 성격은 기쁨 증폭

    # 관계(affinity) 보정
    if affinity > 50 and base_emotion == "angry":
        intensity *= 0.8  # 친한 사이면 분노 약화
    if affinity < -30 and base_emotion == "angry":
        intensity *= 1.2  # 적대 관계면 분노 증폭

    intensity = max(0.0, min(1.0, intensity))
    return (base_emotion, intensity)
