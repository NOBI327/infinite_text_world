# 오버레이 레이어 시스템 설계서

**버전**: 1.0  
**작성일**: 2025-02-07  
**상태**: 확정

---

## 1. 개요

### 1.1 목적

이 문서는 ITW의 오버레이 레이어 시스템을 정의한다. 맵 노드에 동적으로 겹쳐지는 날씨, 영유권, 퀘스트 영향권 등의 오버레이를 통합 관리하는 구조를 수립한다.

### 1.2 설계 사상

```
"퀘스트가 월드를 오염시키는 구조"

퀘스트가 단순히 "NPC한테 받고 → 목적지 가서 → 해결"하는 게 아니라,
퀘스트가 활성화되는 순간 관련 지역 전체가 그 퀘스트의 "분위기권" 안에 들어간다.
```

### 1.3 핵심 개념

| 개념 | 설명 |
|------|------|
| 오버레이 | 맵 노드에 동적으로 적용되는 효과 레이어 |
| severity | 오버레이 강도 (0.0~1.0), 시간에 따라 변화 |
| 병합 | 여러 오버레이가 중첩될 때 효과 통합 |
| 창발적 효과 | 충돌하는 오버레이 조합에서 새로운 효과 발생 |

### 1.4 Protocol T.A.G.와의 일관성

공리 조합에서 창발적 결과가 나오듯이, 오버레이 충돌에서도 창발적 효과가 발생한다.

---

## 2. 레이어 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                 Player View                                  │
├─────────────────────────────────────────────────────────────┤
│  L5: Event Overlay    (축제, 재난, 침공)                    │
│  L4: Quest Overlay    (퀘스트 영향권)                       │
│  L3: Territory Overlay (영유권, 정책)                       │
│  L2: Weather Overlay  (날씨, 환경)                          │
├─────────────────────────────────────────────────────────────┤
│  L1: Infrastructure   (도로, 다리) - 노드 내장              │
│  L0: Biome            (지형, 기후) - 노드 내장              │
├─────────────────────────────────────────────────────────────┤
│  L-1: Depth           (서브그리드, 던전) - 노드 내장        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 레이어 유형 분류

| 레이어 | 저장 방식 | 특성 |
|--------|-----------|------|
| L-1 ~ L1 | **노드 내장** | 불변/준불변, 1:1 매핑 |
| L2 ~ L5 | **오버레이** | 동적, 다:다 매핑, 중첩 가능 |

### 2.3 오버레이 우선순위

```python
class OverlayPriority(int, Enum):
    """충돌 시 우선순위 (높을수록 우선)"""
    BASE = 0        # 기본 바이옴 효과
    WEATHER = 10    # 날씨
    TERRITORY = 20  # 영유권 정책
    QUEST = 30      # 퀘스트 영향
    EVENT = 40      # 긴급 이벤트
```

---

## 3. 오버레이 기반 인터페이스

### 3.1 OverlayType

```python
from enum import Enum

class OverlayType(str, Enum):
    WEATHER = "weather"
    TERRITORY = "territory"
    QUEST = "quest"
    EVENT = "event"
```

### 3.2 BaseOverlay

```python
from abc import ABC, abstractmethod
from typing import Set, Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class BaseOverlay(ABC, BaseModel):
    """모든 오버레이의 기반 클래스"""
    
    # 식별
    overlay_id: str
    overlay_type: OverlayType
    name: str  # 표시용 이름
    
    # 우선순위
    priority: int
    
    # 영향 범위
    affected_nodes: Set[str]
    
    # 활성 상태
    is_active: bool = True
    severity: float = 1.0  # 0.0 ~ 1.0 (강도)
    
    # 생명주기
    created_turn: int
    expires_turn: Optional[int] = None  # None = 영구
    
    @abstractmethod
    def get_node_effects(self, node_id: str) -> "OverlayEffects":
        """해당 노드에 적용할 효과 반환"""
        pass
    
    @abstractmethod
    def on_tick(self, current_turn: int) -> None:
        """턴 경과 시 처리 (severity 변화 등)"""
        pass
    
    def is_expired(self, current_turn: int) -> bool:
        """만료 여부 체크"""
        if self.expires_turn is None:
            return False
        return current_turn >= self.expires_turn
    
    def affects_node(self, node_id: str) -> bool:
        """특정 노드에 영향을 미치는지 확인"""
        return node_id in self.affected_nodes
```

### 3.3 OverlayEffects

