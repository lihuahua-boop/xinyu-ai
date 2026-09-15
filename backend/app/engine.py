# -*- coding: utf-8 -*-
"""一轮对话的完整编排。

顺序固定为：
准备（校验/安全/情绪/记忆/提示词）→ 生成（模型或安全通道）→ 收尾（审核/落库/写记忆/涨关系）。

任何一步失败都不应该让用户看到空白回复，所以每一步都有降级路径。
"""

import json
import time

from . import relationship, safety
from .common import est_tokens, new_id, now_iso
from .config import settings
from .db import as_json, dump_json, execute, insert, query_all, query_one, touch_user
from .emotion import detect
from .llm import get_provider
from .llm.base import LLMError
from .memory import extract_memories, extract_memories_with_llm, extract_profile_updates
from .memory.retriever import profile_snapshot, recall
from .memory.store import add_memory
from .persona import normalize_persona, stage_label, style_flags
from .prompt_builder import build_history, build_system_prompt, mood_context


class EngineError(Exception):
    """业务错误，带 HTTP 状态码。"""

    def __init__(self, code, message, status=400):
        super(EngineError, self).__init__(message)
        self.code = code
        self.message = message
        self.status = status


def load_character(character_id):
    """读角色，不存在则报错。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    return character


def load_user(user_id):
    """读用户，不存在则报错。"""
    user = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user:
        raise EngineError("user_not_found", "用户不存在", 404)
    return user


def recent_messages(character_id, limit=None):
    """最近的消息（按时间正序返回）。"""
    limit = limit or settings.recent_turns * 2
    rows = query_all(
        "SELECT * FROM messages WHERE character_id=? ORDER BY created_at DESC LIMIT ?",
        (character_id, limit),
    )
    rows.reverse()
    return rows


def _today_message_count(user_id):
    """今日已发消息数，用于免费额度控制。"""
    row = query_one(
        "SELECT COUNT(*) AS total FROM messages WHERE user_id=? AND role='user' "
        "AND substr(created_at,1,10)=substr(?,1,10)",
        (user_id, now_iso()),
    )
    return int((row or {}).get("total") or 0)


def _check_quota(user):
    """额度熔断：免费用户每天上限，防止成本失控。"""
    if user.get("membership") == "vip":
        return
    used = _today_message_count(user["id"])
    limit = settings.free_daily_quota
    if used >= limit:
        raise EngineError(
            "quota_exceeded",
            "今天聊得够多了，明天再来找他吧（免费版每天 %d 条）。" % limit,
            429,
        )


def _recent_emotions(character_id, limit=6):
    """最近几轮用户消息的情绪，用于判断"最近状态"。"""
    rows = query_all(
        "SELECT emotion FROM messages WHERE character_id=? AND role='user' "
        "ORDER BY created_at DESC LIMIT ?",
        (character_id, limit),
    )
    return [row.get("emotion") for row in rows]


def _persist_message(character_id, user_id, role, content, emotion="neutral",
                     intensity=0.0, safety_flag="", meta=None):
    """写入一条消息。"""
    message_id = new_id("msg")
    insert("messages", {
        "id": message_id,
        "character_id": character_id,
        "user_id": user_id,
        "role": role,
        "content": content or "",
        "emotion": emotion or "neutral",
        "emotion_intensity": float(intensity or 0.0),
        "safety_flag": safety_flag or "",
        "meta": dump_json(meta or {}),
        "created_at": now_iso(),
    })
    return message_id


def _prepare_turn(character_id, user_id, text):
    """对话前的公共准备：校验、安全、情绪、记忆、提示词。"""
    started = time.time()
    text = (text or "").strip()
    if not text:
        raise EngineError("empty_message", "说点什么吧", 400)
    if len(text) > 2000:
        raise EngineError("message_too_long", "一次说太多了，分几次说给我听", 400)

    character = load_character(character_id)
    if character.get("user_id") != user_id:
        raise EngineError("forbidden", "这个角色不属于当前用户", 403)
    user = load_user(user_id)
    _check_quota(user)

    moderation = safety.moderate(text)
    if not moderation.get("allowed"):
        raise EngineError("content_blocked", "这句话我没办法回应", 400)

    safety_result = safety.screen_user_message(text)
    emotion_result = detect(text, recent_mood=None)
    mood = mood_context([{"emotion": item} for item in _recent_emotions(character_id)])
    if mood["recent_mood_ratio"] >= 0.6:
        emotion_result = detect(text, recent_mood=mood["recent_mood_ratio"])

    memories = recall(character_id, text, emotion_result)
    profile_facts = profile_snapshot(character_id)
    persona = normalize_persona(as_json(character.get("persona"), {}))
    style = style_flags(persona, character.get("stage") or "stranger")
    milestones = relationship.list_milestones(character_id)
    days = relationship.days_together(character)

    system_prompt = build_system_prompt(
        character=character,
        user=user,
        persona=persona,
        memories=memories,
        emotion_result=emotion_result,
        profile_facts=profile_facts,
        milestones=milestones,
        days_together=days,
    )
    history = build_history(recent_messages(character_id))

    context = {
        "persona": persona,
        "style": style,
        "emotion": emotion_result,
        "memories": memories,
        "stage": character.get("stage") or "stranger",
        "stage_label": stage_label(character.get("stage") or "stranger"),
        "template_key": character.get("template_key"),
        "character_name": character.get("name"),
        "profile": as_json(user.get("profile"), {}),
        "days_together": days,
        "turn_id": new_id("turn"),
    }

    crisis = safety_result.get("level") == "high"
    if not crisis:
        context["crisis_text"] = safety.crisis_reply(character.get("name"), "watch") \
            if safety_result.get("level") == "watch" else ""

    return {
        "started": started,
        "text": text,
        "character": character,
        "user": user,
        "safety_result": safety_result,
        "emotion_result": emotion_result,
        "memories": memories,
        "system_prompt": system_prompt,
        "history": history,
        "context": context,
        "crisis": crisis,
    }


def _finalize_turn(prep, reply_text, provider_name, error_note, provider=None):
    """生成后的公共收尾：审核、落库、写记忆、涨关系、记里程碑。"""
    character = prep["character"]
    user = prep["user"]
    character_id = character["id"]
    user_id = user["id"]
    text = prep["text"]
    emotion_result = prep["emotion_result"]
    memories = prep["memories"]
    safety_result = prep["safety_result"]
    crisis = prep["crisis"]
    started = prep["started"]

    screened = safety.screen_reply(reply_text)
    reply_text = screened["clean_text"]

    usage = {
        "prompt_tokens_est": est_tokens(prep["system_prompt"]) + est_tokens(text),
        "completion_tokens_est": est_tokens(reply_text),
    }
    memory_ids = [item["id"] for item in memories]
    user_meta = {
        "emotion": emotion_result.get("emotion"),
        "intensity": emotion_result.get("intensity"),
        "needs": emotion_result.get("needs"),
        "memories_used": memory_ids,
        "usage": usage,
    }
    user_message_id = _persist_message(
        character_id, user_id, "user", text,
        emotion=emotion_result.get("emotion", "neutral"),
        intensity=emotion_result.get("intensity", 0.0),
        safety_flag=safety_result.get("level", "") if crisis else "",
        meta=user_meta,
    )

    # 记忆抽取：规则通道 + 大模型结构化通道（接真实模型时启用），规则始终兜底
    extracted = extract_memories(text, emotion_result, source_message_id=user_message_id)
    if provider is not None and getattr(provider, "name", "") != "mock" \
            and settings.llm_memory_extraction:
        extracted.extend(extract_memories_with_llm(provider, text, emotion_result))
    new_memory_ids = []
    for item in extracted:
        memory_id = add_memory(
            character_id,
            item["category"],
            item["content"],
            key=item.get("key", ""),
            importance=item.get("importance", 0.5),
            confidence=item.get("confidence", 0.6),
            tags=item.get("tags"),
            source_message_id=item.get("source_message_id", ""),
        )
        if memory_id:
            new_memory_ids.append(memory_id)

    profile = extract_profile_updates(text, as_json(user.get("profile"), {}))
    execute("UPDATE users SET profile=?, last_active_at=? WHERE id=?",
            (dump_json(profile), now_iso(), user_id))
    gain = relationship.intimacy_gain(
        text, emotion_result,
        wrote_memory=bool(new_memory_ids),
        recalled_memory=bool(memory_ids),
    )
    stage_info = relationship.apply_gain(character, gain)
    if not character.get("first_chat_at"):
        execute("UPDATE characters SET first_chat_at=? WHERE id=?", (now_iso(), character_id))
    relationship.detect_milestones(character, text, stage_info)
    if stage_info.get("stage_changed"):
        relationship.add_milestone(
            character_id, "stage_" + stage_info["stage"],
            "关系进入「%s」" % stage_info["stage_label"],
            "你们的距离又近了一点。",
        )

    execute("UPDATE messages SET meta=? WHERE id=?",
            (dump_json(dict(user_meta, intimacy_gain=stage_info["intimacy_gain"])), user_message_id))

    assistant_meta = {
        "provider": provider_name,
        "memories_used": memory_ids,
        "safety_flags": screened.get("flags") or [],
        "usage": usage,
        "error": error_note,
    }
    if new_memory_ids:
        assistant_meta["memory_written"] = new_memory_ids
    assistant_message_id = _persist_message(
        character_id, user_id, "assistant", reply_text,
        emotion=emotion_result.get("emotion", "neutral"),
        intensity=emotion_result.get("intensity", 0.0),
        meta=assistant_meta,
    )
    touch_user(user_id)

    character["intimacy"] = stage_info["intimacy"]
    character["stage"] = stage_info["stage"]

    return {
        "reply": reply_text,
        "message_id": assistant_message_id,
        "user_message_id": user_message_id,
        "emotion": {
            "key": emotion_result.get("emotion"),
            "label": emotion_result.get("label"),
            "intensity": emotion_result.get("intensity"),
        },
        "memories_used": [
            {
                "id": item["id"],
                "category": item.get("category"),
                "category_label": item.get("category_label"),
                "content": item.get("content"),
                "reason": item.get("reason"),
                "score": item.get("score"),
            }
            for item in memories
        ],
        "memories_written": len(new_memory_ids),
        "relationship": {
            "intimacy": stage_info["intimacy"],
            "intimacy_gain": stage_info["intimacy_gain"],
            "stage": stage_info["stage"],
            "stage_label": stage_info["stage_label"],
            "stage_changed": stage_info["stage_changed"],
            "days_together": relationship.days_together(character),
            "progress": stage_info["progress"],
        },
        "safety": {
            "level": safety_result.get("level"),
            "flags": screened.get("flags") or [],
        },
        "meta": {
            "provider": provider_name,
            "latency_ms": int((time.time() - started) * 1000),
            "usage": usage,
            "llm_error": error_note,
        },
    }


def chat(character_id, user_id, text, provider=None):
    """处理一轮用户消息，返回完整结果对象（非流式）。"""
    prep = _prepare_turn(character_id, user_id, text)
    impl = None
    if prep["crisis"]:
        reply_text = safety.crisis_reply(prep["character"].get("name"), "high")
        provider_name = "safety-engine"
        error_note = ""
    else:
        impl = provider or get_provider()
        provider_name = impl.name
        error_note = ""
        try:
            reply_text = impl.complete(prep["system_prompt"], prep["history"], text, prep["context"])
        except LLMError as error:
            from .llm.mock import MockProvider
            reply_text = MockProvider().complete(
                prep["system_prompt"], prep["history"], text, prep["context"])
            provider_name = "mock-fallback"
            error_note = str(error)
            impl = None
        if not (reply_text or "").strip():
            from .llm.mock import MockProvider
            reply_text = MockProvider().complete(
                prep["system_prompt"], prep["history"], text, prep["context"])
            provider_name = "mock-fallback"
            impl = None
    return _finalize_turn(prep, reply_text, provider_name, error_note, impl)


def _sse(event, payload):
    """把一次事件格式化成 Server-Sent Events 的一帧。"""
    return "data: " + json.dumps({"event": event, "data": payload}, ensure_ascii=False) + "\n\n"


def chat_stream(character_id, user_id, text, provider=None):
    """流式对话：先逐块吐回复，最后吐一帧带完整结果的 done 事件。"""
    prep = _prepare_turn(character_id, user_id, text)
    text = prep["text"]
    impl = None
    if prep["crisis"]:
        reply_text = safety.crisis_reply(prep["character"].get("name"), "high")
        provider_name = "safety-engine"
        error_note = ""
        yield _sse("token", {"content": reply_text})
    else:
        impl = provider or get_provider()
        provider_name = impl.name
        error_note = ""
        reply_text = ""
        try:
            for chunk in impl.stream(prep["system_prompt"], prep["history"], text, prep["context"]):
                if chunk:
                    reply_text += chunk
                    yield _sse("token", {"content": chunk})
        except LLMError as error:
            from .llm.mock import MockProvider
            reply_text = ""
            for chunk in MockProvider().stream(
                    prep["system_prompt"], prep["history"], text, prep["context"]):
                reply_text += chunk
                yield _sse("token", {"content": chunk})
            provider_name = "mock-fallback"
            error_note = str(error)
            impl = None
        if not (reply_text or "").strip():
            from .llm.mock import MockProvider
            for chunk in MockProvider().stream(
                    prep["system_prompt"], prep["history"], text, prep["context"]):
                reply_text += chunk
                yield _sse("token", {"content": chunk})
            provider_name = "mock-fallback"
            impl = None
    result = _finalize_turn(prep, reply_text, provider_name, error_note, impl)
    yield _sse("done", result)
