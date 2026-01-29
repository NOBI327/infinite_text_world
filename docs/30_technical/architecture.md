# 아키텍처

## 레이어 구조
API Layer (src/api/)
    ↓
Service Layer (src/services/)
    ↓
Core Layer (src/core/)
    ↓
DB Layer (src/db/)

## 의존성 규칙
- Core는 DB를 모른다
- Service가 Core와 DB를 연결
- API는 Service만 호출