```python
from dataclasses import dataclass, field

@dataclass
class OverlayEffects:
    """오버레이가 노드에 미치는 효과"""
    
    # 날씨/환경 덮어쓰기
    weather_override: Optional[str] = None
    temperature_mod: float = 0.0      # 온도 보정
    visibility_mod: float = 0.0       # 시야 보정 (-1.0 ~ +1.0)
    
    # NPC 대화 컨텍스트
    dialogue_tags: List[str] = field(default_factory=list)
    
    # 조우 확률 조정
    encounter_bias: Dict[str, float] = field(default_factory=dict)
    # 예: {"undead": +0.3, "wildlife": -0.5}
    
    # 경제 수정자
    economy_modifier: Dict[str, float] = field(default_factory=dict)
    # 예: {"water": 3.0, "food": 1.5}
    
    # 이동 수정자
    travel_cost_mod: float = 1.0      # 이동 비용 배율
    blocked: bool = False              # 통행 불가
    
    # 서술 힌트
    narrative_tags: List[str] = field(default_factory=list)
    # 예: ["cracked_earth", "wilted_crops", "dry_well"]
    
    # 공명 속성 수정자
    resonance_modifier: Dict[str, float] = field(default_factory=dict)
    # 예: {"Thermal": +0.2, "Bio": -0.1}
```

---

## 4. Weather Overlay (날씨)

### 4.1 개요

Global 날씨 상태를 각 바이옴에서 Local로 해석하는 "Broadcast & Interpret" 패턴.

### 4.2 날씨 유형

```python
class WeatherType(str, Enum):
    CLEAR = "clear"           # 맑음
    CLOUDY = "cloudy"         # 흐림
    RAIN = "rain"             # 비
    HEAVY_RAIN = "heavy_rain" # 폭우
    STORM = "storm"           # 폭풍
    SNOW = "snow"             # 눈
    BLIZZARD = "blizzard"     # 눈보라
    FOG = "fog"               # 안개
    DROUGHT = "drought"       # 가뭄 (퀘스트 영향)
    HEATWAVE = "heatwave"     # 폭염
```

### 4.3 WeatherOverlay 구현

```python
class WeatherOverlay(BaseOverlay):
    """날씨 오버레이"""
    
    overlay_type: OverlayType = OverlayType.WEATHER
    priority: int = OverlayPriority.WEATHER
    
    # 날씨 상세
    weather_type: WeatherType
    intensity: float = 0.5  # 0.0 ~ 1.0
    
    # 바이옴별 해석 규칙
    biome_interpretations: Dict[str, Dict[str, Any]] = {}
    
    def get_node_effects(self, node_id: str) -> OverlayEffects:
        """바이옴에 따른 날씨 효과 계산"""
        
        # 노드의 바이옴 조회
        biome = geography.get_node_biome(node_id)
        
        # 기본 효과
        effects = self._get_base_effects()
        
        # 바이옴별 해석 적용
        if biome in self.biome_interpretations:
            interpretation = self.biome_interpretations[biome]
            effects = self._apply_interpretation(effects, interpretation)
        
        # intensity 적용
        effects = self._scale_by_intensity(effects)
        
        return effects
    
    def _get_base_effects(self) -> OverlayEffects:
        """날씨 유형별 기본 효과"""
        
        BASE_EFFECTS = {
            WeatherType.CLEAR: OverlayEffects(
                visibility_mod=0.1,
                narrative_tags=["sunny", "pleasant"],
            ),
            WeatherType.RAIN: OverlayEffects(
                visibility_mod=-0.2,
                travel_cost_mod=1.2,
                narrative_tags=["rain", "wet_ground", "puddles"],
                dialogue_tags=["weather_rain"],
            ),
            WeatherType.STORM: OverlayEffects(
                visibility_mod=-0.5,
                travel_cost_mod=1.5,
                narrative_tags=["storm", "thunder", "lightning", "dangerous"],
                dialogue_tags=["weather_storm", "stay_indoors"],
                encounter_bias={"wildlife": -0.3},
            ),
            WeatherType.FOG: OverlayEffects(
                visibility_mod=-0.7,
                travel_cost_mod=1.3,
                narrative_tags=["fog", "mist", "eerie", "low_visibility"],
                encounter_bias={"ambush": +0.2},
            ),
            WeatherType.DROUGHT: OverlayEffects(
                temperature_mod=0.3,
                narrative_tags=["drought", "cracked_earth", "dry"],
                dialogue_tags=["water_shortage", "crop_failure"],
                economy_modifier={"water": 2.5, "food": 1.5},
            ),
        }
        
        return BASE_EFFECTS.get(self.weather_type, OverlayEffects())
    
    def on_tick(self, current_turn: int) -> None:
        """날씨 자연 변화"""
        # 날씨는 외부 시스템(time_core)에서 변경
        pass
```

### 4.4 바이옴별 해석 예시

```python
# 사막에서의 비 = 축복
DESERT_RAIN_INTERPRETATION = {
    "narrative_tags_override": ["blessed_rain", "oasis_forming"],
    "dialogue_tags_add": ["rain_celebration"],
    "economy_modifier_override": {"water": 0.5},  # 물 가격 하락
}

# 화산 지대에서의 폭풍 = 위험 증가
VOLCANIC_STORM_INTERPRETATION = {
    "narrative_tags_add": ["ash_storm", "volcanic_lightning"],
    "encounter_bias_add": {"elemental": +0.3},
    "travel_cost_mod_multiply": 1.5,
}
```

