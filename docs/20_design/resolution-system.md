# 판정 시스템 설계 (Protocol T.A.G.)

## 개요
모든 판정은 d6 Dice Pool 시스템으로 통일

## 핵심 규칙

### Dice Pool 구성
- Base Dice: 캐릭터 스탯 (WRITE/READ/EXEC/SUDO)
- Bonus Dice: 유리한 태그, 상황 보너스
- Penalty Dice: 불리한 상황, 페널티

### 판정 공식

### 난이도 기준
| 난이도 | 필요 Hit | 설명 |
|--------|----------|------|
| 1 | 1 | 쉬움 |
| 2 | 2 | 보통 |
| 3 | 3 | 어려움 |
| 4 | 4 | 매우 어려움 |
| 5+ | 5+ | 극한 |

### 결과 티어
- Critical Success: Hits >= Difficulty + 2
- Success: Hits >= Difficulty
- Failure: Hits < Difficulty
- Critical Failure: Hits = 0 AND 1이 존재

## 적용 범위
- 전투: WRITE (공격), EXEC (방어/회피)
- 조사: READ
- 사회: SUDO
- 제작/기술: EXEC

## 조사 시스템 (Echo)
기존 d20 시스템 폐기, d6 Pool로 변경

### 조사 난이도 변환
| 기존 DC | 신규 Difficulty |
|---------|-----------------|
| 5-9 | 1 |
| 10-14 | 2 |
| 15-19 | 3 |
| 20-24 | 4 |
| 25+ | 5 |
