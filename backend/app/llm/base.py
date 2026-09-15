# -*- coding: utf-8 -*-
"""模型适配层的统一接口。"""


class LLMError(Exception):
    """模型调用失败。"""


class ChatProvider(object):
    """所有模型提供方都要实现这两个方法。"""

    name = "base"

    def complete(self, system_prompt, history, user_message, context=None):
        """生成一条回复。

        system_prompt：人格编译后的系统提示
        history：最近的对话历史 [{'role': 'user'|'assistant', 'content': str}]
        user_message：本轮用户消息
        context：结构化上下文（情绪、记忆、关系），本地引擎靠它拼回复
        """
        raise NotImplementedError

    def stream(self, system_prompt, history, user_message, context=None):
        """流式生成：返回一个可迭代的字符串块生成器。

        默认实现退化为一次返回整段，方便非流式 provider 复用。
        """
        yield self.complete(system_prompt, history, user_message, context)

    def complete_json(self, system_prompt, user_message, context=None):
        """要求模型输出结构化 JSON，用于记忆抽取等任务。"""
        raise NotImplementedError

    def available(self):
        """是否可用。"""
        return True
