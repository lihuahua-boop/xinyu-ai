# -*- coding: utf-8 -*-
"""关系成长系统。

亲密度是留存的核心变量：它把「聊了很多」变成「我们更近了」，
并且真实地改变 AI 的称呼、主动性、亲密的表达尺度。
"""

from .common import clamp, days_since, new_id, now_iso
from .db import execute, insert, query_all
from .persona import next_stage, stage_label, stage_progress

# 每轮基础增长
BASE_GAIN = 0.4
# 每天最多增长多少，避免刷消息把关系刷满
DAILY_GAIN_CAP = 8.0
REWARDING_EMOTIONS = ("sad", "anxious", "lonely", "crisis", "tired", "angry")


def intimacy_gain(message, emotion_result, wrote_memory=False, recalled_memory=False):
    """算一轮对话带来的亲密度增长。

    规则：说心里话、暴露脆弱涨得多；敷衍式短消息涨得少；
    产生新记忆或成功回忆起过去，额外加成。
    """
    gain = BASE_GAIN
    emotion = emotion_result.get("emotion", "neutral")
    intensity = emotion_result.get("intensity", 0.0)
    length = emotion_result.get("length", 0)

    if emotion in REWARDING_EMOTIONS:
        gain += 0.5 + intensity * 0.8
    if "vent" in emotion_result.get("needs", []):
        gain += 0.4
    if emotion == "affection":
        gain += 0.5
    if length >= 30:
        gain += 0.4
    elif length <= 3:
        gain -= 0.25
    if wrote_memory:
        gain += 0.35
    if recalled_memory:
        gain += 0.25
    return round(clamp(gain, 0.0, 2.5), 2)


def today_gain(character_id):
    """今日已获得的亲密度，用于每日上限。"""
    row = query_all(
        "SELECT COALESCE(SUM(gain), 0) AS total FROM intimacy_log "
        "WHERE character_id=? AND substr(created_at,1,10)=substr(?,1,10)",
        (character_id, now_iso()),
    )
    return float((row[0] if row else {}).get("total") or 0.0)


def apply_gain(character, gain):
    """把增长写入角色，返回关系状态。"""
    before = float(character.get("intimacy") or 0.0)
    applied = min(gain, max(0.0, DAILY_GAIN_CAP - today_gain(character["id"])))
    after = round(clamp(before + applied, 0.0, 100.0), 2)
    old_stage = character.get("stage") or next_stage(before)
    new_stage = next_stage(after)
    execute("UPDATE characters SET intimacy=?, stage=? WHERE id=?",
            (after, new_stage, character["id"]))
    if applied > 0:
        insert("intimacy_log", {
            "id": new_id("gain"),
            "character_id": character["id"],
            "gain": applied,
            "reason": "对话",
            "created_at": now_iso(),
        })
    return {
        "intimacy": after,
        "intimacy_gain": round(applied, 2),
        "stage": new_stage,
        "stage_label": stage_label(new_stage),
        "stage_changed": new_stage != old_stage,
        "previous_stage": old_stage,
        "previous_stage_label": stage_label(old_stage),
        "progress": stage_progress(after),
    }


def days_together(character):
    """认识多少天，至少 1 天。"""
    start = character.get("first_chat_at") or character.get("created_at")
    return max(1, int(days_since(start)) + 1)


def add_milestone(character_id, kind, title, content="", occurred_at=None):
    """记录一个关系里程碑，同类只记一次。"""
    existing = query_all(
        "SELECT id FROM milestones WHERE character_id=? AND kind=?",
        (character_id, kind),
    )
    if existing:
        return existing[0]["id"]
    milestone_id = new_id("ms")
    insert("milestones", {
        "id": milestone_id,
        "character_id": character_id,
        "kind": kind,
        "title": title,
        "content": content,
        "occurred_at": occurred_at or now_iso(),
        "created_at": now_iso(),
    })
    return milestone_id


def list_milestones(character_id):
    """列出里程碑。"""
    return query_all(
        "SELECT * FROM milestones WHERE character_id=? ORDER BY occurred_at ASC",
        (character_id,),
    )


def detect_milestones(character, user_message, stage_info):
    """从这一轮对话里识别值得记下的关系节点。"""
    created = []
    if not character.get("first_chat_at"):
        created.append(add_milestone(
            character["id"], "first_chat", "第一次聊天",
            "你们的第一句话是：「%s」" % (user_message or "")[:40],
        ))
    if stage_info.get("stage_changed"):
        created.append(add_milestone(
            character["id"], "stage_" + str(stage_info.get("stage")),
            "关系进入「%s」" % stage_info.get("stage_label", ""),
            "你们的距离又近了一点。",
        ))
    text = user_message or ""
    if any(word in text for word in ["喜欢你", "爱你", "想你"]):
        created.append(add_milestone(
            character["id"], "confession", "你说过想我",
            "「%s」" % text[:40],
        ))
    return created


def relationship_view(character):
    """给前端的完整关系状态。"""
    intimacy = float(character.get("intimacy") or 0.0)
    stage = character.get("stage") or next_stage(intimacy)
    return {
        "intimacy": round(intimacy, 1),
        "stage": stage,
        "stage_label": stage_label(stage),
        "days_together": days_together(character),
        "progress": stage_progress(intimacy),
        "milestones": list_milestones(character["id"]),
    }
