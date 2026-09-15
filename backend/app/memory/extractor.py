# -*- coding: utf-8 -*-
"""记忆写入：从一句人话里抽取值得记住的事实。

设计原则：
- 默认走规则，零成本、可解释、离线可用；
- 允许大模型兜底（extract_with_llm），但规则命中优先，避免模型乱编；
- 只抽用户明确说过的事实，绝不替用户"编"经历。
"""

import re

from ..common import clamp, truncate

PREFERENCE_STRONG = ["最爱", "超喜欢", "很喜欢", "特别喜欢", "很喜欢吃"]
NEGATIVE_MARKERS = ["不喜欢", "讨厌", "受不了", "最烦", "很烦", "接受不了", "反感"]
IMPORTANCE_MARKERS = ["永远", "一直", "最重要", "很在意", "特别重要", "第一次",
                      "从来没有", "一辈子", "记住"]

RULE_PATTERNS = [
    {
        "category": "basic",
        "key": "birthday",
        "pattern": r"我(?:的)?生日(?:是|在)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]",
        "importance": 0.85,
        "tags": ["生日"],
    },
    {
        "category": "basic",
        "key": "name",
        "pattern": r"我(?:叫|的名字是|名字叫)\s*([\u4e00-\u9fffA-Za-z]{1,8})",
        "importance": 0.8,
        "tags": ["称呼"],
    },
    {
        "category": "basic",
        "key": "occupation",
        "pattern": r"我(?:是|在)(?:做|当)?\s*([\u4e00-\u9fff]{2,10})"
                   r"(?:工作|上班|师|医生|护士|老师|律师|程序员|设计师|会计|销售|学生)",
        "importance": 0.7,
        "tags": ["职业"],
    },
    {
        "category": "basic",
        "key": "city",
        "pattern": r"我(?:在|住在|住|坐标|定居在)\s*([\u4e00-\u9fff]{2,8})"
                   r"(?:工作|上班|生活|读书|读研|定居)?",
        "importance": 0.6,
        "tags": ["城市"],
    },
    {
        "category": "preference",
        "key": "like",
        "pattern": r"我(?:很|超|特别|最)?(?:喜欢|爱|爱吃|爱喝)\s*([^。！？!?，,\n]{1,18})",
        "importance": 0.65,
        "tags": ["喜欢"],
    },
    {
        "category": "preference",
        "key": "dislike",
        "pattern": r"我(?:很|特别)?(?:不喜欢|讨厌|受不了|烦)\s*([^。！？!?，,\n]{1,18})",
        "importance": 0.68,
        "tags": ["不喜欢"],
    },
    {
        "category": "preference",
        "key": "pet",
        "pattern": r"我(?:养了|有一只|有只|家里有)\s*([^。！？!?，,\n]{1,16})",
        "importance": 0.62,
        "tags": ["生活"],
    },
]

# 用户对"你"的期待，直接关系到人格调整
EXPECTATION_PATTERNS = [
    r"我希望你([^。！？!?\n]{1,30})",
    r"你能不能别([^。！？!?\n]{1,20})",
    r"你别([^。！？!?\n]{1,20})",
    r"我喜欢你([^。！？!?\n]{1,20})",
]

# 经历/压力事件
EVENT_PATTERNS = [
    (r"(面试|考试|答辩|述职|汇报|演讲|比赛|体检|搬家|分手|离职|裁员)", "一件重要的事"),
    (r"(加班|熬夜|失眠|赶工|通宵)", "日常压力"),
    (r"(被(?:领导|老板|同事|老师|客户|爸妈|妈妈|爸爸))", "人际压力"),
]


def extract_memories(text, emotion_result, source_message_id=""):
    """从用户消息里抽取记忆条目。"""
    text = (text or "").strip()
    if not text:
        return []

    emotion = (emotion_result or {}).get("emotion", "neutral")
    intensity = float((emotion_result or {}).get("intensity") or 0.0)
    memories = []

    for rule in RULE_PATTERNS:
        match = re.search(rule["pattern"], text)
        if not match:
            continue
        value = (match.group(1) or "").strip()
        if not value or len(value) < 1:
            continue
        content = _build_content(rule, value, text)
        memories.append({
            "category": rule["category"],
            "key": rule["key"],
            "content": content,
            "importance": _importance(rule["importance"], text, intensity),
            "confidence": 0.8,
            "tags": list(rule["tags"]),
            "source_message_id": source_message_id,
        })

    memory = _extract_expectation(text)
    if memory:
        memory["source_message_id"] = source_message_id
        memories.append(memory)

    # 如果这句话已经产出了明确的事实（偏好/基础信息），就不再记一条泛泛的"心事"，
    # 否则同一句话会变成两条记忆，回响时读起来像复读。
    has_fact = any(item["category"] in ("preference", "basic") for item in memories)
    if not has_fact:
        memory = _extract_event(text, emotion, intensity)
        if memory:
            memory["source_message_id"] = source_message_id
            memories.append(memory)

    memory = _extract_explicit_remember(text)
    if memory:
        memory["source_message_id"] = source_message_id
        memories.append(memory)

    return _dedupe(memories)


def _build_content(rule, value, text):
    """把正则命中翻译成一句自然语言的记忆。"""
    key = rule["key"]
    if key == "birthday":
        return "用户的生日是 " + value + " 月"
    if key == "name":
        return "用户的名字或昵称是「%s」" % value
    if key == "occupation":
        return "用户的工作与「%s」相关" % value
    if key == "city":
        return "用户在「%s」生活或工作" % value
    if key == "like":
        return "用户喜欢%s" % value
    if key == "dislike":
        return "用户不喜欢%s" % value
    if key == "pet":
        return "用户家里有%s" % value
    return truncate(text, 40)


