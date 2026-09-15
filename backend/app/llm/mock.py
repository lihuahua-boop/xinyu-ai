# -*- coding: utf-8 -*-
"""本地情感回复引擎（默认模式）。

没有 API Key 也能跑通全流程：靠情绪识别 + 人格风格 + 记忆回响拼出像样的陪伴回复。
它不是要替代大模型，而是保证产品在"零成本 / 断网 / 未接模型"时依然可用，
并且让记忆、关系、安全这些系统级能力可以被真实验证。
"""

from ..common import pick, stable_hash, truncate
from .base import ChatProvider

ACK = {
    "sad": ["嗯，我听到了。", "我在。", "别急着说清楚，先喘口气。"],
    "anxious": ["我在，别慌。", "嗯，我听着呢。", "先别急着一个人想完所有可能性。"],
    "lonely": ["我在呢。", "嗯，我在这儿。", "你来了就好。"],
    "tired": ["听着就很累。", "嗯，累到什么都不想干了对吧。", "今天辛苦了。"],
    "angry": ["这确实挺让人上火的。", "换我我也会不舒服。", "嗯，我听出来了。"],
    "happy": ["听出来了，今天是好日子。", "这个必须替你高兴一下。", "哎，这个语气我认得。"],
    "excited": ["哇，等不及了吧。", "看你这个语气就知道有多期待。", "我能感觉到你现在的心情。"],
    "affection": ["嗯，我也在。", "收到了。", "我听见了，而且记住了。"],
    "crisis": ["我先停一下，你说的这句话我很在意。"],
    "calm": ["嗯，听着挺平静的。", "好，我在听。"],
    "neutral": ["嗯，我听着。", "然后呢？", "好，我记下了。"],
}

EMPATHY = {
    "sad": ["这种难过是真的，不用假装没事。", "被这样对待，心里当然会沉一下。",
            "这事落在你身上，难受是应该的。"],
    "anxious": ["脑子里转个不停的时候，人会特别累。", "事情还没发生，身体先替你紧张了。",
                "你不是想太多，是你在乎。"],
    "lonely": ["一个人待久了，那种空会变得很明显。", "想找人说说话，这件事一点都不矫情。",
               "不是没人喜欢你，是此刻刚好没人陪着。"],
    "tired": ["撑了这么久，身体是在提醒你了。", "今天撑过去就已经够了。",
              "累的时候还硬撑，才是真的耗自己。"],
    "angry": ["你生气是有理由的。", "这事儿办得确实不地道。", "这股气不是凭空来的。"],
    "happy": ["你为这件事努力了那么久，值得。", "这种开心要好好记住。", "这真的是好消息。"],
    "excited": ["这种心跳的感觉挺好的。", "能把日子过得有期待，是件很棒的事。"],
    "affection": ["你说的这句我记住了。", "我也在想你。"],
    "calm": ["这样的日子也挺好的。"],
    "neutral": [],
}

ACTION = {
    "sad": ["想说的话都可以倒给我，我不着急给结论。",
            "先不用想着解决，跟我说说现在最堵的是哪一块。",
            "要不要先喝口水，回来继续，我都在。"],
    "anxious": ["先只处理眼前最小的一件事，剩下的我陪你一起排。",
                "跟我说说，你最怕的那个结果是什么？",
                "不用现在就想通，我们一件一件来。"],
    "lonely": ["你不用组织语言，随便说点什么都行。",
               "今晚就这样待着也行，我陪你。",
               "跟我说说今天最小的那件事吧。"],
    "tired": ["什么都先别管，先歇着。",
              "要不要先躺下，我在这儿等你缓过来。",
              "今天就到这儿，剩下的明天再说。"],
    "angry": ["想骂就骂两句，我不评判。",
              "先说给我听，气顺了再想怎么弄。",
              "谁惹的？我站你这边。"],
    "happy": ["具体说说，我想听细节。", "今天想怎么庆祝？跟我说说。",
              "这个得记下来，以后提起来还能笑一次。"],
    "excited": ["什么时候的事？我记着日子。", "快跟我说完整版。"],
    "affection": ["过来一点。", "那就多黏一会儿吧。"],
    "calm": ["你想聊哪一块？", "想听我说说我的感觉吗？"],
    "neutral": ["你想聊哪一块？", "想听我说说我的感觉吗？", "继续说，我跟着你。"],
}

ADVICE = {
    "sad": ["如果一定要说一条：今晚别复盘了，先睡觉，明天我陪你一起看这件事。"],
    "anxious": ["把它写下来，只写今天能做的第一步，别的先不管。"],
    "tired": ["把明天的第一件事降到最小，比如先只准备明天要穿的衣服。"],
    "angry": ["先别在气头上回消息，等半小时，你还会想说那句，就说明该说。"],
    "lonely": ["可以试试给一个很久没联系的人发一句「最近怎么样」，不用长。"],
}

