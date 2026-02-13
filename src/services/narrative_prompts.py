"""호출 유형별 프롬프트 빌더

narrative-service.md 섹션 4 대응.
"""

import json
import logging

from src.services.narrative_safety import ContentSafetyFilter
from src.services.narrative_types import (
    BuiltPrompt,
    DialoguePromptContext,
    NarrativeConfig,
    QuestSeedPromptContext,
)

logger = logging.getLogger(__name__)

DIALOGUE_TOKEN_MAP = {
    "open": 500,
    "winding": 400,
    "closing": 300,
    "final": 200,
}

# --- System Prompt Templates ---

LOOK_SYSTEM_PROMPT = """\
あなたはITW（Infinite Text World）の語り手です。

世界設定:
- 舞台は「西域」— 東の帝国から追放された人間たちが暮らす辺境
- 214のDivine Axiomが物理法則として機能する世界
- 「魔法」禁止。「公理技術」と表現

語りのルール:
- 二人称現在形（「あなたは〜する」）
- 感覚: 視覚＋もう1つ以上
- 短い文。一文に一つの情報
- 禁止: 感嘆符, システム用語, 座標, 数値, メタ発言, 「魔法」"""

MOVE_SYSTEM_PROMPT = """\
あなたはITW（Infinite Text World）の語り手です。
プレイヤーの移動を1〜2文で簡潔に描写してください。
禁止: 感嘆符, システム用語, 座標, 数値"""

DIALOGUE_SYSTEM_PROMPT = """\
あなたはITWのNPCとして会話します。

出力形式:
必ず以下のJSON形式で応答してください。他のテキストは含めないでください。

{{
  "narrative": "NPCの発言と行動描写（プレイヤーに見せる部分）",
  "meta": {{
    "dialogue_state": {{
      "wants_to_continue": true,
      "end_conversation": false,
      "topic_tags": []
    }},
    "relationship_delta": {{
      "affinity": 0,
      "reason": "none"
    }},
    "memory_tags": [],
    "quest_seed_response": null,
    "action_interpretation": null,
    "trade_request": null,
    "gift_offered": null
  }}
}}

会話ルール:
- manner_tagsに従った話し方
- 職業/種族に合った語彙のみ
- 座標、数値、システム用語禁止
- relationship_delta.affinityは-5〜+5の範囲
- memory_tagsは重要な会話内容をタグ化"""

QUEST_SEED_SYSTEM_PROMPT = """\
あなたはITWのクエストシード生成器です。
NPC情報と地域情報をもとに、自然な依頼・噂・警告を生成してください。

Tier指示:
  Tier 1(大): 複数NPCが関わる大規模な物語。伏線を2~3本設置せよ。
  Tier 2(中): 個人的な事情が絡む中規模の物語。伏線を1~2本設置せよ。
  Tier 3(小): 単発の頼みごと。伏線不要。

出力形式:
{{
  "narrative": "NPCがシードを伝える発言",
  "meta": {{
    "title_hint": "クエストタイトルのヒント",
    "quest_type_hint": "fetch|escort|investigate|negotiate|craft",
    "urgency_hint": "low|medium|high",
    "context_tags": ["tag1", "tag2"]
  }}
}}"""

IMPRESSION_TAG_SYSTEM_PROMPT = """\
NPCの立場から、PCの行動に対する一言評価タグを生成してください。
20文字以内の短いタグ1つだけを返してください。

例: "grateful_but_bewildered", "reliable_customer", "distrustful_of_methods"\
"""


