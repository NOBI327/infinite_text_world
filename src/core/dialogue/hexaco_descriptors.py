"""HEXACO 수치 → 자연어 변환 (LLM 프롬프트용)

dialogue-system.md 섹션 7.3 대응.
"""

HEXACO_DESCRIPTORS: dict[str, list[tuple[float, float, str]]] = {
    "H": [
        (0.0, 0.3, "利益に敏感で実利的だ"),
        (0.3, 0.7, "普通レベルの誠実さ"),
        (0.7, 1.0, "正直で謙虚だ"),
    ],
    "E": [
        (0.0, 0.3, "大胆で感情に揺れない"),
        (0.3, 0.7, "普通レベルの感受性"),
        (0.7, 1.0, "心配性で感情的だ"),
    ],
    "X": [
        (0.0, 0.3, "寡黙で一人を好む"),
        (0.3, 0.7, "普通レベルの社交性"),
        (0.7, 1.0, "外向的でおしゃべりだ"),
    ],
    "A": [
        (0.0, 0.3, "批判的で対立を恐れない"),
        (0.3, 0.7, "普通レベルの寛容さ"),
        (0.7, 1.0, "寛大で協力的だ"),
    ],
    "C": [
        (0.0, 0.3, "衝動的で即興的だ"),
        (0.3, 0.7, "普通レベルの勤勉さ"),
        (0.7, 1.0, "体系的で慎重だ"),
    ],
    "O": [
        (0.0, 0.3, "伝統的で慣れたものを好む"),
        (0.3, 0.7, "普通レベルの開放性"),
        (0.7, 1.0, "好奇心が強く新しいものを好む"),
    ],
}


def hexaco_to_natural_language(hexaco_values: dict[str, float]) -> str:
    """HEXACO dict → 자연어 성격 묘사 문자열.

    Args:
        hexaco_values: {"H": 0.8, "E": 0.3, "X": 0.7, "A": 0.6, "C": 0.5, "O": 0.4}

    Returns:
        "このNPCは正直で謙虚(H)、大胆で感情に揺れない(E)、..."
    """
    parts: list[str] = []
    for factor in ("H", "E", "X", "A", "C", "O"):
        value = hexaco_values.get(factor, 0.5)
        for low, high, desc in HEXACO_DESCRIPTORS.get(factor, []):
            if low <= value < high or (high == 1.0 and value == 1.0):
                parts.append(f"{desc}({factor})")
                break
    return "このNPCは" + "、".join(parts) + "。"
