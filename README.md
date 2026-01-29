# infinite_text_world

TODO: 프로젝트 설명 추가

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
