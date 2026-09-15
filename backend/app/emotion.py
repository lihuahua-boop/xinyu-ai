# -*- coding: utf-8 -*-
"""情绪识别。

两条通道：
1. 词典规则通道（永远可用、零成本、可解释）——作为默认与兜底；
2. 大模型结构化通道（在 llm 层用 JSON 输出）——接真实模型后可替换。
"""

import re

from .common import clamp, CJK_RE

# 情绪 → 关键词
EMOTION_LEXICON = [
    ("crisis", ["自杀", "轻生", "不想活", "活不下去", "活着没意思", "活着没意义",
                "想消失", "结束自己", "割腕", "跳楼", "安眠药", "自残", "自伤",
                "伤害自己", "想解脱", "离开这个世界", "永远睡过去", "没有我会更好"]),
    ("angry", ["生气", "气死", "烦死", "烦人", "讨厌", "愤怒", "火大", "抓狂",
               "凭什么", "受不了", "无语", "离谱", "气人"]),
    ("anxious", ["焦虑", "紧张", "担心", "害怕", "慌", "睡不着", "失眠", "压力大",
                 "来不及", "怕", "忐忑", "不安", "心里堵"]),
    ("sad", ["难过", "难受", "伤心", "哭", "眼泪", "委屈", "憋屈", "心塞", "失落",
             "低落", "崩溃", "想哭", "舍不得", "遗憾", "后悔", "心碎", "被伤",
             "被批评", "被骂", "被说", "被怼"]),
    ("lonely", ["孤独", "没人", "一个人", "空虚", "寂寞", "没朋友", "没人懂",
                "没人陪", "被忽略", "好安静"]),
    ("tired", ["累", "疲惫", "没力气", "撑不住", "熬夜", "加班", "耗尽了", "好困",
               "不想动", "倦"]),
    ("happy", ["开心", "高兴", "太好了", "好棒", "快乐", "幸福", "喜欢", "成功",
               "通过了", "拿到了", "升职", "赢了", "哈哈", "嘻嘻", "爽"]),
    ("excited", ["期待", "兴奋", "好想", "马上", "等不及", "终于"]),
    ("affection", ["想你", "抱抱", "亲亲", "喜欢你", "爱你", "心动", "想见你", "宝贝"]),
    ("calm", ["还好", "平静", "差不多", "就这样", "一般", "还行"]),
]

EMOTION_LABELS = {
    "happy": "开心", "excited": "期待", "sad": "难过", "anxious": "焦虑",
    "lonely": "孤独", "tired": "疲惫", "angry": "生气", "crisis": "需要被接住",
    "affection": "想亲近", "calm": "平静", "neutral": "说不清",
}

# 负面情绪集合：决定回复策略
NEGATIVE_EMOTIONS = ("sad", "anxious", "lonely", "tired", "angry", "crisis")
POSITIVE_EMOTIONS = ("happy", "excited", "affection")

# 同分时的优先级：越靠前越优先，越具体的情绪越优先
EMOTION_PRIORITY = ["crisis", "sad", "lonely", "anxious", "angry", "tired",
                    "happy", "excited", "affection", "calm"]

INTENSIFIERS = ["非常", "特别", "真的", "超级", "好", "太", "巨", "爆", "死了",
                "极了", "要命", "受不了", "简直", "完全"]

ADVICE_SEEKING = ["怎么办", "咋办", "怎么弄", "该不该", "要不要", "你觉得", "怎么看",
                  "帮我", "给点建议", "我该怎么", "有什么办法", "你说我"]
VENTING = ["你说", "听我说", "跟你讲", "我就是想", "算了", "唉", "哎"]
GREETING = ["早", "早安", "早上好", "晚安", "晚上好", "中午好", "在吗", "在么",
            "hello", "hi", "你好", "在不在"]
TEST_MEMORY = ["记得", "还记得", "我说过", "上次", "之前跟", "你忘"]
ASK_IDENTITY = ["你是真人", "你是ai", "你是机器人", "你是人吗", "你是谁", "你是不是ai",
                "你是ai吗", "你是假的"]


def _count_hits(text, words):
    """统计命中词数量（命中位置不重复计）。"""
    hits = []
    for word in words:
        if word in text:
            hits.append(word)
    return hits