---

## 5. Territory Overlay (영유권)

### 5.1 개요

다중 노드에 걸친 영역의 소유권과 정책을 정의한다.

### 5.2 정책 유형

```python
class TerritoryPolicy(str, Enum):
    OPEN = "open"           # 자유 통행
    TOLL = "toll"           # 통행세
    RESTRICTED = "restricted"  # 제한 (허가 필요)
    HOSTILE = "hostile"     # 적대 (즉시 공격)
    PROTECTED = "protected" # 보호령 (몬스터 출현 감소)
```

### 5.3 TerritoryOverlay 구현

```python
class TerritoryOverlay(BaseOverlay):
    """영유권 오버레이"""
    
    overlay_type: OverlayType = OverlayType.TERRITORY
    priority: int = OverlayPriority.TERRITORY
    
    # 소유권
    owner_id: Optional[str] = None      # NPC ID (영주)
    owner_name: Optional[str] = None    # 표시용
    faction_id: Optional[str] = None    # 소속 세력
    
    # 정책
    policy: TerritoryPolicy = TerritoryPolicy.OPEN
    toll_amount: int = 0                # 통행세 금액
    
    # 세금
    tax_rate: float = 0.1               # 세율 (10%)
    
    # 방어
    guard_level: int = 0                # 경비 수준 (0~5)
    
    # 관계 조건
    required_reputation: Optional[int] = None  # 진입 필요 평판
    
    def get_node_effects(self, node_id: str) -> OverlayEffects:
        """영유권 효과"""
        
        effects = OverlayEffects()
        
        # 정책별 효과
        if self.policy == TerritoryPolicy.TOLL:
            effects.dialogue_tags.append("toll_collection")
            effects.narrative_tags.append("guarded_border")
        
        elif self.policy == TerritoryPolicy.RESTRICTED:
            effects.dialogue_tags.append("restricted_area")
            effects.narrative_tags.append("checkpoints")
        
        elif self.policy == TerritoryPolicy.HOSTILE:
            effects.dialogue_tags.append("enemy_territory")
            effects.narrative_tags.append("hostile_guards")
            effects.encounter_bias["guard"] = 0.5
        
        elif self.policy == TerritoryPolicy.PROTECTED:
            effects.dialogue_tags.append("safe_zone")
            effects.narrative_tags.append("patrolled_roads")
            effects.encounter_bias["monster"] = -0.3
            effects.encounter_bias["bandit"] = -0.4
        
        # 경비 수준 반영
        if self.guard_level > 0:
            effects.encounter_bias["crime"] = -0.1 * self.guard_level
        
        return effects
    
    def on_tick(self, current_turn: int) -> None:
        """영유권 변화 (정복, 반란 등은 외부 이벤트)"""
        pass
    
    def check_entry_permission(self, player: "Player") -> Tuple[bool, str]:
        """진입 허가 체크"""
        
        if self.policy == TerritoryPolicy.OPEN:
            return (True, "")
        
        elif self.policy == TerritoryPolicy.TOLL:
            if player.wallet >= self.toll_amount:
                return (True, f"통행세 {self.toll_amount} 골드 필요")
            return (False, "통행세를 낼 돈이 부족합니다")
        
        elif self.policy == TerritoryPolicy.RESTRICTED:
            if self.required_reputation:
                rep = player.get_reputation(self.faction_id)
                if rep >= self.required_reputation:
                    return (True, "")
            return (False, "진입 허가가 필요합니다")
        
        elif self.policy == TerritoryPolicy.HOSTILE:
            return (False, "적대 영역입니다")
        
        return (True, "")
```

---

## 6. Quest Overlay (퀘스트 영향권)

### 6.1 개요

퀘스트가 활성화되면 관련 지역에 오버레이가 생성되어 월드를 "오염"시킨다.

### 6.2 핵심 개념

```
퀘스트 활성화 → QuestOverlay 생성 → 영향권 노드에 효과 적용
    ↓
방치 시 severity 상승 → 영향권 확장 → 효과 강화
    ↓
해결 시 severity 감소 → 영향권 축소 → 지역 회복
```

### 6.3 QuestOverlay 구현