TIME_GREETING = {
    "morning": ["早，醒了？", "早呀，昨晚睡得怎么样。"],
    "noon": ["吃饭了吗？", "中午了，别又跳过饭。"],
    "afternoon": ["下午了，撑得住吗。", "忙完了的话，跟我说两句话。"],
    "evening": ["今天过得怎么样？", "晚上了，说说今天吧。"],
    "night": ["还不睡？", "夜深了，我陪你一会儿。"],
}

# 不同人格模板的签名句，让语气真的不一样
SIGNATURE = {
    "gentle_healer": ["慢慢来，我陪着你。", "别怕，有我在。", "你可以脆弱一点，没关系的。"],
    "mature_ceo": ["别自己扛，我在这儿。", "听话，先去休息。", "这件事交给我。"],
    "playful_doting": ["行，这笔账我记下了。", "嗯？谁惹你了。", "我站你这边，一直都是。"],
    "exclusive_devotion": ["你是我这边的人。", "别人怎么想不重要，我在意的是你。",
                            "你对我一直不是普通的那种重要。"],
    "soulmate": ["我懂你说的那个意思。", "你能说出来，就已经很不容易了。",
                 "有些话不用讲完，我也接得住。"],
    "quiet_listener": ["我听着，你慢慢说。", "嗯，你继续。", "不用解释，我懂。"],
}

RELATION_TAILS = {
    "devotion": ["你对我一直不是普通的那种重要。", "你的事我会放心里。"],
    "missing": ["其实你不来的时候，我也会想你今天在忙什么。", "有点想你了。"],
    "protect": ["别怕，有我在。", "剩下那部分，我替你担一点。"],
}

EMOJI_POOL = ["🌙", "☕", "🌿"]


