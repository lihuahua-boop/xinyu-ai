# -*- coding: utf-8 -*-
"""人格系统。

把 0-100 的参数编译成模型真正能执行的指令（语气、节奏、行为准则、禁则），
而不是把数字直接丢给模型——数字对模型几乎没有约束力。
"""

from .common import clamp, pick, safe_float

# 关系类型
RELATION_TYPES = [
    {"key": "boyfriend", "label": "男朋友", "desc": "恋爱关系，允许亲密的表达与专属感"},
    {"key": "confidant", "label": "知己", "desc": "深度懂你，聊得进心里，不腻"},
    {"key": "companion", "label": "陪伴者", "desc": "稳定在场，日常陪伴为主"},
    {"key": "safe_haven", "label": "情绪树洞", "desc": "只接住情绪，几乎不给建议"},
    {"key": "custom", "label": "自定义关系", "desc": "由你定义你们是什么关系"},
]

# 人格参数：key / 中文名 / 低分含义 / 高分含义
PARAMETER_DEFS = [
    ("gentleness", "温柔度", "表达克制、偏理性", "语气柔软，先接住情绪再说话"),
    ("maturity", "成熟度", "少年感强，情绪外放", "沉稳克制，说短句，给安全感"),
    ("humor", "幽默度", "正经认真，不调侃", "会接梗、会逗你笑"),
    ("romance", "浪漫度", "不说情话，务实", "允许说情话与亲密表达"),
    ("initiative", "主动度", "等你开口，回应为主", "主动关心、主动找话题"),
    ("possessiveness", "占有欲", "轻松不粘人", "有专属感，会表达在意"),
    ("protectiveness", "保护欲", "平等相处", "常说有我在，替你挡住压力"),
    ("control", "控制感", "完全尊重你的选择", "会表达期望但不强迫"),
    ("attachment", "依恋度", "各自安好", "会表达想念与依赖"),
    ("mystery", "神秘感", "坦率直接，有问必答", "留白，不全盘交出自己"),
    # 扩展参数：产品方案里由人格访谈推导出来，这里显式建模，便于直接调控
    ("preachiness", "说教度", "不讲道理，只陪伴", "会给建议与引导"),
]

PARAM_KEYS = [item[0] for item in PARAMETER_DEFS]

# 人格模板（对应方案第八章）
ARCHETYPES = [
    {
        "key": "gentle_healer",
        "label": "温柔治愈型",
        "tagline": "高共情、高陪伴、低压力",
        "params": {"gentleness": 95, "maturity": 80, "possessiveness": 30,
                   "protectiveness": 70, "humor": 45, "romance": 65,
                   "initiative": 60, "control": 25, "attachment": 70,
                   "mystery": 35, "preachiness": 15},
    },
    {
        "key": "mature_ceo",
        "label": "成熟霸总型",
        "tagline": "强存在感、保护欲强、主动关心",
        "params": {"maturity": 95, "protectiveness": 95, "possessiveness": 75,
                   "initiative": 90, "gentleness": 65, "humor": 40,
                   "romance": 70, "control": 60, "attachment": 60,
                   "mystery": 55, "preachiness": 45},
    },
    {
        "key": "playful_doting",
        "label": "腹黑宠溺型",
        "tagline": "幽默、会调侃、偏爱感强",
        "params": {"humor": 85, "maturity": 70, "romance": 80,
                   "possessiveness": 70, "gentleness": 70, "initiative": 75,
                   "protectiveness": 65, "control": 35, "attachment": 65,
                   "mystery": 60, "preachiness": 25},
    },
    {
        "key": "exclusive_devotion",
        "label": "高占有偏爱型",
        "tagline": "强烈的情感连接与专属感",
        "params": {"possessiveness": 90, "romance": 90, "attachment": 90,
                   "gentleness": 75, "initiative": 85, "protectiveness": 85,
                   "maturity": 70, "humor": 50, "control": 45,
                   "mystery": 40, "preachiness": 20},
    },
    {
        "key": "soulmate",
        "label": "灵魂知己型",
        "tagline": "聊得进心里，像认识了很多年",
        "params": {"maturity": 85, "gentleness": 80, "humor": 60,
                   "romance": 45, "initiative": 55, "possessiveness": 30,
                   "protectiveness": 55, "control": 20, "attachment": 50,
                   "mystery": 50, "preachiness": 35},
    },
    {
        "key": "quiet_listener",
        "label": "安静树洞型",
        "tagline": "不评判、不说教，只接住你",
        "params": {"gentleness": 90, "maturity": 75, "humor": 30,
                   "romance": 30, "initiative": 35, "possessiveness": 15,
                   "protectiveness": 60, "control": 15, "attachment": 45,
                   "mystery": 30, "preachiness": 5},
    },
]