```python
class QuestOverlay(BaseOverlay):
    """퀘스트가 월드에 미치는 영향권"""
    
    overlay_type: OverlayType = OverlayType.QUEST
    priority: int = OverlayPriority.QUEST
    
    # 연결된 퀘스트
    quest_id: str
    quest_title: str
    
    # severity 변화 규칙
    severity_growth_rate: float = 0.03    # 방치 시 턴당 증가율
    severity_decay_rate: float = 0.1      # 해결 후 턴당 감소율
    max_severity: float = 1.0
    
    # 효과 템플릿
    effects_template: Dict[str, Any] = {}
    
    # 영향권 확장 설정
    expansion_threshold: float = 0.5      # 이 severity 이상이면 확장
    expansion_nodes: Set[str] = set()     # 확장 가능한 노드
    
    # 상태
    is_resolving: bool = False            # 해결 중 여부
    
    def get_node_effects(self, node_id: str) -> OverlayEffects:
        """severity에 따라 효과 강도 조절"""
        
        template = self.effects_template
        
        effects = OverlayEffects(
            weather_override=template.get("weather_override"),
            
            dialogue_tags=[
                f"{tag}" 
                for tag in template.get("dialogue_tags", [])
            ],
            
            encounter_bias={
                k: v * self.severity 
                for k, v in template.get("encounter_bias", {}).items()
            },
            
            economy_modifier={
                k: 1.0 + (v - 1.0) * self.severity
                for k, v in template.get("economy_modifier", {}).items()
            },
            
            narrative_tags=self._get_severity_narrative_tags(),
        )
        
        return effects
    
    def _get_severity_narrative_tags(self) -> List[str]:
        """severity에 따른 서술 태그"""
        
        base_tags = self.effects_template.get("narrative_tags", [])
        
        if self.severity < 0.3:
            return [f"{tag}_mild" for tag in base_tags]
        elif self.severity < 0.7:
            return base_tags
        else:
            return [f"{tag}_severe" for tag in base_tags]
    
    def on_tick(self, current_turn: int) -> None:
        """턴 경과 시 severity 변화"""
        
        if self.is_resolving:
            # 해결 중이면 감소
            self.severity = max(0.0, self.severity - self.severity_decay_rate)
            
            # severity 0이 되면 비활성화
            if self.severity <= 0:
                self.is_active = False
        else:
            # 방치 시 증가
            self.severity = min(
                self.max_severity, 
                self.severity + self.severity_growth_rate
            )
            
            # 임계값 초과 시 영향권 확장
            if self.severity >= self.expansion_threshold:
                self._expand_affected_area()
    
    def _expand_affected_area(self) -> None:
        """영향권 확장"""
        
        if not self.expansion_nodes:
            return
        
        # 확장 가능한 노드 중 하나 추가
        new_node = self.expansion_nodes.pop()
        self.affected_nodes.add(new_node)
    
    def on_quest_progress(self, progress_delta: float) -> None:
        """퀘스트 진행 시"""
        
        # 진행에 따라 severity 감소
        reduction = self.severity_decay_rate * progress_delta
        self.severity = max(0.0, self.severity - reduction)
    
    def on_quest_complete(self) -> None:
        """퀘스트 완료 시"""
        
        self.is_resolving = True
        self.severity_decay_rate = 0.2  # 빠르게 회복
    
    def on_quest_failed(self) -> None:
        """퀘스트 실패 시"""
        
        # 최대 severity로 고정되거나 영구화
        self.severity = self.max_severity
        self.severity_growth_rate = 0  # 더 이상 악화 안 함
        self.expires_turn = None  # 영구
```

### 6.4 퀘스트 오버레이 예시

```python
# 가뭄 저주 퀘스트
DROUGHT_CURSE_OVERLAY = QuestOverlay(
    overlay_id="overlay_drought_001",
    name="마른 땅의 저주",
    quest_id="quest_drought_curse",
    quest_title="마른 땅의 저주",
    
    affected_nodes={"village_01", "farm_01", "farm_02", "well_01"},
    expansion_nodes={"farm_03", "village_02", "road_01"},
    
    severity=0.3,
    severity_growth_rate=0.03,
    expansion_threshold=0.5,
    
    effects_template={
        "weather_override": "drought",
        "dialogue_tags": ["curse", "drought", "water_shortage", "despair"],
        "encounter_bias": {
            "undead": +0.3,
            "wildlife": -0.5,
        },
        "economy_modifier": {
            "water": 3.0,
            "food": 1.5,
            "labor": 0.7,
        },
        "narrative_tags": ["cracked_earth", "wilted_crops", "dry_well"],
    },
    
    created_turn=100,
)

# 고블린 침공 퀘스트
GOBLIN_INVASION_OVERLAY = QuestOverlay(
    overlay_id="overlay_goblin_001",
    name="고블린 침공",
    quest_id="quest_goblin_invasion",
    quest_title="고블린의 습격",
    
    affected_nodes={"forest_edge_01", "farm_04", "road_02"},
    expansion_nodes={"village_01", "farm_01"},
    
    severity=0.4,
    severity_growth_rate=0.05,  # 빠르게 악화
    expansion_threshold=0.6,
    
    effects_template={
        "dialogue_tags": ["goblin_threat", "danger", "evacuation"],
        "encounter_bias": {
            "goblin": +0.5,
            "goblin_scout": +0.3,
            "merchant": -0.4,  # 상인 감소
        },
        "economy_modifier": {
            "weapon": 1.5,
            "armor": 1.3,
        },
        "narrative_tags": ["goblin_tracks", "burnt_farms", "fearful_villagers"],
    },
    
    created_turn=100,
)
```

