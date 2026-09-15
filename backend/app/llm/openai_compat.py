# -*- coding: utf-8 -*-
"""OpenAI 兼容接口适配器。

覆盖：DeepSeek、通义千问（兼容模式）、豆包（方舟）、Moonshot、智谱、OpenAI。
只要改 base_url / model 就能切换，业务代码不用动。
"""

import json

import requests

from ..config import settings
from .base import ChatProvider, LLMError


class OpenAICompatProvider(ChatProvider):
    """标准 /chat/completions 协议。"""

    name = "openai_compat"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or settings.llm_base_url or "").rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout

    def available(self):
        """有 key 有地址才算可用。"""
        return bool(self.base_url and self.api_key)

    def complete(self, system_prompt, history, user_message, context=None, json_mode=False):
        """调用模型生成回复。"""
        if not self.available():
            raise LLMError("缺少 XINYU_LLM_BASE_URL 或 XINYU_LLM_API_KEY")

        payload = self._payload(system_prompt, history, user_message, json_mode)

        data = self._post(payload)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("模型返回结构异常：%s" % str(data)[:200])

    def stream(self, system_prompt, history, user_message, context=None, json_mode=False):
        """流式生成，逐块返回增量文本。"""
        if not self.available():
            raise LLMError("缺少 XINYU_LLM_BASE_URL 或 XINYU_LLM_API_KEY")

        payload = self._payload(system_prompt, history, user_message, json_mode)
        payload["stream"] = True
        url = self.base_url + "/chat/completions"
        headers = {
            "Authorization": "Bearer %s" % self.api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        try:
            response = requests.post(
                url, headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                stream=True, timeout=self.timeout)
        except Exception as error:
            raise LLMError("模型调用失败：%s" % error)
        if response.status_code >= 400:
            raise LLMError("模型接口返回 %s：%s" % (response.status_code, response.text[:300]))
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if delta:
                yield delta

    def complete_json(self, system_prompt, user_message, context=None):
        """要求结构化输出，解析失败返回空字典由上层降级。"""
        try:
            raw = self.complete(system_prompt, [], user_message, context, json_mode=True)
        except LLMError:
            return {}
        return _loads(raw)

    def _post(self, payload):
        """带一次重试的请求。"""
        url = self.base_url + "/chat/completions"
        headers = {
            "Authorization": "Bearer %s" % self.api_key,
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(2):
            try:
                response = requests.post(
                    url, headers=headers,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=self.timeout)
                if response.status_code >= 400:
                    raise LLMError("模型接口返回 %s：%s" % (response.status_code, response.text[:300]))
                return response.json()
            except LLMError:
                raise
            except Exception as error:
                last_error = error
                if attempt == 1:
                    break
        raise LLMError("模型调用失败：%s" % last_error)

    def _payload(self, system_prompt, history, user_message, json_mode):
        """组装 chat/completions 请求体。"""
        messages = [{"role": "system", "content": system_prompt}]
        for item in (history or [])[-settings.recent_turns:]:
            role = item.get("role") if item.get("role") in ("user", "assistant") else "user"
            messages.append({"role": role, "content": item.get("content") or ""})
        messages.append({"role": "user", "content": user_message or ""})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload


def _loads(raw):
    """从模型输出里稳健地取出 JSON。"""
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        return json.loads(text)
    except ValueError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                return {}
        return {}
