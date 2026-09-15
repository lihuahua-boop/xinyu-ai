# -*- coding: utf-8 -*-
"""记忆召回：决定"他现在想起哪几件事"。

混合打分 = 字面相关度 + 重要度 + 时间衰减 + 新鲜度（避免反复念叨同一件旧事）
不需要向量库就能在单角色几百条记忆的规模下给出稳定、可解释的结果。
接上 embedding 后，把字面项替换成余弦相似度即可，其余权重不变。
"""

import math

from ..common import bigrams, clamp, hours_since
from ..config import settings
from .store import CATEGORY_LABELS, list_memories, mark_recalled, query_all

W_LEXICAL = 0.42
W_IMPORTANCE = 0.26
W_RECENCY = 0.18
W_NOVELTY = 0.14

CATEGORY_HINTS = {
    "preference": ["喜欢", "讨厌", "偏好", "习惯", "口味", "食物", "音乐", "电影"],
    "emotion": ["难过", "烦", "压力", "累", "焦虑", "开心", "失眠", "心情"],
    "relationship": ["我们", "第一次", "纪念", "记得", "多久", "认识"],
    "basic": ["生日", "工作", "城市", "住", "岁"],
}

# 字面相关度太低时，只有这些类别允许被"情绪带出来"
EMOTION_DRIVEN_CATEGORIES = ("emotion", "preference", "relationship")
# 事实类记忆（生日、城市）低于这个相关度就不提，避免答非所问
MIN_LEXICAL_FOR_FACTS = 0.12

# 高频但几乎不含信息的二字词：它们会造成"今天/真的/其实"这类假相关，
# 让 AI 在闲聊时突然接一段无关旧事（驴头不对马嘴的主要来源）。
STOP_GRAMS = {
    "今天", "明天", "昨天", "前天", "现在", "然后", "已经", "一直", "一下",
    "我们", "你们", "他们", "自己", "真的", "怎么", "什么", "为什么", "这个",
    "那个", "就是", "但是", "因为", "所以", "一个", "不是", "还是", "可以",
    "觉得", "知道", "时候", "没有", "有点", "不太", "还好", "是不是", "怎么办",
    "没什么", "不知道", "没关系", "怎么样", "还可以", "有时候", "其实", "随便",
    "聊聊", "感觉", "好像", "应该", "可能", "比较", "特别", "非常", "不错",
}


def _idf_map(memories, query_grams):
    """用记忆集合估算每个二字组的区分度。"""
    df = {}
    for memory in memories:
        grams = set(bigrams(memory.get("content") or ""))
        for gram in grams & query_grams:
            df[gram] = df.get(gram, 0) + 1
    total = max(1, len(memories))
    idf = {}
    for gram in query_grams:
        idf[gram] = math.log(1.0 + total / float(1 + df.get(gram, 0)))
    return idf


def _lexical_score(query_grams, memory_grams, idf):
    """带 idf 权重的字面重合度，归一化到 0-1。"""
    if not query_grams:
        return 0.0
    total_weight = sum(idf.get(gram, 1.0) for gram in query_grams) or 1.0
    hit_weight = sum(idf.get(gram, 1.0) for gram in (query_grams & memory_grams))
    score = hit_weight / total_weight
    return clamp(score)


def _recency_score(memory):
    """时间衰减：越久远的事件权重越低，但不会归零。"""
    age_days = hours_since(memory.get("created_at")) / 24.0
    half_life = max(1.0, settings.memory_half_life_days)
    return 0.5 ** (age_days / half_life)


def _novelty_score(memory):
    """新鲜度：刚提过的记忆降权，避免 AI 反复念叨。"""
    recall_count = int(memory.get("recall_count") or 0)
    score = 1.0 / (1.0 + 0.6 * recall_count)
    hours = hours_since(memory.get("last_recalled_at"))
    if memory.get("last_recalled_at") and hours < 12:
        score *= 0.45
    return score


def _category_boost(category, query):
    """按问题类型给不同类别加权。"""
    hints = CATEGORY_HINTS.get(category, [])
    if any(hint in query for hint in hints):
        return 0.08
    if category == "basic":
        return 0.04
    return 0.0