---

## 7. Event Overlay (일시적 이벤트)

### 7.1 개요

축제, 재난, 침공 등 시간 제한이 있는 특수 이벤트.

### 7.2 이벤트 유형

```python
class EventType(str, Enum):
    FESTIVAL = "festival"       # 축제
    DISASTER = "disaster"       # 재난
    INVASION = "invasion"       # 침공
    PLAGUE = "plague"           # 역병
    MIRACLE = "miracle"         # 기적
    MARKET = "market"           # 시장/박람회
```

### 7.3 EventOverlay 구현

```python
class EventOverlay(BaseOverlay):
    """일시적 이벤트 오버레이"""
    
    overlay_type: OverlayType = OverlayType.EVENT
    priority: int = OverlayPriority.EVENT
    
    # 이벤트 상세
    event_type: EventType
    description: str
    
    # 시간 제한
    duration_turns: int
    
    # 효과
    effects: OverlayEffects
    
    # 특수 컨텐츠
    special_npcs: List[str] = []       # 이벤트 전용 NPC
    special_shops: List[str] = []      # 이벤트 전용 상점
    special_encounters: List[str] = [] # 이벤트 전용 조우
    
    def get_node_effects(self, node_id: str) -> OverlayEffects:
        """이벤트 효과 반환"""
        return self.effects
    
    def on_tick(self, current_turn: int) -> None:
        """만료 체크"""
        if self.is_expired(current_turn):
            self.is_active = False
```

### 7.4 이벤트 예시

```python
# 수확제
HARVEST_FESTIVAL = EventOverlay(
    overlay_id="event_harvest_001",
    name="가을 수확제",
    event_type=EventType.FESTIVAL,
    description="마을의 연례 수확 축제",
    
    affected_nodes={"village_01", "market_01"},
    
    duration_turns=72,  # 3일
    created_turn=1000,
    expires_turn=1072,
    
    effects=OverlayEffects(
        dialogue_tags=["festival", "celebration", "harvest"],
        narrative_tags=["decorations", "music", "feasting"],
        economy_modifier={
            "food": 0.7,      # 음식 할인
            "alcohol": 0.8,   # 술 할인
        },
        encounter_bias={
            "merchant": +0.4,
            "entertainer": +0.3,
            "pickpocket": +0.2,
        },
    ),
    
    special_npcs=["festival_merchant_01", "fortune_teller_01"],
    special_shops=["festival_food_stall", "game_booth"],
)
```

---

## 8. 오버레이 병합 시스템

### 8.1 OverlayManager

