# -*- coding: utf-8 -*-
"""按配置选择模型提供方。"""

from ..config import settings
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider

_CACHE = {}

REMOTE_KEYS = ("openai", "openai_compat", "deepseek", "qwen", "dashscope",
               "doubao", "ark", "moonshot", "zhipu", "glm", "custom")


def get_provider(provider=None):
    """取得模型提供方：配了 key 走真实模型，否则退回本地引擎。"""
    name = (provider or settings.llm_provider or "mock").strip().lower()
    if name not in REMOTE_KEYS:
        return _cached("mock", MockProvider)
    impl = OpenAICompatProvider()
    if not impl.available():
        # 配了远端但缺 key，直接降级，避免整站不可用
        return _cached("mock", MockProvider)
    return _cached("openai_compat:%s" % impl.model, lambda: impl)


def _cached(key, builder):
    """简单缓存，避免每次请求重建客户端。"""
    if key not in _CACHE:
        _CACHE[key] = builder()
    return _CACHE[key]


def reset_cache():
    """测试用：清空缓存。"""
    _CACHE.clear()