def recall(character_id, query, emotion_result=None, top_k=None, min_score=None,
           mark_used=True):
    """召回应被想起的记忆。

    mark_used=True 时会记录召回次数，让"同一件事被反复念叨"自然地降权。
    """
    top_k = top_k or settings.memory_top_k
    min_score = settings.memory_min_score if min_score is None else min_score
    query = (query or "").strip()
    emotion_result = emotion_result or {}
    needs = emotion_result.get("needs", [])
    emotion = emotion_result.get("emotion", "neutral")

    memories = list_memories(character_id, limit=400)
    if not memories:
        return []

    query_text = query
    if emotion in ("sad", "anxious", "lonely", "tired", "angry"):
        # 情绪不好时，除了字面匹配，也把相关的情绪记忆拉进来
        query_text = query + " " + " ".join(CATEGORY_HINTS["emotion"])
    query_grams = set(gram for gram in bigrams(query_text) if gram not in STOP_GRAMS)
    idf = _idf_map(memories, query_grams)

    scored = []
    for memory in memories:
        memory_grams = set(gram for gram in bigrams(memory.get("content") or "")
                           if gram not in STOP_GRAMS)
        memory_grams |= set(gram for gram in bigrams(memory.get("key") or "")
                            if gram not in STOP_GRAMS)
        lexical = _lexical_score(query_grams, memory_grams, idf)

        # 相关性闸门：不相关的事实不要硬提，
        # 否则会出现"你说累，他提你生日"这种瞬间出戏的回复。
        tests_memory = "tests_memory" in needs
        category = memory.get("category")
        negative = emotion in ("sad", "anxious", "lonely", "tired", "angry", "crisis")
        if not tests_memory:
            if category == "basic" and lexical < MIN_LEXICAL_FOR_FACTS:
                continue
            if lexical < 0.04 and not (negative and category in ("emotion", "relationship")):
                continue
            # 中性/开心时，偏好记忆也必须真的相关，否则"随便聊一句"会冒出"你不喜欢冷处理"
            if not negative and category == "preference" and lexical < 0.08:
                continue

        importance = float(memory.get("importance") or 0.5)
        recency = _recency_score(memory)
        novelty = _novelty_score(memory)
        boost = _category_boost(category, query)
        if emotion in ("sad", "anxious", "lonely", "tired", "angry") \
                and category in ("emotion", "relationship"):
            boost += 0.05
        score = (W_LEXICAL * lexical + W_IMPORTANCE * importance +
                 W_RECENCY * recency + W_NOVELTY * novelty + boost)
        if "tests_memory" in needs:
            # 用户在考"你还记得吗"，这时要大方地想起最重要的事
            score += 0.1
        scored.append((score, lexical, memory))

    scored.sort(key=lambda item: -item[0])
    results = []
    for score, lexical, memory in scored:
        threshold = min_score
        if "tests_memory" in needs:
            threshold = min(min_score, 0.25)
        if score < threshold:
            continue
        item = dict(memory)
        item["score"] = round(score, 3)
        item["lexical"] = round(lexical, 3)
        item["category_label"] = CATEGORY_LABELS.get(item.get("category"), item.get("category"))
        item["reason"] = _reason(item, lexical)
        results.append(item)
        if len(results) >= top_k:
            break
    if mark_used and results:
        mark_recalled([item["id"] for item in results])
    return results


def _reason(memory, lexical):
    """给前端一句"为什么想起这件事"的解释，可解释性也是信任的一部分。"""
    if lexical >= 0.3:
        return "和这次聊到的事直接相关"
    if float(memory.get("importance") or 0) >= 0.85:
        return "这是你特别在意的，他一直记着"
    if memory.get("category") == "emotion":
        return "这件心事他记了很久"
    return "属于你们之间的旧事"


def build_memory_block(memories, budget_tokens=None):
    """把召回的记忆排成提示词片段，并在 token 预算内裁剪。"""
    budget = budget_tokens or settings.memory_prompt_budget
    if not memories:
        return ""
    lines = []
    used = 0
    for memory in memories:
        tags = memory.get("tags") or []
        tag_text = ("（%s）" % "、".join(tags)) if tags else ""
        line = "- [%s] %s%s" % (memory.get("category_label", ""), memory.get("content", ""), tag_text)
        cost = len(line)
        if used + cost > budget and lines:
            break
        lines.append(line)
        used += cost
    if not lines:
        return ""
    header = "以下是你记得的、和此刻可能相关的事（自然地用，不要生硬复述）："
    return header + "\n" + "\n".join(lines)


def profile_snapshot(character_id):
    """常驻画像：基础信息，每轮都注入，不占用召回额度。"""
    rows = query_all(
        "SELECT key, content FROM memories WHERE character_id=? AND active=1 "
        "AND category='basic' ORDER BY importance DESC LIMIT 6",
        (character_id,),
    )
    return [row["content"] for row in rows]
