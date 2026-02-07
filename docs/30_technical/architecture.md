# 아키텍처

## 레이어 구조
```
API Layer (src/api/)
    ↓
Service Layer (src/services/)
    ↓
Core Layer (src/core/)
    ↓
DB Layer (src/db/)
```

## 의존성 규칙
- Core는 DB를 모른다
- Service가 Core와 DB를 연결
- API는 Service만 호출
- **Service는 다른 Service를 직접 호출하지 않는다**

## 서비스 간 통신 원칙

### 규칙
- 서비스는 다른 서비스를 직접 import하거나 호출하지 않는다.
- 서비스 간 통신은 반드시 EventBus를 경유한다.
- 각 서비스는 자신의 도메인 이벤트를 발행(emit)하고, 관심 있는 이벤트를 구독(subscribe)한다.
- 데이터는 DB에만 존재하며, 이벤트는 식별자(ID)만 전달한다.

### 허용되는 의존 방향

| 방향 | 예시 | 허용 |
|------|------|------|
| Service → Core | npc_service → core_rule | ✅ |
| Service → DB | npc_service → models | ✅ |
| Service → EventBus | npc_service → event_bus | ✅ |
| Service → Service | npc_service → quest_service | ❌ |

### 이벤트 흐름 예시

퀘스트로 인한 NPC 생성:

1. `quest_service`가 퀘스트 활성화 후 `npc_needed` 이벤트 발행
2. `npc_service`가 `npc_needed` 구독, NPC 생성 후 `npc_created` 발행
3. `quest_service`가 `npc_created` 구독, 해당 NPC를 퀘스트에 연결

```
quest_service --emit("npc_needed")--> [EventBus]
[EventBus] --deliver--> npc_service
npc_service --emit("npc_created")--> [EventBus]
[EventBus] --deliver--> quest_service
```

### 무한 루프 방지
- 동일 원인에서 동일 이벤트 중복 발행 금지
- 한 턴 내 이벤트 전파 깊이 최대 5단계로 제한
- 퀘스트 자동 생성 시 쿨다운(최소 N턴 간격) 적용

## EventBus 도입 시점
- 현재(Phase 1): 서비스 간 직접 호출 없음 → EventBus 불필요
- Phase 2(NPC/관계/퀘스트 추가 시): `src/core/event_bus.py` 구현 및 적용
- EventBus 인프라는 NPC 시스템 구현과 동시에 도입한다