```python
class OverlayManager:
    """오버레이 병합 및 충돌 처리"""
    
    overlays: List[BaseOverlay] = []
    
    def register(self, overlay: BaseOverlay) -> None:
        """오버레이 등록"""
        self.overlays.append(overlay)
        self.overlays.sort(key=lambda o: o.priority)
    
    def unregister(self, overlay_id: str) -> None:
        """오버레이 제거"""
        self.overlays = [o for o in self.overlays if o.overlay_id != overlay_id]
    
    def get_overlays_at_node(self, node_id: str) -> List[BaseOverlay]:
        """노드에 영향을 미치는 오버레이 목록"""
        return [
            o for o in self.overlays 
            if o.is_active and o.affects_node(node_id)
        ]
    
    def get_merged_effects(self, node_id: str) -> "MergedEffects":
        """노드에 적용되는 모든 오버레이 효과 병합"""
        
        applicable = self.get_overlays_at_node(node_id)
        
        if not applicable:
            return MergedEffects()
        
        # 우선순위 정렬 (낮은 것부터)
        applicable.sort(key=lambda o: o.priority)
        
        # 병합
        merged = MergedEffects()
        conflicts = []
        
        for overlay in applicable:
            effects = overlay.get_node_effects(node_id)
            conflict = merged.merge(effects, overlay)
            if conflict:
                conflicts.append(conflict)
        
        # 충돌이 있으면 창발적 결과 생성
        if conflicts:
            merged.narrative_tags.append("reality_unstable")
            merged.emergent_effects = self.resolve_conflicts(conflicts)
        
        return merged
    
    def resolve_conflicts(
        self, 
        conflicts: List["OverlayConflict"]
    ) -> Dict[str, Any]:
        """충돌을 창발적 효과로 변환"""
        
        emergent = {}
        
        for conflict in conflicts:
            # 날씨 충돌
            if conflict.conflict_type == "weather":
                emergent.update(self._resolve_weather_conflict(conflict))
            
            # 정책 충돌
            elif conflict.conflict_type == "policy":
                emergent.update(self._resolve_policy_conflict(conflict))
        
        return emergent
    
    def _resolve_weather_conflict(
        self, 
        conflict: "OverlayConflict"
    ) -> Dict[str, Any]:
        """날씨 충돌 해결"""
        
        values = set(conflict.values)
        
        # 가뭄 + 홍수 = 뒤틀린 저주
        if "drought" in values and "flood" in values:
            return {
                "weather_pattern": "chaotic_alternating",
                "narrative": "하루는 타들어가는 가뭄, 다음 날은 대지를 삼키는 홍수",
                "extra_encounter": "elemental_chaos",
                "resonance_instability": True,
            }
        
        # 폭풍 + 폭염 = 번개 폭풍
        if "storm" in values and "heatwave" in values:
            return {
                "weather_pattern": "lightning_storm",
                "narrative": "뜨거운 공기가 하늘을 찢는 번개를 만들어낸다",
                "extra_encounter": "lightning_elemental",
            }
        
        return {}
    
    def _resolve_policy_conflict(
        self, 
        conflict: "OverlayConflict"
    ) -> Dict[str, Any]:
        """정책 충돌 해결 (영토 분쟁)"""
        
        return {
            "contested_territory": True,
            "narrative": "두 세력이 이 땅의 지배권을 두고 다투고 있다",
            "extra_encounter": "patrol_skirmish",
            "dialogue_tags_add": ["territorial_dispute", "choose_side"],
        }
    
    def tick(self, current_turn: int) -> None:
        """모든 오버레이 턴 처리"""
        
        to_remove = []
        
        for overlay in self.overlays:
            if overlay.is_expired(current_turn):
                overlay.is_active = False
                to_remove.append(overlay.overlay_id)
            elif overlay.is_active:
                overlay.on_tick(current_turn)
        
        # 만료된 오버레이 제거
        for overlay_id in to_remove:
            self.unregister(overlay_id)
```

### 8.2 MergedEffects

```python
@dataclass
class MergedEffects:
    """병합된 최종 효과"""
    
    # 기본 효과들
    weather: Optional[str] = None
    temperature_mod: float = 0.0
    visibility_mod: float = 0.0
    
    dialogue_tags: List[str] = field(default_factory=list)
    narrative_tags: List[str] = field(default_factory=list)
    
    encounter_bias: Dict[str, float] = field(default_factory=dict)
    economy_modifier: Dict[str, float] = field(default_factory=dict)
    
    travel_cost_mod: float = 1.0
    blocked: bool = False
    
    resonance_modifier: Dict[str, float] = field(default_factory=dict)
    
    # 충돌로 인한 창발적 효과
    emergent_effects: Dict[str, Any] = field(default_factory=dict)
    
    # 적용된 오버레이 기록
    applied_overlays: List[str] = field(default_factory=list)
    
    def merge(
        self, 
        effects: OverlayEffects, 
        overlay: BaseOverlay
    ) -> Optional["OverlayConflict"]:
        """효과 병합, 충돌 시 Conflict 반환"""
        
        conflict = None
        
        # 날씨: 덮어쓰기 (우선순위 높은 것이 이김)
        if effects.weather_override:
            if self.weather and self.weather != effects.weather_override:
                conflict = OverlayConflict(
                    conflict_type="weather",
                    values=[self.weather, effects.weather_override],
                    overlays=[self.applied_overlays[-1], overlay.overlay_id],
                )
            self.weather = effects.weather_override
        
        # 수치: 가산
        self.temperature_mod += effects.temperature_mod
        self.visibility_mod += effects.visibility_mod
        
        # 태그: 누적
        self.dialogue_tags.extend(effects.dialogue_tags)
        self.narrative_tags.extend(effects.narrative_tags)
        
        # 조우 확률: 가산
        for k, v in effects.encounter_bias.items():
            self.encounter_bias[k] = self.encounter_bias.get(k, 0.0) + v
        
        # 경제 수정자: 승산
        for k, v in effects.economy_modifier.items():
            self.economy_modifier[k] = self.economy_modifier.get(k, 1.0) * v
        
        # 이동 비용: 승산
        self.travel_cost_mod *= effects.travel_cost_mod
        
        # 통행 불가: OR
        self.blocked = self.blocked or effects.blocked
        
        # 공명 수정자: 가산
        for k, v in effects.resonance_modifier.items():
            self.resonance_modifier[k] = self.resonance_modifier.get(k, 0.0) + v
        
        self.applied_overlays.append(overlay.overlay_id)
        
        return conflict
```

### 8.3 OverlayConflict

