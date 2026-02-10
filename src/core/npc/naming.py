"""NPC 명명 시스템

npc-system.md 섹션 7 대응.
Alpha 단계: 이름 풀 기반 생성.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class NPCNameSeed:
    """이름 생성용 시드 (섹션 7.1)"""

    region_name: str = ""  # "타르고스 영지"
    biome_descriptor: str = ""  # "언덕", "화염 산맥"
    facility_type: str = ""  # "smithy", "market"
    role: str = ""  # "blacksmith", "merchant"
    gender: str = "N"  # "M", "F", "N"


@dataclass
class NPCFullName:
    """NPC 전체 명칭 (섹션 7.2)"""

    region_name: str = ""
    biome_descriptor: str = ""
    facility_name: str = ""
    occupation: str = ""
    given_name: str = ""
    gender: str = "N"
    current_occupation: str = ""

    def formal_name(self) -> str:
        """정식 명칭"""
        return (
            f"{self.region_name}의 {self.biome_descriptor} "
            f"{self.facility_name} {self.occupation} {self.given_name}"
        )

    def current_name(self) -> str:
        """현재 상태 반영 명칭"""
        if self.current_occupation != self.occupation:
            return f"{self.current_occupation} {self.given_name}"
        return f"{self.occupation} {self.given_name}"

    def short_name(self) -> str:
        """짧은 호칭"""
        return self.given_name

    def to_dict(self) -> Dict:
        return {
            "region_name": self.region_name,
            "biome_descriptor": self.biome_descriptor,
            "facility_name": self.facility_name,
            "occupation": self.occupation,
            "given_name": self.given_name,
            "gender": self.gender,
            "current_occupation": self.current_occupation,
        }


# ── 이름 풀 (섹션 7.3 기반) ─────────────────────────────────

GIVEN_NAMES: Dict[str, List[str]] = {
    "M": [
        "엘라르",
        "토린",
        "발더",
        "카엘",
        "드레이크",
        "로건",
        "에릭",
        "하드리안",
        "레오닉",
        "가렛",
        "브란도",
        "마르쿠스",
        "오웬",
        "다미안",
        "루카스",
        "시그문트",
        "에드윈",
        "라이언",
        "펠릭스",
        "세드릭",
    ],
    "F": [
        "탈라",
        "미렌",
        "세라",
        "아이린",
        "릴리아",
        "엘레나",
        "이사벨",
        "로리엔",
        "카산드라",
        "비비안",
        "엘사",
        "나디아",
        "클레어",
        "아리아",
        "헬레나",
        "코라",
        "베로니카",
        "마르가",
        "에밀리아",
        "리비아",
    ],
    "N": [
        "아쉬",
        "로완",
        "퀸",
        "사이러스",
        "모건",
        "테일러",
        "조던",
        "에이버리",
        "리스",
        "하퍼",
        "다코타",
        "케이든",
        "알렉스",
        "레슬리",
        "패튼",
        "나엘",
        "새미",
        "엘리엇",
        "유진",
        "카밀",
    ],
}

OCCUPATIONS: Dict[str, Dict[str, str]] = {
    "blacksmith": {"title": "대장장이", "facility": "대장간"},
    "merchant": {"title": "상인", "facility": "상점"},
    "herbalist": {"title": "약초사", "facility": "오두막"},
    "innkeeper": {"title": "여관주인", "facility": "여관"},
    "guard": {"title": "경비병", "facility": "초소"},
    "farmer": {"title": "농부", "facility": "농장"},
    "miner": {"title": "광부", "facility": "광산"},
    "scholar": {"title": "학자", "facility": "서재"},
    "bandit": {"title": "도적", "facility": "야영지"},
    "priest": {"title": "사제", "facility": "성전"},
    "barkeeper": {"title": "주인장", "facility": "주점"},
    "foreman": {"title": "감독관", "facility": "광산"},
}

BIOME_DESCRIPTORS: Dict[str, List[str]] = {
    "temperate_forest": ["푸른 숲", "고요한 숲", "이끼낀 골짜기"],
    "volcanic": ["화염 산맥", "재의 평원", "용암 기슭"],
    "hills": ["언덕", "구릉지", "바위 고원"],
    "desert": ["모래벌판", "메마른 땅", "태양의 길"],
}

NAME_POOLS: Dict = {
    "given_names": GIVEN_NAMES,
    "occupations": OCCUPATIONS,
    "biome_descriptors": BIOME_DESCRIPTORS,
}


def generate_name(
    seed: Optional[NPCNameSeed] = None,
    rng_seed: Optional[int] = None,
) -> NPCFullName:
    """이름 풀에서 랜덤 선택하여 NPCFullName 생성 (섹션 7.3)

    Args:
        seed: 이름 시드. None이면 성별 N, 역할 없음 기준으로 생성.
        rng_seed: 재현성을 위한 RNG 시드.

    Returns:
        NPCFullName 인스턴스.
    """
    rng = random.Random(rng_seed)

    if seed is None:
        seed = NPCNameSeed()

    gender = seed.gender if seed.gender in GIVEN_NAMES else "N"
    names = GIVEN_NAMES[gender]
    given_name = rng.choice(names)

    occupation_data = OCCUPATIONS.get(seed.role, {})
    occupation = occupation_data.get("title", seed.role or "주민")
    facility_name = occupation_data.get("facility", "")

    return NPCFullName(
        region_name=seed.region_name,
        biome_descriptor=seed.biome_descriptor,
        facility_name=facility_name,
        occupation=occupation,
        given_name=given_name,
        gender=gender,
        current_occupation=occupation,
    )
