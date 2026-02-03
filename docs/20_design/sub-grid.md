# 서브 그리드 시스템

## 개요
메인 그리드 노드 내부로 진입하는 확장 공간

## 좌표 체계

### 메인 그리드
- 좌표: (x, y)
- 이동: n, s, e, w

### 서브 그리드
- 좌표: (parent_x, parent_y, sx, sy, sz)
- parent: 진입한 메인 노드
- sx, sy: 서브 그리드 내 수평 위치
- sz: 서브 그리드 내 수직 위치 (0=입구)
- 이동: n, s, e, w, up, down

## 서브 그리드 유형

| 유형 | 구조 | sz 범위 | 예시 |
|------|------|---------|------|
| Dungeon | 하강형 | 0 ~ -N | 지하묘지, 폐광 |
| Tower | 상승형 | 0 ~ +N | 마법사 탑 |
| Forest | 수평형 | 0 (고정) | 깊은 숲, 미로 |
| Cave | 복합형 | -N ~ +M | 자연 동굴 |

## 명령어

| 명령 | 위치 | 동작 |
|------|------|------|
| enter | 메인 (L3 있는 노드) | 서브 그리드 진입 |
| exit | 서브 (sz=0, 입구) | 메인 그리드 복귀 |
| up | 서브 | sz += 1 |
| down | 서브 | sz -= 1 |

## 생성 방식
- 절차적 생성 (메인 그리드와 동일)
- 시드: hash(parent_x, parent_y, depth_name)
- 층별 난이도: depth_tier + abs(sz)

## 데이터 모델

### SubGridNode
- parent_coordinate: STRING (FK to map_nodes)
- sx, sy, sz: INTEGER
- tier: STRING
- axiom_vector: JSON
- (기타 MapNode와 동일)