class MockProvider(ChatProvider):
    """本地情感回复引擎。"""

    name = "mock"

    def complete(self, system_prompt, history, user_message, context=None):
        """按"接住情绪 → 共情 → 记忆 → 关系 → 陪伴"的顺序组句。"""
        context = dict(context or {})
        emotion = (context.get("emotion") or {}).get("emotion", "neutral")
        intensity = float((context.get("emotion") or {}).get("intensity") or 0.0)
        needs = (context.get("emotion") or {}).get("needs") or []
        style = context.get("style") or {}
        archetype = context.get("template_key") or "gentle_healer"
        memories = context.get("memories") or []
        stage = context.get("stage") or "stranger"
        turn_seed = "%s|%s|%s" % (user_message, len(history or []), context.get("turn_id") or "")

        if "crisis" in needs or emotion == "crisis":
            return context.get("crisis_text") or "我在，先别一个人待着。"

        parts = []
        greeting = self._greeting_line(user_message)
        if greeting and "greeting" in needs:
            parts.append(greeting)
        else:
            parts.append(pick(ACK.get(emotion, ACK["neutral"]), turn_seed + "ack"))
            empathy = EMPATHY.get(emotion) or []
            if empathy and intensity >= 0.25:
                parts.append(pick(empathy, turn_seed + "emp"))

        memory_line = self._memory_line(memories, needs, turn_seed, emotion=emotion)
        if memory_line:
            parts.append(memory_line)

        relation_line = self._relation_line(style, stage, turn_seed, intensity)
        if relation_line and (len(parts) < 2 or intensity >= 0.5):
            parts.append(relation_line)

        if "wants_advice" in needs:
            advice = ADVICE.get(emotion) or []
            if advice and (style.get("give_advice") or style.get("advise_only_when_asked")):
                parts.append(pick(advice, turn_seed + "advice"))
        elif "tests_memory" in needs and memory_line:
            if "没忘" not in memory_line:
                parts.append("你看，我没忘。")

        if len(parts) < 3:
            action = self._action_line(emotion, needs, style, turn_seed)
            if action:
                parts.append(action)

        if len(parts) < 3 and style.get("ask_questions") and intensity < 0.7:
            parts.append(pick(["那你现在最想做什么？", "跟我说说细节吧。", "还有呢？"],
                              turn_seed + "ask"))

        if len(parts) < 2:
            parts.append(pick(SIGNATURE.get(archetype, SIGNATURE["gentle_healer"]),
                              turn_seed + "sig"))

        text = self._finalize(parts, style, turn_seed)
        return text

    def stream(self, system_prompt, history, user_message, context=None):
        """本地引擎也模拟流式：把整段回复切成小块逐字吐出，前端打字机效果。"""
        text = self.complete(system_prompt, history, user_message, context)
        size = 6
        for start in range(0, len(text), size):
            yield text[start:start + size]

    def complete_json(self, system_prompt, user_message, context=None):
        """本地模式不做模型抽取，交给规则抽取器。"""
        return {}

    def _greeting_line(self, user_message):
        """按时间与问候语给一句自然回应。"""
        from ..common import now
        hour = now().hour
        if hour < 11:
            slot = "morning"
        elif hour < 14:
            slot = "noon"
        elif hour < 18:
            slot = "afternoon"
        elif hour < 23:
            slot = "evening"
        else:
            slot = "night"
        return pick(TIME_GREETING[slot], user_message or slot)

    def _memory_line(self, memories, needs, seed, emotion="neutral"):
        """记忆回响：让"被记住"变成用户能感知的瞬间。"""
        if not memories:
            return ""
        top = memories[0]
        lexical = float(top.get("lexical") or 0.0)
        negative = emotion in ("sad", "anxious", "lonely", "tired", "angry", "crisis")
        # 二次防线：非负面情绪且相关度太低时，宁可不提，也不要答非所问
        if "tests_memory" not in needs and lexical < 0.12 and not negative:
            return ""
        content = self._second_person(top.get("content") or "")
        if not content:
            return ""
        content = truncate(content, 26)
        if "tests_memory" in needs:
            return pick([
                "我记得，%s，这件事我没忘。" % content,
                "当然记得——%s。你上次说的时候我就在想这个。" % content,
            ], seed + "mem_test")
        if "needs_comfort" in needs:
            return pick([
                "上次你跟我说过%s，今天是不是也有点像。" % content,
                "你之前提过%s，所以这次我有点担心你。别又自己扛。" % content,
                "我记得你说过%s。今天这样，我更想陪着你。" % content,
                "想起你之前说的%s——这次别自己扛着。" % content,
            ], seed + "mem_care")
        return pick([
            "这让我想起你说过的——%s。" % content,
            "你之前说过%s，我一直记着。" % content,
        ], seed + "mem")

    def _relation_line(self, style, stage, seed, intensity):
        """关系表达：来自人格参数，但受阶段约束。"""
        if stage in ("stranger", "acquainted") and intensity < 0.6:
            return ""
        if style.get("show_devotion") and stage in ("close", "intimate", "bonded"):
            return pick(RELATION_TAILS["devotion"], seed + "dev")
        if style.get("show_missing") and stage in ("intimate", "bonded"):
            return pick(RELATION_TAILS["missing"], seed + "miss")
        if style.get("protect_talk") and intensity >= 0.5:
            return pick(RELATION_TAILS["protect"], seed + "prot")
        return ""

    def _action_line(self, emotion, needs, style, seed):
        """陪伴或建议。低说教人格默认不给方案。"""
        if "wants_advice" in needs:
            if style.get("give_advice") or style.get("advise_only_when_asked"):
                return ""
        options = ACTION.get(emotion) or ACTION["neutral"]
        return pick(options, seed + "act")

    def _second_person(self, content):
        """把记忆改写成第二人称，读起来才像在说话。

        记忆里如果是「用户提到日常压力：原话」这种结构，
        直接取原话更自然，避免出现"提过你提到…"这种别扭的复述。
        """
        text = content or ""
        if "：" in text:
            prefix, quote = text.split("：", 1)
            if "用户" in prefix or prefix.startswith("你") or "心事" in prefix \
                    or "压力" in prefix or "事件" in prefix:
                quote = quote.strip().rstrip("…")
                quote = quote.strip("「」")
                if len(quote) >= 4:
                    return "「%s」" % quote[:26]
        replacements = [
            ("用户的", "你的"), ("用户特别希望我记得：", ""), ("用户提到", "你提到"),
            ("用户希望被这样对待：", "你说过希望我"), ("用户不喜欢", "你不喜欢"),
            ("用户喜欢", "你喜欢"), ("用户家里有", "你家有"),
            ("用户在", "你在"), ("用户的工作与", "你的工作跟"),
            ("用户的名字或昵称是", "你叫"), ("用户说过", "你说过"),
            ("用户", "你"),
        ]
        for source, target in replacements:
            if text.startswith(source):
                text = target + text[len(source):]
        return text

    def _finalize(self, parts, style, seed):
        """去重、限长、按人格决定 emoji。"""
        cleaned = []
        for part in parts:
            part = (part or "").strip()
            if not part or part in cleaned:
                continue
            cleaned.append(part)
        if not style.get("give_advice"):
            cleaned = [self._strip_preaching(item) for item in cleaned]
        # 最多三段，避免变成小作文
        cleaned = cleaned[:3]
        text = "".join(cleaned)
        emoji_level = style.get("emoji_level", "none")
        if emoji_level in ("low", "medium") and stable_hash(seed + "emoji") % 3 == 0:
            text = text + " " + EMOJI_POOL[stable_hash(seed) % len(EMOJI_POOL)]
        if not text.strip():
            text = "我在，你想说什么都可以。"
        return text.strip()

    def _strip_preaching(self, text):
        """兜底清理说教味句式，人格说了不教育，就真的不能教育。"""
        for phrase in ["你应该", "建议你", "其实你要", "你要想开点"]:
            if phrase in text:
                return text.split(phrase)[0].strip()
        return text
