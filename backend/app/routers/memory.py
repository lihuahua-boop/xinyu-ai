# -*- coding: utf-8 -*-
"""记忆与主动陪伴接口。"""

from fastapi import APIRouter

from ..db import query_one
from ..engine import EngineError
from ..memory import list_memories, memory_stats
from ..memory.store import CATEGORY_LABELS, add_memory, deactivate_memory
from ..proactive import dismiss, list_proactive, materialize
from ..schemas import MemoryCreate

router = APIRouter(prefix="/api", tags=["memory"])


@router.get("/characters/{character_id}/memories")
def get_memories(character_id: str, category: str = "", limit: int = 200):
    """他还记得关于你的事。"""
    character = query_one("SELECT id FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    items = list_memories(character_id, category=category or None, limit=limit)
    grouped = {}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)
    return {
        "stats": memory_stats(character_id),
        "labels": CATEGORY_LABELS,
        "items": items,
        "grouped": grouped,
    }


@router.post("/characters/{character_id}/memories")
def create_memory(character_id: str, payload: MemoryCreate):
    """手动补一条记忆（用户主动告诉他的事）。"""
    character = query_one("SELECT id FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    if payload.category not in CATEGORY_LABELS:
        raise EngineError("bad_category", "记忆类别不支持", 400)
    memory_id = add_memory(character_id, payload.category, payload.content,
                           importance=payload.importance, confidence=1.0,
                           tags=["用户手动添加"])
    return {"id": memory_id, "stats": memory_stats(character_id)}


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    """让他忘掉这件事。"""
    affected = deactivate_memory(memory_id)
    if not affected:
        raise EngineError("memory_not_found", "没有这条记忆", 404)
    return {"ok": True}


@router.get("/characters/{character_id}/proactive")
def get_proactive(character_id: str, materialize_now: int = 0):
    """主动陪伴消息。

    materialize_now=1 时，先把到点的主动消息生成出来（前端进入聊天时调用）。
    """
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    created = []
    if materialize_now:
        created = materialize(character_id, character["user_id"])
    return {"created": created, "history": list_proactive(character_id)}


@router.post("/proactive/{record_id}/dismiss")
def dismiss_proactive(record_id: str):
    """关掉一条主动消息。"""
    dismiss(record_id)
    return {"ok": True}
