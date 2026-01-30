# AI Provider 추상화 설계

## 개요
여러 LLM API를 유연하게 교체할 수 있는 추상화 레이어

## 지원 Provider
| Provider | 상태 | 용도 |
|----------|------|------|
| mock | 구현 | 테스트/Fallback |
| gemini | 구현 예정 | Gemini API |
| openai | 예정 | GPT-4 등 |
| anthropic | 예정 | Claude API |
| ollama | 예정 | 로컬 무료 |

## 폴더 구조
```
src/services/ai/
├── __init__.py
├── base.py          # 추상 인터페이스
├── factory.py       # Provider 팩토리
├── mock.py          # Mock 구현
└── gemini.py        # Gemini 구현
```

## 인터페이스
```python
class AIProvider(ABC):
    def generate(prompt: str, context: dict) -> str
    def is_available() -> bool
    @property name -> str
```

## 설정
환경변수:
- AI_PROVIDER: provider 선택 (기본: mock)
- AI_API_KEY: API 키
- AI_MODEL: 모델명 (선택)
- AI_BASE_URL: 커스텀 URL (선택)

## 사용 예시
```python
provider = get_ai_provider()
text = provider.generate("prompt here")
```

## Fallback 정책
1. API 키 없음 → MockProvider 사용
2. API 에러 → 기본 텍스트 반환
3. Provider 없음 → MockProvider 사용