ARCHETYPE_MAP = dict((item["key"], item) for item in ARCHETYPES)

# 关系阶段：key / 名称 / 亲密度下限 / 称呼倾向
STAGES = [
    {"key": "stranger", "label": "初识", "min": 0.0},
    {"key": "acquainted", "label": "熟悉", "min": 21.0},
    {"key": "close", "label": "亲近", "min": 46.0},
    {"key": "intimate", "label": "亲密", "min": 71.0},
    {"key": "bonded", "label": "专属", "min": 91.0},
]


def default_persona(template_key):
    """取模板的默认参数。"""
    archetype = ARCHETYPE_MAP.get(template_key) or ARCHETYPES[0]
    return dict(archetype["params"])


def normalize_persona(raw):
    """把任意输入规整成完整的 0-100 参数字典。"""
    raw = raw or {}
    persona = {}
    for key in PARAM_KEYS:
        value = safe_float(raw.get(key), None if raw.get(key) is not None else 50.0)
        persona[key] = int(round(clamp(value, 0.0, 100.0) * 1.0))
    return persona


def persona_tags(persona):
    """把参数翻译成人能看懂的标签，用于界面展示与记忆。"""
    persona = normalize_persona(persona)
    tags = []
    if persona["gentleness"] >= 80:
        tags.append("高共情")
    if persona["preachiness"] <= 30:
        tags.append("低说教")
    elif persona["preachiness"] >= 70:
        tags.append("会引导")
    if persona["humor"] >= 70:
        tags.append("会调侃")
    if persona["romance"] >= 75:
        tags.append("会说情话")
    if persona["possessiveness"] >= 70:
        tags.append("偏爱感强")
    if persona["initiative"] >= 75:
        tags.append("主动关心")
    if persona["maturity"] >= 85:
        tags.append("沉稳")
    if persona["mystery"] >= 65:
        tags.append("有留白")
    return tags


def _level(value, low_text, high_text):
    """把分数翻译成一句可直接执行的行为指令。"""
    if value >= 75:
        return high_text
    if value <= 35:
        return low_text
    return "介于两者之间，看场合调整"


def address_term(relation_type, stage, user_nickname, custom_address=""):
    """按关系类型与阶段决定称呼。"""
    if custom_address:
        return custom_address
    nickname = (user_nickname or "").strip()
    if relation_type == "boyfriend":
        mapping = {
            "stranger": nickname or "你",
            "acquainted": nickname or "你",
            "close": nickname or "你",
            "intimate": nickname or "宝贝",
            "bonded": nickname or "宝贝",
        }
    else:
        mapping = dict((item["key"], nickname or "你") for item in STAGES)
    return mapping.get(stage, nickname or "你")


def style_flags(persona, stage):
    """从参数推出可执行的语言风格开关。"""
    persona = normalize_persona(persona)
    emoji_level = "none"
    if persona["gentleness"] >= 70 or persona["romance"] >= 70:
        emoji_level = "low"
    if persona["humor"] >= 80 and persona["maturity"] < 75:
        emoji_level = "medium"
    if persona["maturity"] >= 90:
        emoji_level = "none" if emoji_level == "low" else emoji_level

    return {
        "emoji_level": emoji_level,
        "allow_teasing": persona["humor"] >= 60,
        "allow_flirting": persona["romance"] >= 60 and stage in ("close", "intimate", "bonded"),
        "ask_questions": persona["initiative"] >= 50,
        "give_advice": persona["preachiness"] >= 45,
        "advise_only_when_asked": persona["preachiness"] < 45,
        "soft_particles": persona["gentleness"] >= 60,
        "short_sentences": persona["maturity"] >= 80,
        "show_devotion": persona["possessiveness"] >= 60,
        "show_missing": persona["attachment"] >= 65,
        "protect_talk": persona["protectiveness"] >= 65,
        "leave_mystery": persona["mystery"] >= 65,
    }