class PromptBuilder:
    """호출 유형별 프롬프트 조립"""

    def __init__(self, config: NarrativeConfig, safety: ContentSafetyFilter):
        self._config = config
        self._safety = safety

    def build_look(self, node_data: dict, player_state: dict) -> BuiltPrompt:
        """look 프롬프트. max_tokens=300."""
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        tier = node_data.get("tier", 1)
        node_name = node_data.get("name", f"地点({x},{y})")

        user_prompt = (
            f"場所: {node_name}\n" f"Tier: {tier}\n" f"3〜5文で描写を生成してください。"
        )

        return BuiltPrompt(
            system_prompt=LOOK_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=300,
        )

    def build_move(self, from_node: dict, to_node: dict, direction: str) -> BuiltPrompt:
        """move 프롬프트. max_tokens=150."""
        from_name = from_node.get(
            "name", f"地点({from_node.get('x', 0)},{from_node.get('y', 0)})"
        )
        to_name = to_node.get(
            "name", f"地点({to_node.get('x', 0)},{to_node.get('y', 0)})"
        )

        user_prompt = (
            f"出発: {from_name}\n"
            f"到着: {to_name}\n"
            f"方向: {direction}\n"
            f"1〜2文で移動描写を生成してください。"
        )

        return BuiltPrompt(
            system_prompt=MOVE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=150,
        )

    def build_dialogue(self, ctx: DialoguePromptContext) -> BuiltPrompt:
        """대화 프롬프트 조립.

        조립 순서:
        1. System: 역할 + META 스키마 + 출력 규칙 + 행동 규칙 + scene_direction
        2. User: NPC Context → Session Context → Turn Context → History → Current Input
        """
        # System prompt + scene_direction
        system = DIALOGUE_SYSTEM_PROMPT
        scene_dir = self._safety.get_scene_direction_prompt(ctx.scene_direction)
        if scene_dir:
            system += scene_dir

        # User prompt 조립
        parts: list[str] = []

        # NPC Context
        parts.append("[NPC Context]")
        parts.append(f"名前: {ctx.npc_name}")
        parts.append(f"種族: {ctx.npc_race}")
        if ctx.npc_role:
            parts.append(f"職業: {ctx.npc_role}")
        if ctx.hexaco_summary:
            parts.append(f"性格: {ctx.hexaco_summary}")
        if ctx.manner_tags:
            parts.append(f"話し方: {', '.join(ctx.manner_tags)}")
        if ctx.attitude_tags:
            parts.append(f"態度: {', '.join(ctx.attitude_tags)}")
        parts.append(f"関係: {ctx.relationship_status} (親密度: {ctx.familiarity})")
        if ctx.npc_memories:
            parts.append(f"記憶: {'; '.join(ctx.npc_memories)}")
        if ctx.npc_opinions:
            opinions_str = json.dumps(ctx.npc_opinions, ensure_ascii=False)
            parts.append(f"他NPC意見: {opinions_str}")
        if ctx.node_environment:
            parts.append(f"環境: {ctx.node_environment}")

        # Session Context
        parts.append("")
        parts.append("[Session Context]")
        if ctx.constraints:
            parts.append(f"PC制約: {json.dumps(ctx.constraints, ensure_ascii=False)}")
        if ctx.quest_seed:
            parts.append(
                f"クエストシード: {json.dumps(ctx.quest_seed, ensure_ascii=False)}"
            )
        if ctx.active_quests:
            parts.append(
                f"進行クエスト: {json.dumps(ctx.active_quests, ensure_ascii=False)}"
            )
        if ctx.expired_seeds:
            parts.append(
                f"期限切れシード: {json.dumps(ctx.expired_seeds, ensure_ascii=False)}"
            )
        if ctx.chain_context:
            parts.append(
                f"チェイン: {json.dumps(ctx.chain_context, ensure_ascii=False)}"
            )
        if ctx.companion_context:
            parts.append(
                f"同行NPC: {json.dumps(ctx.companion_context, ensure_ascii=False)}"
            )

        # Turn Context
        parts.append("")
        parts.append("[Turn Context]")
        parts.append(
            f"フェーズ: {ctx.budget_phase} (残り{ctx.budget_remaining}/{ctx.budget_total})"
        )
        if ctx.phase_instruction:
            parts.append(f"フェーズ指示: {ctx.phase_instruction}")
        if ctx.seed_delivered:
            parts.append("シード伝達済み: はい")
        if ctx.accumulated_delta != 0.0:
            parts.append(f"累積好感変動: {ctx.accumulated_delta:+.1f}")

        # History
        if ctx.history:
            parts.append("")
            parts.append("[Conversation History]")
            for entry in ctx.history:
                role = entry.get("role", "pc")
                text = entry.get("text", "")
                label = "PC" if role == "pc" else "NPC"
                parts.append(f"{label}: {text}")

        # Current Input
        parts.append("")
        parts.append(f"[Current Input]\nPC: {ctx.pc_input}")

        user_prompt = "\n".join(parts)
        max_tokens = DIALOGUE_TOKEN_MAP.get(ctx.budget_phase, 400)

        return BuiltPrompt(
            system_prompt=system,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            expect_json=True,
        )

    def build_quest_seed(self, ctx: QuestSeedPromptContext) -> BuiltPrompt:
        """퀘스트 시드 프롬프트. max_tokens=400. expect_json=True."""
        user_prompt = (
            f"シード種別: {ctx.seed_type}\n"
            f"Tier: {ctx.seed_tier}\n"
            f"NPC: {ctx.npc_name} ({ctx.npc_role})\n"
            f"性格: {ctx.npc_hexaco_summary}\n"
            f"地域: {ctx.region_info}\n"
            f"コンテキストタグ: {', '.join(ctx.context_tags)}\n"
            f"既存シード(重複回避): {', '.join(ctx.existing_seeds)}"
        )

        return BuiltPrompt(
            system_prompt=QUEST_SEED_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=400,
            expect_json=True,
        )

    def build_impression_tag(
        self, summary: str, quest_result: dict | None
    ) -> BuiltPrompt:
        """NPC 한줄평 프롬프트. max_tokens=50."""
        user_prompt = f"対話要約: {summary}"
        if quest_result:
            user_prompt += (
                f"\nクエスト結果: {json.dumps(quest_result, ensure_ascii=False)}"
            )

        return BuiltPrompt(
            system_prompt=IMPRESSION_TAG_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=50,
        )
