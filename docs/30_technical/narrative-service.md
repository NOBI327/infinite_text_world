# Narrative Service 설계

## 개요
AI Provider를 사용해 게임 서술을 생성하는 서비스

## 책임
- look 액션 서술 생성
- move 액션 서술 생성
- fallback 서술 제공

## 클래스 구조
```python
class NarrativeService:
    def __init__(ai_provider: AIProvider)
    def generate_look(node_data: dict, player_state: dict) -> str
    def generate_move(from_node: dict, to_node: dict, direction: str) -> str
```

## Fallback 정책
- AI 사용 불가 → 기본 템플릿 서술
- API 에러 → 기본 템플릿 서술
- 예외 발생 → 기본 템플릿 서술

## 프롬프트 템플릿

### look 프롬프트
- 위치 정보 (좌표, 등급, 특성)
- 감각 정보 (시각, 청각)
- 2-3문장 묘사 요청

### move 프롬프트
- 출발지/도착지 정보
- 이동 방향
- 1-2문장 이동 묘사 요청