```python
@dataclass
class OverlayConflict:
    """오버레이 충돌 정보"""
    
    conflict_type: str      # "weather", "policy", "quest"
    values: List[str]       # 충돌하는 값들
    overlays: List[str]     # 충돌하는 오버레이 ID들
```

---

## 9. 노드 진입 처리 흐름

### 9.1 전체 파이프라인

```python
def on_node_enter(player: "Player", node_id: str) -> "NodeContext":
    """노드 진입 시 오버레이 포함 전체 처리"""
    
    # 1. 기반 지리 정보 (L0~L1)
    geography = geography_module.get_node(node_id)
    
    # 2. 오버레이 효과 병합 (L2~L5)
    merged_effects = overlay_manager.get_merged_effects(node_id)
    
    # 3. 통행 체크
    if merged_effects.blocked:
        return NodeContext(
            blocked=True,
            block_reason="이 지역은 현재 통행이 불가능합니다.",
        )
    
    # 4. 영유권 체크
    territory_overlays = [
        o for o in overlay_manager.get_overlays_at_node(node_id)
        if o.overlay_type == OverlayType.TERRITORY
    ]
    for territory in territory_overlays:
        permitted, message = territory.check_entry_permission(player)
        if not permitted:
            return NodeContext(blocked=True, block_reason=message)
    
    # 5. 최종 날씨 결정
    final_weather = merged_effects.weather or geography.default_weather
    
    # 6. NPC 대화 컨텍스트에 오버레이 태그 주입
    npcs = npc_module.get_npcs_at_node(node_id)
    for npc in npcs:
        npc.dialogue_context.overlay_tags = merged_effects.dialogue_tags
    
    # 7. 조우 판정 (오버레이 bias 적용)
    encounter = combat_module.roll_encounter(
        node_id,
        geography.base_encounters,
        merged_effects.encounter_bias,
    )
    
    # 8. 서술 컨텍스트 생성
    narrative_context = NarrativeContext(
        geography=geography,
        weather=final_weather,
        narrative_tags=merged_effects.narrative_tags,
        emergent_effects=merged_effects.emergent_effects,
        applied_overlays=merged_effects.applied_overlays,
    )
    
    # 9. AI 서술 생성
    description = narrative_service.describe_node(narrative_context)
    
    return NodeContext(
        geography=geography,
        weather=final_weather,
        overlay_effects=merged_effects,
        npcs=npcs,
        encounter=encounter,
        description=description,
    )
```

### 9.2 서술 생성 예시

```python
# 가뭄 저주 퀘스트 활성화 상태 + severity 0.7

narrative_context = NarrativeContext(
    geography=village_node,
    weather="drought",
    narrative_tags=["cracked_earth", "wilted_crops", "dry_well", "severe"],
    emergent_effects={},
    applied_overlays=["overlay_drought_001"],
)

# AI에게 전달되는 프롬프트:
"""
장소: 마을 광장
날씨: 가뭄
환경 태그: 갈라진 땅, 시든 작물, 마른 우물, 심각함
적용된 효과: 마른 땅의 저주

위 조건을 반영하여 플레이어가 이 장소에 도착했을 때의 묘사를 작성하세요.
"""

# AI 출력:
"""
갈라진 땅이 발 아래서 삐걱거립니다. 한때 풍요로웠을 밭에는 
시든 작물만이 흙먼지 속에 쓰러져 있고, 마을 중앙의 우물은 
바닥을 드러낸 지 오래입니다. 주민들의 눈에는 절망이 서려 있습니다.
"""
```

---

## 10. 퀘스트-오버레이 연동

### 10.1 퀘스트 생성 시 오버레이 자동 생성

```python
def create_quest_with_overlay(
    quest_data: "QuestData",
    affected_nodes: Set[str],
    effects_template: Dict[str, Any],
) -> Tuple["Quest", QuestOverlay]:
    """퀘스트 생성 시 오버레이 함께 생성"""
    
    # 퀘스트 생성
    quest = Quest(
        quest_id=generate_uuid(),
        title=quest_data.title,
        description=quest_data.description,
        # ...
    )
    
    # 오버레이 생성
    overlay = QuestOverlay(
        overlay_id=f"overlay_{quest.quest_id}",
        name=f"{quest.title} 영향권",
        quest_id=quest.quest_id,
        quest_title=quest.title,
        affected_nodes=affected_nodes,
        effects_template=effects_template,
        severity=quest_data.initial_severity,
        severity_growth_rate=quest_data.growth_rate,
        created_turn=current_turn,
    )
    
# 퀘스트 등록 및 이벤트 발행
    quest_engine.register_quest(quest)
    
    event_bus.emit("quest_created", {
        "quest_id": quest.quest_id,
        "affected_nodes": list(affected_nodes),
        "effects_template": effects_template,
    })
    # → overlay_core 모듈이 구독하여 QuestOverlay 생성
    
    return quest
```

