# Nexus System & Travel Montage Specification
**Version:** 1.0.0
**Author:** Main Creative Director (Gemini)
**Phase:** 1 (Persistence & Core Mechanics)

## 1. Overview
이 문서는 ITW의 핵심 메커니즘인 **Nexus System (비동기 협력/건설)**과 **Travel Montage (이동 생략/인카운터)**의 데이터 구조 및 로직 명세를 정의한다. 이 명세는 `Phase 1: SQLite Persistence` 구현 시 반드시 반영되어야 한다.

---

## 2. Database Schema Requirements (SQLAlchemy)

### 2.1. MapNode (Extension)
기존 `MapNode` 모델에 다음 필드를 추가하여 노드의 상태와 발전도를 추적한다.

| Field Name | Type | Description |
|---|---|---|
| `visit_count` | Integer | 해당 노드에 유저가 진입한 총 횟수 (기본값: 0) |
| `danger_rating` | Float | 0.0 ~ 1.0. 이동 시 인카운터 발생 확률 계수 (기본값: 지형별 상이) |
| `is_settlement` | Boolean | `visit_count`와 `structure_score`가 임계치를 넘으면 True로 전환 |
| `environment_log` | JSON | (Optional) 유저 행동으로 인한 환경 변화 로그 (예: 화재 발생 여부) |

### 2.2. MapStructure (New Table)
유저가 건설한 구조물을 저장하는 테이블.

| Field Name | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `node_id` | FK | 해당 구조물이 위치한 MapNode의 ID |
| `creator_id` | FK | 최초 건설자 Player ID |
| `type` | String | Enum: `SIGN`, `CACHE`, `SHELTER`, `BRIDGE`, `ROPE`, `CAMPFIRE` |
| `tier` | Integer | 구조물 등급 (1~3). 기부(Upgrade)를 통해 상승. |
| `durability` | Integer | 내구도. 0이 되면 기능 정지 (파괴되지 않고 '수리 필요' 상태) |
| `metadata` | JSON | 구조물별 특수 데이터 (예: 표지판의 텍스트, 보관함의 인벤토리 ID) |
| `likes` | Integer | 타 유저에게 받은 좋아요 수 |

### 2.3. Player (Extension)
| Field Name | Type | Description |
|---|---|---|
| `karma` | Integer | 타인에게 받은 좋아요 누적 수치. API 토큰 한도 등에 영향. |

### 2.4. InteractionLog (New Table)
중복 '좋아요' 방지 및 행동 추적용.

| Field Name | Type | Description |
|---|---|---|
| `id` | UUID | PK |
| `actor_id` | FK | 행동한 유저 ID |
| `target_structure_id` | FK | 대상 구조물 ID |
| `action_type` | String | `LIKE`, `REPAIR`, `UPGRADE` |
| `timestamp` | DateTime | 행동 시각 |

---

## 3. Core Logic Specification

### 3.1. Nexus System Logic
#### Construction (건설)
- **조건:** 유저는 인벤토리에 특정 Axiom 조합(`Materia` + `Ordo`)과 자원을 보유해야 함.
- **프로세스:**
  1. `ConstructionRequest` 수신 (좌표, 타입).
  2. 자원 소모 검증.
  3. `MapStructure` 레코드 생성.
  4. 해당 `MapNode`의 `visit_count` 또는 환경 변수 업데이트.

#### Structure Evolution (마을 발생)
- 특정 노드에 `MapStructure`가 5개 이상이고, `visit_count`가 100 이상일 경우:
- **System Action:** 해당 노드의 `biome_type`을 `SETTLEMENT`로 변경하거나, `is_settlement` 플래그를 True로 설정.
- **Narrative Effect:** 이후 해당 노드 묘사 시 AI 프롬프트에 "작은 정착지"라는 Context 주입.

### 3.2. Travel Montage Logic (Fast Travel)

#### Algorithm: `execute_travel`
유저가 "A에서 B로 이동"을 선언했을 때 실행되는 로직.

1.  **Path Validation:**
    * A와 B 사이의 경로를 계산 (단순 거리 계산 or A*).
    * 경로상의 모든 노드가 `explored=True` (한 번이라도 방문함) 상태인지 확인.
    * 아니라면 이동 불가 (탐험 모드로 한 칸씩 가야 함).

2.  **Cost Calculation:**
    * `Total Stamina` = Sum(Node.movement_cost for Node in Path) - (Structures Bonus).
    * *Note:* 다리(`BRIDGE`)나 로프(`ROPE`)가 있는 노드는 비용 대폭 감소.

3.  **Risk Assessment (The Montage Roll):**
    * 이동 경로 전체에 대해 **단 1회의 통합 주사위 굴림** 실행.
    * `Risk Score` = Average(`danger_rating` of path nodes).
    * Roll 1d100.
    * **IF Roll > Risk Score:**
        * **Result:** SUCCESS.
        * **Action:** 유저 좌표를 B로 즉시 변경. 스태미나 차감.
        * **Output:** "여행 요약문" 생성 (AI 비용 최소화).
    * **IF Roll <= Risk Score:**
        * **Result:** INTERRUPTION.
        * **Action:** 경로 중 `danger_rating`이 가장 높은 지점(X, Y)에서 이동 강제 중단.
        * **Output:** 해당 지점에서 "인카운터(전투/재난)" 발생 메시지 출력.

---

## 4. AI Prompting Strategy (Optimization)
- **Travel Success:** AI에게 전체 묘사를 맡기지 말고, 시스템이 생성한 템플릿 문장을 사용하거나 매우 짧은 토큰(50 tokens)만 사용.
  - *Template:* "당신은 [출발지]를 떠나 [도착지]까지 무사히 도착했습니다. 도중에 [구조물 이름] 덕분에 편안히 이동했습니다."
- **Travel Interruption:** 이때만 정상적인 Scene Description 프롬프트 가동.