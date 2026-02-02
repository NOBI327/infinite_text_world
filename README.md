# Infinite Text World (ITW)

1인용 텍스트 기반 절차적 생성 TRPG 엔진

## 특징
- 절차적 월드 생성
- 서브 그리드 맵 시스템 (던전, 숲, 탑 등)
- AI 기반 서술 생성
- Protocol T.A.G. 판정 시스템

## 기술 스택
- Python 3.11
- FastAPI
- SQLite + SQLAlchemy
- Gemini API (또는 다른 LLM)

## 개발 환경 설정

### 의존성 설치

```bash
pip install -e ".[dev]"
```

### Pre-commit 설정

```bash
pre-commit install
```

이후 git commit 시 자동으로 다음이 실행됩니다:
- ruff (린터 + 자동 수정)
- ruff-format (코드 포맷터)
- pytest (테스트)

### 수동 실행

```bash
# 린트 체크
ruff check src/ tests/

# 테스트 실행
pytest -v

# pre-commit 전체 실행
pre-commit run --all-files
```