### 10.2 퀘스트 진행에 따른 오버레이 변화

```python
def on_quest_objective_complete(quest_id: str, objective_index: int) -> None:
    """퀘스트 목표 완료 시"""
    
    overlay = overlay_manager.get_overlay_by_quest(quest_id)
    if overlay:
        # 진행도에 따라 severity 감소
        progress = quest_engine.get_quest_progress(quest_id)
        overlay.on_quest_progress(progress)

def on_quest_complete(quest_id: str) -> None:
    """퀘스트 완료 시"""
    
    overlay = overlay_manager.get_overlay_by_quest(quest_id)
    if overlay:
        overlay.on_quest_complete()
        # 서서히 회복 (즉시 제거하지 않음)

def on_quest_failed(quest_id: str) -> None:
    """퀘스트 실패 시"""
    
    overlay = overlay_manager.get_overlay_by_quest(quest_id)
    if overlay:
        overlay.on_quest_failed()
        # 영구화되거나 최악의 상태로 고정
```

### 10.3 이벤트 흐름

**퀘스트-오버레이 연동 이벤트**:
```
quest_engine                         overlay_core
     |                                    |
     |--emit("quest_created")------------>|
     |                                    |--> create_quest_overlay()
     |                                    |
     |--emit("quest_progress")----------->|
     |                                    |--> overlay.on_quest_progress()
     |                                    |
     |--emit("quest_completed")---------->|
     |                                    |--> overlay.on_quest_complete()
```

**오버레이가 발행하는 이벤트**:

| 이벤트 | 조건 | 구독자 |
|--------|------|--------|
| `overlay_severity_critical` | severity > 0.8 | quest_engine, narrative |
| `overlay_area_expanded` | 영향권 확장 시 | narrative |

---

## 11. DB 스키마

### 11.1 overlay_zones 테이블

```python
class OverlayZoneModel(Base):
    """오버레이 DB 모델"""
    __tablename__ = "overlay_zones"
    
    overlay_id: str = Column(String, primary_key=True)
    overlay_type: str = Column(String, nullable=False)
    name: str = Column(String, nullable=False)
    
    priority: int = Column(Integer, default=0)
    
    # JSON으로 저장
    affected_nodes: str = Column(JSON)  # Set → List로 직렬화
    
    is_active: bool = Column(Boolean, default=True)
    severity: float = Column(Float, default=1.0)
    
    created_turn: int = Column(Integer, nullable=False)
    expires_turn: int = Column(Integer, nullable=True)
    
    # 타입별 추가 데이터
    data: str = Column(JSON)  # 타입별 세부 데이터
```

### 11.2 직렬화/역직렬화

```python
def serialize_overlay(overlay: BaseOverlay) -> Dict[str, Any]:
    """오버레이 → DB 저장용 dict"""
    
    return {
        "overlay_id": overlay.overlay_id,
        "overlay_type": overlay.overlay_type.value,
        "name": overlay.name,
        "priority": overlay.priority,
        "affected_nodes": list(overlay.affected_nodes),
        "is_active": overlay.is_active,
        "severity": overlay.severity,
        "created_turn": overlay.created_turn,
        "expires_turn": overlay.expires_turn,
        "data": overlay.dict(exclude={
            "overlay_id", "overlay_type", "name", "priority",
            "affected_nodes", "is_active", "severity",
            "created_turn", "expires_turn"
        }),
    }

def deserialize_overlay(row: OverlayZoneModel) -> BaseOverlay:
    """DB 행 → 오버레이 객체"""
    
    overlay_type = OverlayType(row.overlay_type)
    data = json.loads(row.data) if isinstance(row.data, str) else row.data
    
    OVERLAY_CLASSES = {
        OverlayType.WEATHER: WeatherOverlay,
        OverlayType.TERRITORY: TerritoryOverlay,
        OverlayType.QUEST: QuestOverlay,
        OverlayType.EVENT: EventOverlay,
    }
    
    cls = OVERLAY_CLASSES[overlay_type]
    
    return cls(
        overlay_id=row.overlay_id,
        name=row.name,
        priority=row.priority,
        affected_nodes=set(row.affected_nodes),
        is_active=row.is_active,
        severity=row.severity,
        created_turn=row.created_turn,
        expires_turn=row.expires_turn,
        **data,
    )
```

---

## 12. 구현 우선순위

### Alpha 필수

- overlay_core 모듈 (BaseOverlay, OverlayManager)
- 기본 병합 로직
- MergedEffects 구조

### Alpha 후

- weather_overlay
- quest_overlay
- 노드 진입 시 오버레이 통합
- 충돌 처리 기초

### 미래 확장

- territory_overlay
- event_overlay
- 창발적 효과 생성
- 복잡한 충돌 해결

---

## 13. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| 1.0 | 2025-02-07 | 최초 작성 |
