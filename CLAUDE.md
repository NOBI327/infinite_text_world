# ITW Development Guide

## Project
Text-based procedural single-player TRPG engine (Python/FastAPI/SQLite)

## Git Convention
- 논리 단위마다 즉시 커밋 + push
- 커밋 전: ruff check src/ tests/ && pytest tests/ -v
- 메시지: Conventional Commits (feat/fix/docs/test/refactor/chore)
- git push origin main

## Structure
- src/core/ - Game logic (no DB dependency)
- src/modules/ - Toggleable feature modules (GameModule interface)
- src/services/ - Business logic with DB
- src/db/ - ORM models
- src/api/ - FastAPI endpoints
- docs/ - Documentation

## Documentation
- WHY: docs/10_product/
- WHAT: docs/20_design/
- HOW: docs/30_technical/
- RUN: docs/40_operations/
- 구현 지시서: docs/40_operations/instructions/

## Reference
- docs/INDEX.md - 설계 문서 인덱스
- docs/SRC_INDEX.md - 소스 코드 인덱스
- 작업 전 관련 문서를 먼저 읽을 것

## Architecture Rules
- 의존 방향: API → Service → Core → DB (역방향 금지)
- Module → Core, Module → DB 허용. Module → Module 금지
- Service간 직접 호출 금지, EventBus 경유
- Core는 DB를 모른다, Service가 Core와 DB를 연결
- 상세: docs/30_technical/architecture.md 참조

## Rules
1. Code is truth (if implemented)
2. Ask user if unclear (if not implemented)
3. Don't guess - read docs/INDEX.md, docs/SRC_INDEX.md first
4. 다른 서비스를 직접 import하지 말 것

## Quality Gates
1. ruff check - 린트 통과
2. pytest - 테스트 통과
3. pytest --cov - 커버리지 70%+
4. mypy - 타입 체크 통과

## Logging
- print() 사용 금지
- logging 모듈 사용
- 레벨: DEBUG < INFO < WARNING < ERROR
