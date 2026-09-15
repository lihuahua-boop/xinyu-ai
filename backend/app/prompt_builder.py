# -*- coding: utf-8 -*-
"""分层提示词组装。

层次（从稳定到易变）：
1. 人格层：稳定，来自参数编译
2. 关系层：阶段、亲密度、里程碑
3. 画像层：基础信息，每轮常驻
4. 记忆层：检索出来的片段，按 token 预算裁剪
5. 情绪层：当前这轮的情绪与需求
6. 安全层：连续观察到的低落状态
"""

from .config import settings
from .db import as_json
from .emotion import EMOTION_LABELS, recent_mood_ratio
from .memory.retriever import build_memory_block
from .persona import compile_persona, stage_label


def build_system_prompt(character, user, persona, memories, emotion_result,
                        profile_facts=None, milestones=None, greeting_hint="",
                        days_together=1):
    """组装系统提示词。"""
    stage = character.get("stage") or "stranger"
    intimacy = float(character.get("intimacy") or 0.0)
    user_profile = as_json((user or {}).get("profile"), {})
    age_verified = bool((user or {}).get("age_verified"))

    prompt = compile_persona(
        persona=persona,
        character_name=character.get("name") or "他",
        relation_type=character.get("relation_type") or "boyfriend",
        stage=stage,
        intimacy=intimacy,
        user_nickname=user_profile.get("display_name") or (user or {}).get("nickname") or "",
        custom_address=user_profile.get("call_me") or "",
        milestones=milestones or [],
        days_together=days_together,
        greeting_hint=greeting_hint,
        age_verified=age_verified,
    )

    if profile_facts:
        prompt += "\n\n【你确定记得的关于对方的固定信息】\n"
        for fact in profile_facts:
            prompt += "- %s\n" % fact

    memory_block = build_memory_block(memories)
    if memory_block:
        prompt += "\n\n【相关记忆】\n" + memory_block

    prompt += "\n\n【本轮情绪读解】\n"
    prompt += "- 检测到的情绪：%s（强度 %.2f）\n" % (
        EMOTION_LABELS.get(emotion_result.get("emotion"), "说不清"),
        float(emotion_result.get("intensity") or 0.0),
    )
    needs = emotion_result.get("needs") or []
    need_text = {
        "needs_comfort": "需要被安慰，不需要被教育",
        "wants_advice": "明确在问办法，可以先共情再给一条建议",
        "vent": "在倾诉，让他说完，不要打断式建议",
        "shares_feeling": "在分享好情绪，请一起高兴，具体地夸",
        "wants_closeness": "在主动靠近，可以回应亲密",
        "tests_memory": "在确认你是否记得，自然地提一件你记得的事",
        "asks_identity": "在问身份，诚实承认是 AI，但保持陪伴语气",
        "greeting": "这是日常问候，轻松自然地回应",
        "ongoing_low": "对方最近几轮状态持续偏低，今天不要急着劝好，先陪着",
    }
    for need in needs:
        if need in need_text:
            prompt += "- %s\n" % need_text[need]
    if not needs:
        prompt += "- 普通对话，自然接话即可\n"

    prompt += "\n【输出要求】\n"
    prompt += "- 只输出你要说的话本身，不要旁白、不要括号里的动作描写、不要分条列点\n"
    prompt += "- 长度控制在 1-3 句，像真人在微信上回消息\n"
    return prompt


def build_history(rows, limit=None):
    """把数据库里的消息转成模型可用的对话历史。"""
    limit = limit or settings.recent_turns
    history = []
    for row in rows[-limit:]:
        role = "assistant" if row.get("role") == "assistant" else "user"
        content = (row.get("content") or "").strip()
        if not content:
            continue
        history.append({"role": role, "content": content})
    return history


def mood_context(emotion_rows):
    """从最近几轮的情绪里读出"今天状态怎么样"。"""
    emotions = [row.get("emotion") for row in emotion_rows if row.get("emotion")]
    ratio = recent_mood_ratio(emotions)
    if ratio >= 0.7 and len(emotions) >= 3:
        return {"recent_mood_ratio": ratio, "tone": "持续偏低"}
    if ratio >= 0.4:
        return {"recent_mood_ratio": ratio, "tone": "有些低落"}
    return {"recent_mood_ratio": ratio, "tone": "平稳"}


def stage_context(character):
    """阶段上下文，用于日志与调试。"""
    return {
        "stage": character.get("stage"),
        "stage_label": stage_label(character.get("stage")),
        "intimacy": float(character.get("intimacy") or 0.0),
    }