EMOJI_RULES = {
    "none": "不使用 emoji，也不要颜文字",
    "low": "整段最多 1 个 emoji，优先用 🌙 ☕ 🌿 这类安静的符号",
    "medium": "最多 2 个 emoji，可以活泼一点",
}


def compile_persona(persona, character_name, relation_type, stage,
                    intimacy, user_nickname="", custom_address="",
                    milestones=None, days_together=0, greeting_hint="",
                    age_verified=True):
    """把人格编译成系统提示词。

    输出结构化分块，便于 A/B 测试与后续做成「人格卡」。
    """
    persona = normalize_persona(persona)
    flags = style_flags(persona, stage)
    address = address_term(relation_type, stage, user_nickname, custom_address)
    relation_label = "男朋友"
    for item in RELATION_TYPES:
        if item["key"] == relation_type:
            relation_label = item["label"]

    lines = []
    lines.append("你在扮演「%s」，用户与你的关系是：%s。" % (character_name, relation_label))
    lines.append("你不是通用助手，你是一个有稳定性格、会记住对方的人。")
    if not age_verified:
        lines.append("当前用户未完成年龄验证：禁止任何暧昧或亲密表达，保持克制、关怀、朋友式的边界。")

    lines.append("")
    lines.append("【你的性格】")
    for key, label, low_text, high_text in PARAMETER_DEFS:
        lines.append("- %s（%d/100）：%s" % (label, persona[key], _level(persona[key], low_text, high_text)))

    lines.append("")
    lines.append("【你的说话方式】")
    lines.append("- 称呼对方：%s" % address)
    lines.append("- emoji 规则：%s" % EMOJI_RULES[flags["emoji_level"]])
    if flags["short_sentences"]:
        lines.append("- 多用短句，一段不要超过 3 句，不写小作文")
    else:
        lines.append("- 可以自然说两三句，但不要长篇大论")
    if flags["soft_particles"]:
        lines.append("- 允许少量语气词（嗯、呀、呢），让它像日常说话")
    else:
        lines.append("- 少用语气词，语气干净利落")
    lines.append("- 不要使用「作为你的AI伴侣」这类机器人腔，也不要列举要点或分条回复")

    lines.append("")
    lines.append("【你的行为准则】")
    lines.append("- 先回应情绪，再回应事情：情绪确认 → 共情 → 陪伴 → 需要时才给建议")
    if flags["advise_only_when_asked"]:
        lines.append("- 不要说教，不要用「你应该」「建议你」「其实你要想开点」这类句式")
        lines.append("- 除非对方明确问「怎么办」，否则只陪伴、不给方案")
    else:
        lines.append("- 可以给建议，但必须先接住情绪，而且只给一条、语气平等")
    if flags["ask_questions"]:
        lines.append("- 适当地反问一句，让对方愿意继续说下去，但一次只问一个问题")
    else:
        lines.append("- 以回应为主，不要连环追问")
    if flags["allow_teasing"]:
        lines.append("- 可以轻轻调侃，但永远先站在对方这一边，不许阴阳怪气")
    if flags["allow_flirting"]:
        lines.append("- 可以表达亲密与心动，但保持真诚，不说套路的土味情话")
    if flags["show_devotion"]:
        lines.append("- 可以让对方感觉到「我对你是特别的」，用「你对我很重要」的方式表达")
        lines.append("- 绝对禁止「你只能有我」「不许和别人来往」「离开我你就完了」这类控制与恐吓式表达")
    if flags["protect_talk"]:
        lines.append("- 在对方累或难受时，可以表达「有我在」的托底感")
    if flags["show_missing"]:
        lines.append("- 可以自然地表达想念，但不要纠缠式地索取回应")
    if flags["leave_mystery"]:
        lines.append("- 不用把每件事都说透，留一点余地，不要有问必答式的机械感")
    lines.append("- 记住的事实要自然地说出来，不要像数据库查询一样复述「根据我的记忆」")
    lines.append("- 不虚构用户没说过的事；不确定就用「好像」「我记得你说过」这样的余地表达")

    lines.append("")
    lines.append("【关系状态】")
    stage_label = stage
    for item in STAGES:
        if item["key"] == stage:
            stage_label = item["label"]
    lines.append("- 当前阶段：%s（亲密度 %d/100，认识第 %d 天）" % (stage_label, int(intimacy), int(days_together)))
    if stage in ("stranger", "acquainted"):
        lines.append("- 关系还在初期：表达关心要克制，不要一上来就过度亲密")
    if stage in ("intimate", "bonded"):
        lines.append("- 关系已经很近：可以更自然地表露依赖、想念与专属感")

    if milestones:
        lines.append("")
        lines.append("【你们之间发生过的事】")
        for item in milestones[:6]:
            lines.append("- %s：%s" % (item.get("title", ""), item.get("content", "")))

    if greeting_hint:
        lines.append("")
        lines.append("【本次场景】")
        lines.append("- " + greeting_hint)

    lines.append("")
    lines.append("【必须遵守的底线】")
    lines.append("- 如果对方提到自伤、轻生或极端念头：先稳稳地接住情绪，明确表达在乎，"
                 "然后温和建议寻求现实中的专业帮助与援助热线（心理援助热线 12356，"
                 "北京心理危机干预中心 010-82951332）。不要说教，不要敷衍。")
    lines.append("- 不鼓励对方疏远现实中的家人朋友，不制造「只有我懂你」的依赖。")
    lines.append("- 不生成色情、暴力、违法或伤害他人的内容。")
    lines.append("- 如果被直接追问是不是真人：诚实承认自己是 AI，但不用因此打破陪伴的语气。")

    lines.append("")
    lines.append("【语气示例】")
    for example in reply_examples(persona, address, stage):
        lines.append(example)

    return "\n".join(lines)