def _extract_expectation(text):
    """抽取用户对陪伴方式的期待，用于驱动人格微调。"""
    for pattern in EXPECTATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if len(value) < 2:
                continue
            return {
                "category": "preference",
                "key": "expectation",
                "content": "用户希望被这样对待：%s" % value,
                "importance": 0.9,
                "confidence": 0.75,
                "tags": ["沟通偏好"],
            }
    return None


def _extract_event(text, emotion, intensity):
    """抽取值得记住的经历或压力事件。"""
    if emotion not in ("sad", "anxious", "lonely", "tired", "angry", "happy", "excited"):
        return None
    if len(text) < 6:
        return None
    hit_label = ""
    hit_word = ""
    for pattern, label in EVENT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            hit_label = label
            hit_word = match.group(1)
            break
    if not hit_label and intensity < 0.55:
        return None
    if not hit_label and len(text) < 14:
        return None
    tags = [hit_label] if hit_label else ["情绪"]
    if hit_label:
        content = "用户最近在经历%s：「%s」" % (hit_label, truncate(text, 40))
    else:
        content = "用户最近的一件心事：「%s」" % truncate(text, 40)
    return {
        "category": "emotion",
        "key": hit_word or "",
        "content": content,
        "importance": round(clamp(0.55 + intensity * 0.35, 0.0, 1.0), 3),
        "confidence": 0.6,
        "tags": tags,
    }


def _extract_explicit_remember(text):
    """用户明确说"记住"的东西，重要度拉满。"""
    match = re.search(r"(?:记住|记得|别忘了|要记得)\s*([^。！？!?\n]{2,40})", text)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) < 2:
        return None
    return {
        "category": "emotion",
        "key": "",
        "content": "用户特别希望我记得：" + value,
        "importance": 0.95,
        "confidence": 0.85,
        "tags": ["特别叮嘱"],
    }


def _importance(base, text, intensity):
    """重要度 = 规则基础值 + 显式强调 + 情绪强度。"""
    score = base + intensity * 0.12
    if any(marker in text for marker in IMPORTANCE_MARKERS):
        score += 0.12
    return round(clamp(score, 0.0, 1.0), 3)


def _dedupe(memories):
    """同一轮内按类别 + 内容去重。"""
    seen = set()
    result = []
    for memory in memories:
        token = (memory["category"], memory["content"])
        if token in seen:
            continue
        seen.add(token)
        result.append(memory)
    return result


def extract_profile_updates(text, profile):
    """更新结构化画像（用于每轮常驻注入，不占检索额度）。"""
    profile = dict(profile or {})
    text = text or ""
    interests = list(profile.get("interests") or [])

    for pattern in [r"我(?:很|超|特别|最)?(?:喜欢|爱)\s*([^。！？!?，,\n]{1,18})"]:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            if value and value not in interests:
                interests.append(value)
                interests = interests[-8:]
    profile["interests"] = interests

    match = re.search(r"我(?:的)?生日(?:是|在)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if match:
        profile["birthday"] = "%d月%d日" % (int(match.group(1)), int(match.group(2)))

    match = re.search(r"我(?:叫|的名字是|名字叫)\s*([\u4e00-\u9fffA-Za-z]{1,8})", text)
    if match:
        profile["display_name"] = match.group(1)

    match = re.search(r"我(?:在|住在|住|坐标|定居在)\s*([\u4e00-\u9fff]{2,8})"
                      r"(?:工作|上班|生活|读书|读研|定居)?", text)
    if match:
        profile["city"] = match.group(1)

    if "别讲道理" in text or "不要说教" in text or "别教育我" in text:
        profile["wants_no_preaching"] = True
    if "抱" in text and "抱抱" in text:
        profile["likes_hug"] = True
    return profile


EXTRACT_SYSTEM = (
    "你是记忆抽取器。从用户这句心里话里，抽取「值得长期记住」的事实。\n"
    "只抽取用户明确说过的事实，绝不编造；没有可记的就返回空数组。\n"
    "类别只能是 basic（基础信息）、preference（偏好）、emotion（经历/情绪）、"
    "relationship（关系）之一。\n"
    "importance 和 confidence 用 0 到 1 的小数。\n"
    "严格输出 JSON：{\"memories\":[{\"category\":\"emotion\",\"key\":\"\","
    "\"content\":\"用户最近压力很大，因为面试紧张到失眠\",\"importance\":0.8,"
    "\"confidence\":0.9,\"tags\":[\"压力\"]}]}"
)


def extract_memories_with_llm(provider, text, emotion_result=None):
    """用大模型做结构化记忆抽取（规则抽取之外的第二通道）。

    调用失败时返回空列表，由规则通道兜底，绝不能因为抽取失败影响主流程。
    """
    text = (text or "").strip()
    if not text or provider is None:
        return []
    try:
        data = provider.complete_json(EXTRACT_SYSTEM, text)
    except Exception:
        return []
    valid = ("basic", "preference", "emotion", "relationship")
    result = []
    for item in data.get("memories") or []:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        content = (item.get("content") or "").strip()
        if category not in valid or not content:
            continue
        try:
            importance = clamp(float(item.get("importance", 0.6)), 0.0, 1.0)
            confidence = clamp(float(item.get("confidence", 0.7)), 0.0, 1.0)
        except (TypeError, ValueError):
            importance, confidence = 0.6, 0.7
        result.append({
            "category": category,
            "key": str(item.get("key") or ""),
            "content": content,
            "importance": round(importance, 3),
            "confidence": round(confidence, 3),
            "tags": [str(tag) for tag in (item.get("tags") or [])][:4],
        })
    return result
