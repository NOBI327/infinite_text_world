# 월드 레이어 시스템 설계

## 개요
기존 MapNode/AxiomVector 시스템과 4-Layer Geography를 통합한 설계

## 기존 시스템 (현재)
- MapNode: 좌표, tier, axiom_vector, sensory_data, resources, echoes
- AxiomVector: 214 Divine Axioms 기반 태그 벡터
- NodeTier: Common/Uncommon/Rare

## 신규 레이어 시스템

### L0 - Biome (기저층)
- 기존 axiom_vector를 biome_tags로 확장
- 불변 속성 (지형, 기후, 식생)
- weather_interpretation 딕셔너리 추가

### L1 - Infrastructure (연결층)
- 기존 required_tags 확장
- infrastructure_type: Road, Bridge, Tunnel 등
- infrastructure_health: 0.0~1.0 (수리 가능)
- 이동 비용(move_cost) 영향

### L2 - Facility (기능층)
- 기존 resources 확장
- facility_type: Mine, Inn, Farm, Wall 등
- owner_id: NPC 또는 플레이어 소유
- 자원 생산/서비스 제공

### L3 - Depth (심연층)
- 신규 추가
- 서브 그리드 진입점
- depth_name, depth_tier, entry_condition
- is_discovered: 발견 여부

## 통합 방식
| 기존 | 신규 | 처리 |
|------|------|------|
| axiom_vector | L0 biome_tags | 공존 (axiom은 세부, biome은 분류) |
| NodeTier | depth_tier | 별개 (NodeTier=희귀도, depth_tier=난이도) |
| required_tags | L1 infrastructure | 통합 |
| resources | L2 facility | 확장 |
| 없음 | L3 depth | 신규 |

## 구현 우선순위
1. L3 Depth (서브 그리드) - MVP 필수
2. L0 Biome 확장 - 컨텐츠 다양성
3. L1 Infrastructure - 이동 시스템 강화
4. L2 Facility - 경제 시스템

## 향후 확장 (별도 Phase)
- Weather 시스템
- Territory 시스템
