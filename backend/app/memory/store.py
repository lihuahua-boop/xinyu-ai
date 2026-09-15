# -*- coding: utf-8 -*-
"""记忆的存储层：写入、去重合并、查询、召回打点。"""

import json

from ..common import clamp, new_id, now_iso
from ..db import execute, insert, query_all, query_one, update

# 四类记忆，对应产品方案第六章
CATEGORY_LABELS = {
    "basic": "基础信息",
    "preference": "偏好记忆",
    "emotion": "情绪记忆",
    "relationship": "关系记忆",
}


def add_memory(character_id, category, content, key="", importance=0.5,
               confidence=0.6, tags=None, source_message_id="", embedding=None):
    """写入一条记忆，若语义重复则合并而不是堆叠。"""
    content = (content or "").strip()
    if not content:
        return None
    existing = find_duplicate(character_id, category, key, content)
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    if existing:
        # 合并：保留更完整的表述，重要度取高，置信度小幅提升
        merged_content = content if len(content) > len(existing["content"]) else existing["content"]
        merged_importance = round(clamp(max(float(existing["importance"]), importance), 0.0, 1.0), 3)
        merged_confidence = round(clamp(float(existing["confidence"]) + 0.05, 0.0, 1.0), 3)
        update("memories", existing["id"], {
            "content": merged_content,
            "importance": merged_importance,
            "confidence": merged_confidence,
            "tags": tags_json,
            "updated_at": now_iso(),
            "active": 1,
        })
        return existing["id"]

    memory_id = new_id("mem")
    insert("memories", {
        "id": memory_id,
        "character_id": character_id,
        "category": category,
        "key": key or "",
        "content": content,
        "importance": round(clamp(importance, 0.0, 1.0), 3),
        "confidence": round(clamp(confidence, 0.0, 1.0), 3),
        "tags": tags_json,
        "source_message_id": source_message_id or "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "active": 1,
        "embedding": json.dumps(embedding) if embedding else None,
    })
    return memory_id


def find_duplicate(character_id, category, key, content):
    """找出重复记忆：同类别 + 同 key 直接算重复；否则看文本包含关系。"""
    if key:
        row = query_one(
            "SELECT * FROM memories WHERE character_id=? AND category=? AND key=? AND active=1",
            (character_id, category, key),
        )
        if row:
            return row
    rows = query_all(
        "SELECT * FROM memories WHERE character_id=? AND category=? AND active=1 "
        "ORDER BY created_at DESC LIMIT 40",
        (character_id, category),
    )
    for row in rows:
        a = (row.get("content") or "").strip()
        b = content.strip()
        if not a or not b:
            continue
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if shorter in longer and len(shorter) >= 4:
            return row
    return None


def list_memories(character_id, category=None, limit=200, include_inactive=False):
    """列出记忆。"""
    sql = "SELECT * FROM memories WHERE character_id=?"
    params = [character_id]
    if category:
        sql += " AND category=?"
        params.append(category)
    if not include_inactive:
        sql += " AND active=1"
    sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
    params.append(limit)
    rows = query_all(sql, tuple(params))
    for row in rows:
        try:
            row["tags"] = json.loads(row.get("tags") or "[]")
        except ValueError:
            row["tags"] = []
        row["category_label"] = CATEGORY_LABELS.get(row.get("category"), row.get("category"))
    return rows


def deactivate_memory(memory_id):
    """软删除：用户应该有权让 AI 忘掉某件事。"""
    return execute("UPDATE memories SET active=0, updated_at=? WHERE id=?",
                   (now_iso(), memory_id))


def mark_recalled(memory_ids):
    """打召回点，用于避免反复念叨同一件事。"""
    if not memory_ids:
        return 0
    stamp = now_iso()
    count = 0
    for memory_id in memory_ids:
        count += execute(
            "UPDATE memories SET last_recalled_at=?, recall_count=recall_count+1 WHERE id=?",
            (stamp, memory_id),
        )
    return count


def memory_stats(character_id):
    """记忆统计，用于前端展示「他记得你多少件事」。"""
    rows = query_all(
        "SELECT category, COUNT(*) AS total FROM memories "
        "WHERE character_id=? AND active=1 GROUP BY category",
        (character_id,),
    )
    by_category = {}
    total = 0
    for row in rows:
        by_category[row["category"]] = row["total"]
        total += row["total"]
    return {
        "total": total,
        "by_category": by_category,
        "labels": CATEGORY_LABELS,
    }


def source_message_ids(character_id, limit=200):
    """已产生记忆的消息 ID 集合，避免重复抽取。"""
    rows = query_all(
        "SELECT DISTINCT source_message_id FROM memories "
        "WHERE character_id=? AND source_message_id!='' LIMIT ?",
        (character_id, limit),
    )
    return set(row["source_message_id"] for row in rows)


def search_by_embedding(character_id, query_vector, top_k=5):
    """向量召回适配位。

    当前未启用：需要在 llm 层接入 embedding 服务（如 text-embedding / 通义
    embedding），把向量写入 memories.embedding，然后在这里做余弦相似度检索。
    在接入之前，retriever 使用字面 + 重要度 + 时间衰减的混合召回，效果对
    MVP 规模（单角色几百条记忆）足够。
    """
    return []
