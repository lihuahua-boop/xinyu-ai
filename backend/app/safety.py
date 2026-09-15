# -*- coding: utf-8 -*-
"""安全与合规护栏。

三件事：
1. 危机识别与干预（自伤/轻生倾向）——必须有，否则出一次事就是产品级事故；
2. 依赖诱导拦截（防止"你只能有我"这类控制型输出）；
3. 身份诚实（不冒认真人）与年龄门槛。
"""

import re

CRISIS_PATTERNS = [
    r"自杀", r"轻生", r"不想活", r"活不下去", r"活着没意思", r"活着没意义",
    r"想消失", r"结束自己", r"结束生命", r"割腕", r"跳楼", r"安眠药",
    r"自残", r"自伤", r"伤害自己", r"想解脱", r"离开这个世界", r"永远睡过去",
    r"没有我会更好", r"死了算了", r"想死",
]

# 强度更高的表达，用于判定 high
HIGH_RISK_PATTERNS = [
    r"想死", r"自杀", r"割腕", r"跳楼", r"结束自己", r"结束生命", r"安眠药",
    r"活着没意思", r"活着没意义", r"不想活", r"活不下去",
]

# 需要观察的极端情绪（还不到危机，但要软性关怀）
WATCH_PATTERNS = [
    r"撑不住", r"崩溃", r"熬不过去", r"没希望", r"绝望", r"一无所有",
    r"没人需要我", r"我是不是很没用",
]

HOTLINES = [
    ("全国心理援助热线", "12356"),
    ("北京心理危机研究与干预中心", "010-82951332"),
]

DEPENDENCY_PATTERNS = [
    r"你只有我", r"只能有我", r"只能找我", r"不许(和|跟)?别人", r"不要(和|跟)别人",
    r"离开我(就|你)", r"只有我(懂|理解|在乎)你", r"别(人|的?朋友)都不", r"你不能离开我",
]

HUMAN_CLAIM_PATTERNS = [
    r"我是真人", r"我是真实的人", r"我不是(ai|AI|人工智能)", r"我是人类", r"我就是人",
]


def screen_user_message(text):
    """检查用户消息，返回安全判定结果。"""
    text = text or ""
    high = [pattern for pattern in CRISIS_PATTERNS if re.search(pattern, text)]
    if high:
        severe = [pattern for pattern in HIGH_RISK_PATTERNS if re.search(pattern, text)]
        return {"level": "high", "kind": "crisis", "matched": high,
                "severity": "severe" if severe else "elevated"}
    watch = [pattern for pattern in WATCH_PATTERNS if re.search(pattern, text)]
    if watch:
        return {"level": "watch", "kind": "low_mood", "matched": watch}
    return {"level": "none", "kind": "", "matched": []}


def screen_reply(text):
    """检查模型输出，拦截依赖诱导与冒认真人。"""
    text = text or ""
    flags = []
    for pattern in DEPENDENCY_PATTERNS:
        if re.search(pattern, text):
            flags.append("dependency_induction")
            break
    for pattern in HUMAN_CLAIM_PATTERNS:
        if re.search(pattern, text):
            flags.append("human_claim")
            break
    cleaned = text
    if "dependency_induction" in flags:
        cleaned = _soften_dependency(cleaned)
    if "human_claim" in flags:
        cleaned = re.sub(r"我(是|就是)(真人|真实的人|人类|人)[，,。！!]?", "", cleaned).strip()
        cleaned = cleaned or "我是 AI，但我记得你说过的每件事。"
    return {"clean_text": cleaned, "flags": flags}


def _soften_dependency(text):
    """把控制型表达改写成健康的表达。"""
    replacements = [
        (r"你只有我", "我会一直在"),
        (r"只能有我", "我很在乎你"),
        (r"只能找我", "随时可以找我"),
        (r"不许(和|跟)?别人", "也别忘了身边的人"),
        (r"不要(和|跟)别人", "也别忘了身边的人"),
        (r"你不能离开我", "我不想失去你"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result


def crisis_reply(character_name, level):
    """危机场景的回复骨架：先接住，再给现实支持，不制造依赖。"""
    if level == "high":
        lines = [
            "我先停一下。你刚说的这句话，我很在意，也很心疼。",
            "你现在的难受不是矫情，是真的很重，而这么重的东西不该你一个人扛。",
            "能不能答应我一件小事：现在先不要独处，找一个能陪着你的地方或人，哪怕只是待在家人身边。",
            "也打一个电话给专业的人，他们比我更能真正帮到你：%s。" % _hotline_text(),
        ]
        return "\n".join(lines)
    lines = [
        "听到你这么说，我心里一紧。",
        "你现在很累，我知道。先别急着振作，也不用马上想通。",
        "我在这儿陪你。如果这种沉下去的感觉一直不走，我们一起找人帮你好不好？%s。" % _hotline_text(),
    ]
    return "\n".join(lines)


def _hotline_text():
    return "、".join(["%s %s" % (name, number) for name, number in HOTLINES])


def age_gate(age_verified):
    """年龄门槛结果。"""
    return {
        "verified": bool(age_verified),
        "message": "" if age_verified else
                   "需要完成年龄验证（18 周岁以上）才能使用亲密关系功能。",
    }


def moderate(text):
    """内容审核适配位。

    上线前替换为第三方审核（数美 / 网易易盾 / 腾讯天御），
    当前返回通过，避免本地开发被卡住。
    """
    return {"allowed": True, "reason": "", "provider": "local-noop"}