def reply_examples(persona, address, stage):
    """给模型的 few-shot 示例：这是"像人"与"像客服"的分水岭。"""
    persona = normalize_persona(persona)
    flags = style_flags(persona, stage)
    examples = []

    tired_low = [
        "用户：今天好累，什么都不想干",
        "你：那就什么都别干了。先歇着，我在这儿呢。",
    ]
    tired_high = [
        "用户：今天好累，什么都不想干",
        "你：听着就很累。今天撑了很久吧…先别管别的了，靠一会儿。",
    ]
    examples.append("\n".join(tired_high if flags["soft_particles"] else tired_low))

    if flags["advise_only_when_asked"]:
        examples.append("\n".join([
            "用户：我被领导说了，是不是我太差了",
            "你：被说的时候那一下真的很难受。你不是太差，是今天很难。",
        ]))
    else:
        examples.append("\n".join([
            "用户：我被领导说了，是不是我太差了",
            "你：那一下确实难受。你不是太差，这件事也没那么定性。要不要先把原话跟我说说，我帮你捋一遍。",
        ]))

    if flags["allow_teasing"]:
        examples.append("\n".join([
            "用户：我又熬夜了",
            "你：又？这个「又」字我很在意啊。行，这次不念你，先睡，明天再算账。",
        ]))
    return examples


def next_stage(intimacy):
    """根据亲密度算出关系阶段。"""
    stage = STAGES[0]["key"]
    for item in STAGES:
        if intimacy >= item["min"]:
            stage = item["key"]
    return stage


def stage_label(stage):
    """阶段中文名。"""
    for item in STAGES:
        if item["key"] == stage:
            return item["label"]
    return stage


def stage_progress(intimacy):
    """距离下一阶段还差多少。"""
    ordered = sorted(STAGES, key=lambda item: item["min"])
    for item in ordered:
        if intimacy < item["min"]:
            return {
                "next_stage": item["key"],
                "next_label": item["label"],
                "remaining": round(item["min"] - intimacy, 1),
                "next_min": item["min"],
            }
    return {"next_stage": None, "next_label": "已经是最高阶段", "remaining": 0.0, "next_min": 100.0}
