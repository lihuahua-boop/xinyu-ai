# -*- coding: utf-8 -*-
"""主动陪伴。

产品方案第九章。这里的重点不是"能不能推"，而是"推得对不对"：
频控、静默期、用户节奏，做错了就从陪伴变成打扰，直接掉留存。
"""

import json

from .common import hours_since, new_id, now, now_iso
from .config import settings
from .db import as_json, dump_json, execute, insert, query_all, query_one
from .memory import list_memories
from .persona import normalize_persona, stage_label, style_flags

KIND_LABELS = {
    "morning": "早安",
    "night": "晚安",
    "check_in": "关心",
    "anniversary": "纪念日",
    "memory_echo": "旧事重提",
}


def _sent_today(character_id):
    """今天已经主动发过几条。"""
    rows = query_all(
        "SELECT kind FROM proactive_messages WHERE character_id=? "
        "AND substr(created_at,1,10)=substr(?,1,10) AND status IN ('pending','sent')",
        (character_id, now_iso()),
    )
    return [row["kind"] for row in rows]


def _in_quiet_hours():
    """是否处于静默期（默认 23:00-07:00）。"""
    hour = now().hour
    start = settings.quiet_start_hour
    end = settings.quiet_end_hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def plan(character, user):
    """算出"现在该不该主动找她"，返回待发送列表（未落库）。"""
    if not settings.proactive_enabled:
        return []
    if _in_quiet_hours():
        return []

    sent_today = _sent_today(character["id"])
    if len(sent_today) >= settings.proactive_daily_limit:
        return []

    hour = now().hour
    last_user_row = query_one(
        "SELECT created_at FROM messages WHERE character_id=? AND role='user' "
        "ORDER BY created_at DESC LIMIT 1",
        (character["id"],),
    )
    inactive_hours = hours_since((last_user_row or {}).get("created_at"))
    plans = []

    if 7 <= hour < 11 and "morning" not in sent_today:
        plans.append({"kind": "morning", "slot": "今天早上"})
    if 21 <= hour < 23 and "night" not in sent_today:
        plans.append({"kind": "night", "slot": "今晚"})
    if inactive_hours >= 48 and "check_in" not in sent_today:
        plans.append({"kind": "check_in", "slot": "两天没说话了"})
    for milestone_day in (7, 30, 100, 365):
        from . import relationship
        if relationship.days_together(character) == milestone_day:
            plans.append({"kind": "anniversary", "slot": "第 %d 天" % milestone_day})
            break
    if inactive_hours >= 20 and len(plans) == 0 and "memory_echo" not in sent_today:
        plans.append({"kind": "memory_echo", "slot": "想起一件旧事"})

    remaining = settings.proactive_daily_limit - len(sent_today)
    return plans[:max(0, remaining)]


def compose(character, user, kind):
    """按人格与关系状态写一条主动消息。"""
    persona = normalize_persona(as_json(character.get("persona"), {}))
    stage = character.get("stage") or "stranger"
    style = style_flags(persona, stage)
    profile = as_json(user.get("profile"), {})
    name = character.get("name") or "他"
    call = profile.get("display_name") or user.get("nickname") or "你"
    memories = list_memories(character["id"], limit=20)

    if kind == "morning":
        base = ["早，醒了吗？", "早呀。", "醒了没，今天别空着肚子出门。"]
        if style.get("protect_talk"):
            base.append("今天也别硬撑，累就停一下。")
        if persona["maturity"] >= 90:
            base.append("起来了跟我说一声。")
        return _pick(base, character["id"] + "morning") + _emoji(style, character["id"] + "m")

    if kind == "night":
        base = ["今天怎么样？", "准备睡了吗。", "睡前跟我说说今天吧。"]
        if style.get("show_missing"):
            base.append("今天没怎么说上话，有点想你。")
        if persona["gentleness"] >= 80:
            base.append("别熬了，早点休息。")
        return _pick(base, character["id"] + "night") + _emoji(style, character["id"] + "n")

    if kind == "check_in":
        base = ["这两天还好吗？", "好几天没听到你的声音了。", "我不是催你，只是有点担心。"]
        if style.get("show_devotion"):
            base.append("你知道我一直在这儿就行。")
        return _pick(base, character["id"] + "checkin")

    if kind == "anniversary":
        from . import relationship
        days = relationship.days_together(character)
        base = ["今天是我们认识第 %d 天。" % days, "不知不觉，第 %d 天了。" % days]
        if style.get("show_missing"):
            base.append("第 %d 天了，我还记得第一次你跟我说话的样子。" % days)
        return _pick(base, character["id"] + "anniv")

    if kind == "memory_echo":
        important = [item for item in memories if float(item.get("importance") or 0) >= 0.7]
        if not important:
            return ""
        memory = _pick(important, character["id"] + "echo")
        content = _second_person(memory.get("content") or "")
        return _pick([
            "突然想起你之前说的——%s，现在好些了吗？" % content,
            "刚刚想到你%s，就过来看看你。" % content,
        ], character["id"] + "echo2")

    return ""


