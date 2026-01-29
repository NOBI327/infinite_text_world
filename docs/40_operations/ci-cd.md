# CI/CD

## GitHub Actions
- 트리거: push/PR to main
- 단계: ruff check → pytest

## 로컬 검증
커밋 전 실행:
1. ruff check src/ tests/
2. pytest -v
