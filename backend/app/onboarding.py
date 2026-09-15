# -*- coding: utf-8 -*-
"""人格访谈：用聊天的方式了解用户想要一个怎样的他。

对应产品方案第四章第三步。访谈结果直接改人格参数，
而不是只写进一段"偏好描述"——参数才真的会影响模型的行为。
"""

from .common import clamp

INTERVIEW_QUESTIONS = [
    {
        "key": "comfort_style",
        "question": "如果你难过，希望我怎么陪你？",
        "hint": "这决定他以后在你难受时的第一反应",
        "options": [
            {"key": "comfort", "label": "先安慰我，不要讲大道理",
             "effects": {"gentleness": 12, "preachiness": -18}},
            {"key": "advice", "label": "帮我分析一下，告诉我怎么办",
             "effects": {"preachiness": 22, "maturity": 8}},
            {"key": "silent", "label": "什么都不用说，安静陪着我就好",
             "effects": {"gentleness": 10, "initiative": -12, "preachiness": -12}},
        ],
    },
    {
        "key": "tone",
        "question": "你喜欢他怎么跟你说话？",
        "hint": "语气会决定你们相处起来的感觉",
        "options": [
            {"key": "teasing", "label": "会逗我，偶尔有点玩笑",
             "effects": {"humor": 25, "maturity": -8}},
            {"key": "gentle", "label": "认真、温柔，慢慢说",
             "effects": {"humor": -15, "gentleness": 8}},
            {"key": "steady", "label": "成熟稳重，有安全感",
             "effects": {"maturity": 18, "protectiveness": 10}},
        ],
    },
    {
        "key": "initiative",
        "question": "你希望他多久主动找你一次？",
        "hint": "主动陪伴的尺度，太频繁会变成打扰",
        "options": [
            {"key": "high", "label": "每天都想收到他的消息",
             "effects": {"initiative": 25, "attachment": 10}},
            {"key": "medium", "label": "早晚问候就好",
             "effects": {"initiative": 8}},
            {"key": "low", "label": "我说了他再回我就好",
             "effects": {"initiative": -25, "attachment": -10}},
        ],
    },
    {
        "key": "devotion",
        "question": "关系里你更在意什么？",
        "hint": "决定他表达在意的强度",
        "options": [
            {"key": "exclusive", "label": "我要明确感觉到被偏爱",
             "effects": {"possessiveness": 22, "romance": 15}},
            {"key": "free", "label": "互相独立、自在一点",
             "effects": {"possessiveness": -18, "attachment": -10}},
            {"key": "soulmate", "label": "像老朋友那样懂我",
             "effects": {"romance": -12, "maturity": 12, "humor": 8}},
        ],
    },
    {
        "key": "boundary",
        "question": "有哪些相处方式你绝对不喜欢？",
        "hint": "这些会被写进他的禁则，他不会再犯",
        "options": [
            {"key": "cold", "label": "冷处理、敷衍我",
             "effects": {"gentleness": 10, "initiative": 8}},
            {"key": "preach", "label": "说教、教育我",
             "effects": {"preachiness": -22}},
            {"key": "control", "label": "管着我、控制我",
             "effects": {"control": -28, "possessiveness": -12}},
        ],
    },
]

QUESTION_MAP = dict((item["key"], item) for item in INTERVIEW_QUESTIONS)

BOUNDARY_NOTES = {
    "cold": "不喜欢被冷处理或敷衍，需要被认真回应",
    "preach": "不喜欢被说教，反感「你应该」这类句式",
    "control": "不喜欢被管着，需要自己的空间",
}


def apply_answer(persona, profile, question_key, option_key):
    """把一次访谈回答应用到人格参数与画像上。"""
    question = QUESTION_MAP.get(question_key)
    if not question:
        return persona, profile, None
    option = None
    for item in question["options"]:
        if item["key"] == option_key:
            option = item
            break
    if option is None:
        return persona, profile, None

    persona = dict(persona or {})
    for key, delta in option["effects"].items():
        persona[key] = int(round(clamp(float(persona.get(key, 50)) + delta, 0.0, 100.0)))

    profile = dict(profile or {})
    answered = list(profile.get("interview_answers") or [])
    answered = [item for item in answered if item.get("question") != question_key]
    answered.append({
        "question": question_key,
        "question_text": question["question"],
        "answer": option_key,
        "answer_text": option["label"],
    })
    profile["interview_answers"] = answered

    if question_key == "boundary":
        dislikes = list(profile.get("dislikes") or [])
        note = BOUNDARY_NOTES.get(option_key)
        if note and note not in dislikes:
            dislikes.append(note)
        profile["dislikes"] = dislikes

    return persona, profile, option


def next_question(profile):
    """还没回答的第一个问题。"""
    answered = set()
    for item in (profile or {}).get("interview_answers") or []:
        answered.add(item.get("question"))
    for question in INTERVIEW_QUESTIONS:
        if question["key"] not in answered:
            return question
    return None


def progress(profile):
    """访谈进度。"""
    answered = len((profile or {}).get("interview_answers") or [])
    return {"answered": answered, "total": len(INTERVIEW_QUESTIONS)}
