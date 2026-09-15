# -*- coding: utf-8 -*-
"""聊天接口。"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..common import new_id
from ..db import as_json, dump_json, execute, insert, query_all, query_one
from ..engine import EngineError, chat as run_chat, chat_stream
from ..memory.store import CATEGORY_LABELS
from ..schemas import ChatRequest

router = APIRouter(prefix="/api/characters", tags=["chat"])


def _memory_map(rows):
    """把消息里记录的 memory_id 展开成可显示的内容。

    聊天接口实时返回的是完整记忆对象，但历史消息里只存了 id。
    不展开的话，回看聊天记录时「他想起」卡片就只剩一个空壳。
    """
    ids = set()
    for row in rows:
        meta = as_json(row.get("meta"), {})
        ids.update([item for item in (meta.get("memories_used") or []) if isinstance(item, str)])
    if not ids:
        return {}
    placeholders = ",".join(["?"] * len(ids))
    rows = query_all(
        "SELECT id, category, content FROM memories WHERE id IN (%s)" % placeholders,
        tuple(ids),
    )
    return dict((row["id"], {
        "id": row["id"],
        "category": row["category"],
        "category_label": CATEGORY_LABELS.get(row["category"], row["category"]),
        "content": row["content"],
    }) for row in rows)


@router.post("/{character_id}/chat")
def send_message(character_id: str, payload: ChatRequest):
    """发一条消息，拿到他这一轮的回复。"""
    return run_chat(character_id, payload.user_id, payload.text)


@router.post("/{character_id}/chat/stream")
def send_message_stream(character_id: str, payload: ChatRequest):
    """流式发消息：先逐块吐回复，最后吐完整结果。"""
    generator = chat_stream(character_id, payload.user_id, payload.text)
    return StreamingResponse(generator, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.get("/{character_id}/messages")
def list_messages(character_id: str, limit: int = 60):
    """聊天记录。"""
    character = query_one("SELECT id FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    rows = query_all(
        "SELECT * FROM messages WHERE character_id=? ORDER BY created_at DESC LIMIT ?",
        (character_id, max(1, min(limit, 200))),
    )
    rows.reverse()
    memory_map = _memory_map(rows)
    items = []
    for row in rows:
        meta = as_json(row.get("meta"), {})
        used = [memory_map[item] for item in (meta.get("memories_used") or [])
                if isinstance(item, str) and item in memory_map]
        items.append({
            "id": row["id"],
            "role": row.get("role"),
            "content": row.get("content"),
            "emotion": row.get("emotion"),
            "emotion_intensity": row.get("emotion_intensity"),
            "created_at": row.get("created_at"),
            "memories_used": used,
            "proactive": meta.get("proactive") or "",
            "safety_flag": row.get("safety_flag") or "",
        })
    return {"items": items}


@router.post("/{character_id}/messages/seed")
def seed_message(character_id: str, role: str, content: str):
    """调试用：直接塞一条消息，方便做演示数据。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    from ..common import now_iso
    message_id = new_id("msg")
    insert("messages", {
        "id": message_id,
        "character_id": character_id,
        "user_id": character["user_id"],
        "role": role if role in ("user", "assistant") else "user",
        "content": content,
        "emotion": "neutral",
        "emotion_intensity": 0.0,
        "safety_flag": "",
        "meta": dump_json({"seeded": True}),
        "created_at": now_iso(),
    })
    return {"id": message_id}
