# Game API 명세

## Base URL
```
http://localhost:8000
```

## 엔드포인트

### POST /game/register
플레이어를 등록하고 Safe Haven(0,0)에서 시작합니다.

**Request:**
```json
{
  "player_id": "test_player"
}
```

**Response (200):**
```json
{
  "success": true,
  "player": {
    "player_id": "test_player",
    "x": 0,
    "y": 0,
    "supply": 20,
    "fame": 0,
    "inventory": {},
    "discovered_count": 1
  },
  "location": {
    "location_id": "1eebfe13",
    "visual": "...",
    "atmosphere": "...",
    "sound": "...",
    "smell": "...",
    "special_features": ["안전 지대 보호막 작동"],
    "resources": [
      {"type": "res_basic_supply", "abundance": "풍부함"}
    ],
    "echoes": []
  },
  "directions": [
    {
      "direction": "N",
      "visual_hint": "...",
      "atmosphere_hint": "...",
      "danger_level": "Safe",
      "discovered": false
    }
  ]
}
```

---

### GET /game/state/{player_id}
플레이어의 현재 게임 상태를 조회합니다.

**Response (200):**
GameStateResponse (register와 동일한 형식)

**Response (404):**
```json
{
  "detail": "Player not found: {player_id}"
}
```

---

### POST /game/action
게임 액션을 실행합니다.

**Request:**
```json
{
  "player_id": "test_player",
  "action": "look|move|rest|investigate|harvest",
  "params": {}
}
```

#### 지원 액션

| 액션 | params | 설명 |
|------|--------|------|
| `look` | - | 현재 위치 관찰 |
| `move` | `{"direction": "n\|s\|e\|w"}` | 이동 (Supply 소모) |
| `rest` | - | 휴식 (Supply 회복) |
| `investigate` | `{"echo_index": 0}` | Echo 조사 |
| `harvest` | `{"resource_id": "...", "amount": 1}` | 자원 채취 |

**Response (200):**
```json
{
  "success": true,
  "action": "move",
  "message": "북쪽으로 이동했습니다. Supply -1",
  "data": {
    "supply_consumed": 1,
    "remaining_supply": 19
  },
  "location": { ... }
}
```

**Response (400):**
```json
{
  "detail": "Missing 'direction' parameter"
}
```
```json
{
  "detail": "Unknown action: invalid. Valid actions: look, move, rest, investigate, harvest"
}
```

**Response (404):**
```json
{
  "detail": "Player not found: {player_id}"
}
```

---

## 에러 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (파라미터 누락, 알 수 없는 액션) |
| 404 | 플레이어 없음 |
| 500 | 서버 내부 오류 |

---

## Health Check

### GET /health
서버 상태 확인

**Response (200):**
```json
{
  "status": "healthy"
}
```
