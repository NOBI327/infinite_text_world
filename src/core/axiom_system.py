"""
ITW Core Engine - Module 1: Axiom System
=========================================
Protocol T.A.G. (214 Divine Axioms) 로더 및 관리 시스템

이 모듈은 214개의 신성 공리(Divine Axioms)를 로드하고,
게임 내 모든 객체/지형/이벤트의 기반이 되는 태그 벡터를 관리합니다.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum


class ResonanceType(Enum):
    """8대 공명 속성"""
    THERMAL = "Thermal"      # Primordial (원소/에너지)
    STRUCTURAL = "Structural" # Material (물질/재질)
    KINETIC = "Kinetic"      # Force (물리/운동)
    BIO = "Bio"              # Organic (유기/생체)
    PSYCHE = "Psyche"        # Mind (정신/감정)
    DATA = "Data"            # Logic (논리/장치)
    SOCIAL = "Social"        # Social (사회/규율)
    ESOTERIC = "Esoteric"    # Mystery (신비/초월)


class DomainType(Enum):
    """8대 영역"""
    PRIMORDIAL = "Primordial"  # 000-029
    MATERIAL = "Material"      # 030-059
    FORCE = "Force"            # 060-089
    ORGANIC = "Organic"        # 090-119
    MIND = "Mind"              # 120-149
    LOGIC = "Logic"            # 150-179
    SOCIAL = "Social"          # 180-199
    MYSTERY = "Mystery"        # 200-213


@dataclass
class AxiomInteraction:
    """Axiom 간 상호작용 정의"""
    effect: str          # neutralize, amplify, transform, resist, ignore, trigger
    ratio: Optional[float] = None       # neutralize, resist용
    multiplier: Optional[float] = None  # amplify용
    result: Optional[str] = None        # transform, trigger용


@dataclass
class AxiomLogic:
    """Axiom의 로직 정의"""
    passive: List[str] = field(default_factory=list)
    on_contact: Dict[str, AxiomInteraction] = field(default_factory=dict)
    damage_mod: Dict[str, float] = field(default_factory=dict)
    special: Optional[str] = None


@dataclass
class Axiom:
    """
    단일 Divine Axiom 정의

    세계의 모든 사물과 현상은 이 214개 공리의 조합으로 정의됩니다.
    예: Fireball = Ignis(Fire) + Vis(Force) + Sphaera(Sphere)
    """
    id: int
    code: str              # axiom_ignis
    name_latin: str        # Ignis
    name_kr: str           # 화염
    name_en: str           # Fire
    domain: DomainType
    resonance: ResonanceType
    tier: int              # 1=기본, 2=중급, 3=고급
    logic: AxiomLogic
    tags: List[str]
    flavor: str

    def get_display_name(self, lang: str = "kr") -> str:
        """언어별 표시명 반환"""
        if lang == "kr":
            return f"{self.name_latin} ({self.name_kr})"
        elif lang == "en":
            return f"{self.name_latin} ({self.name_en})"
        return self.name_latin

    def has_passive(self, effect: str) -> bool:
        """특정 패시브 효과 보유 여부"""
        return effect in self.logic.passive

    def get_interaction(self, other_axiom_latin: str) -> Optional[AxiomInteraction]:
        """다른 Axiom과의 상호작용 조회"""
        return self.logic.on_contact.get(other_axiom_latin)


class AxiomLoader:
    """
    214 Divine Axioms 로더 및 관리자

    JSON 파일에서 Axiom 데이터를 로드하고,
    다양한 방식으로 조회/필터링할 수 있는 인터페이스를 제공합니다.
    """

    def __init__(self, json_path: str = "itw_214_divine_axioms.json"):
        self._axioms: Dict[int, Axiom] = {}
        self._axioms_by_code: Dict[str, Axiom] = {}
        self._axioms_by_latin: Dict[str, Axiom] = {}
        self._axioms_by_domain: Dict[DomainType, List[Axiom]] = {d: [] for d in DomainType}
        self._axioms_by_resonance: Dict[ResonanceType, List[Axiom]] = {r: [] for r in ResonanceType}
        self._axioms_by_tier: Dict[int, List[Axiom]] = {1: [], 2: [], 3: []}

        self._load(json_path)

    def _parse_logic(self, logic_data: Dict) -> AxiomLogic:
        """JSON logic 객체를 AxiomLogic으로 파싱"""
        on_contact = {}
        for target, interaction in logic_data.get("on_contact", {}).items():
            on_contact[target] = AxiomInteraction(
                effect=interaction.get("effect", ""),
                ratio=interaction.get("ratio"),
                multiplier=interaction.get("multiplier"),
                result=interaction.get("result")
            )

        return AxiomLogic(
            passive=logic_data.get("passive", []),
            on_contact=on_contact,
            damage_mod=logic_data.get("damage_mod", {}),
            special=logic_data.get("special")
        )

    def _load(self, json_path: str):
        """JSON 파일에서 Axiom 데이터 로드"""
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Axiom data file not found: {json_path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            # Enum 변환
            domain = DomainType(item["domain"])
            resonance = ResonanceType(item["resonance"])

            axiom = Axiom(
                id=item["id"],
                code=item["code"],
                name_latin=item["name_latin"],
                name_kr=item["name_kr"],
                name_en=item["name_en"],
                domain=domain,
                resonance=resonance,
                tier=item["tier"],
                logic=self._parse_logic(item["logic"]),
                tags=item["tags"],
                flavor=item["flavor"]
            )

            # 다중 인덱싱
            self._axioms[axiom.id] = axiom
            self._axioms_by_code[axiom.code] = axiom
            self._axioms_by_latin[axiom.name_latin] = axiom
            self._axioms_by_domain[domain].append(axiom)
            self._axioms_by_resonance[resonance].append(axiom)
            self._axioms_by_tier[axiom.tier].append(axiom)

        print(f"[AxiomLoader] Loaded {len(self._axioms)} Divine Axioms")

    # === 조회 메서드 ===

    def get_by_id(self, axiom_id: int) -> Optional[Axiom]:
        """ID로 Axiom 조회"""
        return self._axioms.get(axiom_id)

    def get_by_code(self, code: str) -> Optional[Axiom]:
        """코드로 Axiom 조회 (예: axiom_ignis)"""
        return self._axioms_by_code.get(code)

    def get_by_latin(self, latin_name: str) -> Optional[Axiom]:
        """라틴어명으로 Axiom 조회 (예: Ignis)"""
        return self._axioms_by_latin.get(latin_name)

    def get_by_domain(self, domain: DomainType) -> List[Axiom]:
        """영역별 Axiom 리스트 조회"""
        return self._axioms_by_domain.get(domain, [])

    def get_by_resonance(self, resonance: ResonanceType) -> List[Axiom]:
        """공명 속성별 Axiom 리스트 조회"""
        return self._axioms_by_resonance.get(resonance, [])

    def get_by_tier(self, tier: int) -> List[Axiom]:
        """티어별 Axiom 리스트 조회"""
        return self._axioms_by_tier.get(tier, [])

    def get_all(self) -> List[Axiom]:
        """모든 Axiom 리스트 반환"""
        return list(self._axioms.values())

    def search_by_tag(self, tag: str) -> List[Axiom]:
        """태그로 Axiom 검색"""
        return [a for a in self._axioms.values() if tag in a.tags]

    def search_by_passive(self, passive_effect: str) -> List[Axiom]:
        """특정 패시브 효과를 가진 Axiom 검색"""
        return [a for a in self._axioms.values() if a.has_passive(passive_effect)]

    # === 상호작용 계산 ===

    def calculate_interaction(self, source: Axiom, target: Axiom) -> Optional[Dict[str, Any]]:
        """
        두 Axiom 간의 상호작용 계산

        Returns:
            {
                "effect": "amplify",
                "value": 1.5,
                "result": None
            }
        """
        interaction = source.get_interaction(target.name_latin)
        if not interaction:
            # 기본 규칙 (정의되지 않은 상호작용)
            if source.domain == target.domain:
                return {"effect": "amplify", "value": 1.1}
            elif source.resonance == target.resonance:
                return {"effect": "resist", "value": 0.8}
            else:
                return {"effect": "neutral", "value": 1.0}

        result = {"effect": interaction.effect}

        if interaction.effect == "neutralize":
            result["value"] = interaction.ratio or 1.0
        elif interaction.effect == "amplify":
            result["value"] = interaction.multiplier or 1.0
        elif interaction.effect == "resist":
            result["value"] = interaction.ratio or 0.5
        elif interaction.effect == "transform":
            result["result"] = interaction.result
        elif interaction.effect == "trigger":
            result["result"] = interaction.result
        elif interaction.effect == "ignore":
            result["value"] = 0

        return result

    # === 통계 ===

    def get_stats(self) -> Dict[str, Any]:
        """Axiom 통계 정보 반환"""
        return {
            "total": len(self._axioms),
            "by_tier": {t: len(a) for t, a in self._axioms_by_tier.items()},
            "by_domain": {d.value: len(a) for d, a in self._axioms_by_domain.items()},
            "by_resonance": {r.value: len(a) for r, a in self._axioms_by_resonance.items()}
        }


# === Axiom Vector (태그 조합) ===

@dataclass
class AxiomVector:
    """
    Axiom 벡터 - 객체/지형의 태그 조합

    게임 내 모든 엔티티는 이 벡터로 정의됩니다.
    예: 늪지대 = {Lutum: 0.6, Aqua: 0.4, Putredo: 0.3}
    """
    weights: Dict[str, float] = field(default_factory=dict)

    def add(self, axiom_code: str, weight: float):
        """Axiom 추가 또는 가중치 증가"""
        self.weights[axiom_code] = self.weights.get(axiom_code, 0) + weight
        # 가중치는 0~1 사이로 클램프
        self.weights[axiom_code] = max(0, min(1, self.weights[axiom_code]))

    def get(self, axiom_code: str) -> float:
        """Axiom 가중치 조회"""
        return self.weights.get(axiom_code, 0)

    def get_dominant(self) -> Optional[str]:
        """가장 높은 가중치의 Axiom 반환"""
        if not self.weights:
            return None
        return max(self.weights, key=self.weights.get)

    def get_top_n(self, n: int = 3) -> List[tuple]:
        """상위 n개 Axiom 반환 [(code, weight), ...]"""
        sorted_items = sorted(self.weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def merge_with(self, other: 'AxiomVector', ratio: float = 0.5) -> 'AxiomVector':
        """
        다른 벡터와 병합 (클러스터 상속용)

        Args:
            other: 병합할 벡터
            ratio: self의 비율 (0.5 = 50:50 혼합)
        """
        result = AxiomVector()
        all_codes = set(self.weights.keys()) | set(other.weights.keys())

        for code in all_codes:
            w1 = self.weights.get(code, 0)
            w2 = other.weights.get(code, 0)
            result.weights[code] = w1 * ratio + w2 * (1 - ratio)

        return result

    def to_dict(self) -> Dict[str, float]:
        """직렬화용 딕셔너리 변환"""
        return self.weights.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'AxiomVector':
        """딕셔너리에서 생성"""
        vector = cls()
        vector.weights = data.copy()
        return vector

    def __repr__(self):
        top = self.get_top_n(3)
        parts = [f"{code}:{weight:.2f}" for code, weight in top]
        return f"AxiomVector({', '.join(parts)}{'...' if len(self.weights) > 3 else ''})"


# === 테스트 코드 ===

if __name__ == "__main__":
    # 테스트: Axiom 로더
    loader = AxiomLoader("itw_214_divine_axioms.json")

    # 통계 출력
    stats = loader.get_stats()
    print("\n=== Axiom Statistics ===")
    print(f"Total: {stats['total']}")
    print(f"By Tier: {stats['by_tier']}")
    print(f"By Domain: {stats['by_domain']}")

    # 샘플 조회
    ignis = loader.get_by_latin("Ignis")
    if ignis:
        print(f"\n=== Sample Axiom: {ignis.get_display_name()} ===")
        print(f"Domain: {ignis.domain.value}")
        print(f"Tier: {ignis.tier}")
        print(f"Passive: {ignis.logic.passive}")
        print(f"Flavor: {ignis.flavor}")

    # 상호작용 테스트
    aqua = loader.get_by_latin("Aqua")
    if ignis and aqua:
        interaction = loader.calculate_interaction(ignis, aqua)
        print("\n=== Interaction: Ignis → Aqua ===")
        print(f"Result: {interaction}")

    # 벡터 테스트
    swamp_vector = AxiomVector()
    swamp_vector.add("axiom_lutum", 0.6)
    swamp_vector.add("axiom_aqua", 0.4)
    swamp_vector.add("axiom_putredo", 0.3)
    print("\n=== Swamp Vector ===")
    print(f"Vector: {swamp_vector}")
    print(f"Dominant: {swamp_vector.get_dominant()}")
