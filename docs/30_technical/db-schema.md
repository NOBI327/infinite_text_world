# DB 스키마 (예정)

## map_nodes
- coordinate (PK): "x_y" 형식
- tier: Common/Uncommon/Rare
- axiom_vector: JSON
- sensory_data: JSON

### 레이어 필드 (추가 예정)

#### L0 - Biome
- biome_id: STRING (FK to biomes)

#### L1 - Infrastructure
- infrastructure_type: STRING (nullable)
- infrastructure_health: FLOAT (default 1.0)

#### L2 - Facility
- facility_type: STRING (nullable)
- facility_owner_id: STRING (nullable)

#### L3 - Depth
- depth_name: STRING (nullable)
- depth_tier: INTEGER (nullable)
- depth_entry_condition: STRING (nullable)
- depth_discovered: BOOLEAN (default false)

## players
- player_id (PK)
- x, y: 위치
- supply, fame: 상태
- character_data: JSON

## 신규 테이블 (추가 예정)

### biomes
- id: STRING PK
- name_kr: STRING
- base_tags: JSON
- base_modifiers: JSON
- weather_interpretation: JSON