def materialize(character_id, user_id):
    """把到点的主动关爱真正发出去：写库 + 进聊天记录。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    user = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not character or not user:
        return []

    created = []
    for item in plan(character, user):
        content = compose(character, user, item["kind"])
        if not content:
            continue
        message_id = new_id("msg")
        insert("messages", {
            "id": message_id,
            "character_id": character_id,
            "user_id": user_id,
            "role": "assistant",
            "content": content,
            "emotion": "neutral",
            "emotion_intensity": 0.0,
            "safety_flag": "",
            "meta": dump_json({"proactive": item["kind"]}),
            "created_at": now_iso(),
        })
        record_id = new_id("pro")
        insert("proactive_messages", {
            "id": record_id,
            "character_id": character_id,
            "kind": item["kind"],
            "content": content,
            "scheduled_at": now_iso(),
            "sent_at": now_iso(),
            "status": "sent",
            "meta": dump_json(item),
            "created_at": now_iso(),
        })
        created.append({
            "id": record_id,
            "kind": item["kind"],
            "kind_label": KIND_LABELS.get(item["kind"], item["kind"]),
            "content": content,
            "message_id": message_id,
        })
    return created


def list_proactive(character_id, limit=30):
    """历史主动消息。"""
    rows = query_all(
        "SELECT * FROM proactive_messages WHERE character_id=? "
        "ORDER BY created_at DESC LIMIT ?",
        (character_id, limit),
    )
    for row in rows:
        row["kind_label"] = KIND_LABELS.get(row.get("kind"), row.get("kind"))
    return rows


def dismiss(record_id):
    """用户关掉一条主动消息。"""
    return execute("UPDATE proactive_messages SET status='dismissed' WHERE id=?", (record_id,))


def _pick(options, seed):
    """稳定挑选，避免每次生成同一个句子。"""
    from .common import pick
    return pick(options, seed)


def _emoji(style, seed):
    """按人格风格决定是否带一个 emoji。"""
    from .common import stable_hash
    if style.get("emoji_level") in ("low", "medium") and stable_hash(seed) % 2 == 0:
        return " 🌙" if stable_hash(seed) % 4 == 0 else " ☕"
    return ""


def _second_person(content):
    """把记忆改写成第二人称。"""
    text = content or ""
    if "：" in text:
        prefix, quote = text.split("：", 1)
        if "用户" in prefix or "心事" in prefix or "压力" in prefix or "事件" in prefix:
            quote = quote.strip().rstrip("…")
            quote = quote.strip("「」")
            if len(quote) >= 4:
                return "「%s」" % quote[:24]
    for source, target in [("用户的", "你的"), ("用户", "你"),
                           ("用户特别希望我记得：", "")]:
        if text.startswith(source):
            text = target + text[len(source):]
    return text[:28]