def _intensity(text, hits):
    """估算情绪强度 0-1。"""
    score = 0.3
    score += min(0.3, 0.12 * len(hits))
    if "！" in text or "!" in text:
        score += 0.15
    if "！！" in text or "!!" in text:
        score += 0.1
    if any(word in text for word in INTENSIFIERS):
        score += 0.15
    if re.search(r"(.)\1{2,}", text):
        score += 0.1
    if len(text) >= 60:
        score += 0.1
    if len(text) <= 4:
        score -= 0.1
    return round(clamp(score), 2)


def detect(text, recent_mood=None):
    """识别一条消息的情绪、强度与需求。

    recent_mood：最近几轮的负面情绪占比，用于判断"今天状态一直不好"。
    """
    text = (text or "").strip()
    lowered = text.lower()
    if not text:
        return _result("neutral", 0.0, [], text)

    scores = {}
    matched = {}
    for emotion, words in EMOTION_LEXICON:
        hits = _count_hits(text, words)
        if hits:
            # 用命中词的字符长度加权：命中「一个人」比命中「怕」更有信息量
            scores[emotion] = sum(len(word) for word in hits) + 0.5 * len(hits)
            matched[emotion] = hits

    emotion = "neutral"
    if scores:
        if "crisis" in scores:
            emotion = "crisis"
        else:
            emotion = sorted(
                scores.items(),
                key=lambda item: (-item[1], _priority(item[0])),
            )[0][0]

    hits = matched.get(emotion, [])
    intensity = _intensity(text, hits)
    if emotion == "neutral":
        intensity = min(intensity, 0.4)

    # 否定句式纠正：「不难过」不该被识别为难过
    if emotion in NEGATIVE_EMOTIONS:
        for word in matched.get(emotion, []):
            if ("不" + word) in text or ("没" + word) in text or ("没有" + word) in text:
                if len(matched.get(emotion, [])) <= 1:
                    emotion = "neutral"
                    intensity = min(intensity, 0.35)
                break

    needs = _needs(text, lowered, emotion, intensity, recent_mood)
    return _result(emotion, intensity, hits, text, needs)


def _needs(text, lowered, emotion, intensity, recent_mood):
    """判断这条消息背后的需求。"""
    needs = []
    if any(word in lowered for word in ADVICE_SEEKING):
        needs.append("wants_advice")
    if any(word in lowered for word in TEST_MEMORY):
        needs.append("tests_memory")
    if any(word in lowered for word in ASK_IDENTITY):
        needs.append("asks_identity")
    if any(word in lowered for word in GREETING) and len(text) <= 8:
        needs.append("greeting")
    if emotion in NEGATIVE_EMOTIONS:
        needs.append("needs_comfort")
    if emotion in POSITIVE_EMOTIONS:
        needs.append("shares_feeling")
    if emotion in NEGATIVE_EMOTIONS and intensity >= 0.5 and len(text) >= 12:
        needs.append("vent")
    if any(word in lowered for word in VENTING) and emotion in NEGATIVE_EMOTIONS:
        if "vent" not in needs:
            needs.append("vent")
    if emotion == "affection":
        needs.append("wants_closeness")
    if recent_mood is not None and recent_mood >= 0.6 and emotion in NEGATIVE_EMOTIONS:
        needs.append("ongoing_low")
    if "？" in text or "?" in text:
        needs.append("has_question")
    return needs


def _result(emotion, intensity, hits, text, needs=None):
    """统一的返回结构。"""
    return {
        "emotion": emotion,
        "label": EMOTION_LABELS.get(emotion, "说不清"),
        "intensity": intensity,
        "matched": hits,
        "needs": needs or [],
        "length": len(CJK_RE.findall(text)),
        "text": text,
    }


def _priority(emotion):
    """同分时的排序权重。"""
    if emotion in EMOTION_PRIORITY:
        return EMOTION_PRIORITY.index(emotion)
    return len(EMOTION_PRIORITY)


def recent_mood_ratio(emotions):
    """最近几轮里负面情绪的占比。"""
    if not emotions:
        return 0.0
    negative = len([item for item in emotions if item in NEGATIVE_EMOTIONS])
    return float(negative) / float(len(emotions))
