"""模型适配层。"""

from .base import ChatProvider, LLMError
from .factory import get_provider
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider

__all__ = ["ChatProvider", "LLMError", "MockProvider", "OpenAICompatProvider", "get_provider"]
