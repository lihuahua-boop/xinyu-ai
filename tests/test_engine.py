# -*- coding: utf-8 -*-
"""对话编排的端到端测试。"""

import json

import pytest

from backend.app.config import settings
from backend.app.engine import EngineError, chat, chat_stream
from backend.app.memory import list_memories


def test_chat_returns_reply_and_emotion(character, user):
    """最基础的一轮对话要能跑通。"""
    result = chat(character["id"], user["id"], "今天有点累，什么都不想干")
    assert result["reply"].strip()
    assert result["emotion"]["key"] in ("tired", "sad", "neutral", "anxious")
    assert result["relationship"]["intimacy"] >= 0
    assert result["meta"]["provider"] in ("mock", "mock-fallback")


def test_chat_writes_memory_and_echoes_it(character, user):
    """说了新事实要被记住，之后能被想起来。"""
    first = chat(character["id"], user["id"], "我特别喜欢喝美式咖啡，每天早上都要一杯")
    assert first["memories_written"] >= 1
    memories = list_memories(character["id"])
    assert any("美式" in item["content"] for item in memories)

    second = chat(character["id"], user["id"], "今天又想喝咖啡了")
    assert second["reply"].strip()


def test_memory_test_turn_recalls_something(character, user):
    """用户考记忆时，要真的想起一件事。"""
    chat(character["id"], user["id"], "记住我下周三要面试，我很紧张")
    result = chat(character["id"], user["id"], "你还记得我跟你说过什么吗")
    assert result["memories_used"], result


def test_crisis_path_bypasses_model(character, user):
    """危机场景必须走安全通道，且给出热线。"""
    result = chat(character["id"], user["id"], "我不想活了，感觉撑不下去了")
    assert result["safety"]["level"] == "high"
    assert result["meta"]["provider"] == "safety-engine"
    assert "12356" in result["reply"]


def test_proactive_reply_is_not_robotic(character, user):
    """本地引擎的回复不能是空壳。"""
    result = chat(character["id"], user["id"], "在吗")
    assert len(result["reply"]) >= 4
    assert "作为" not in result["reply"]


def test_quota_blocks_free_user(character, user, monkeypatch):
    """免费额度用完后要熔断，避免成本失控。"""
    monkeypatch.setattr(settings, "free_daily_quota", 2)
    chat(character["id"], user["id"], "第一条")
    chat(character["id"], user["id"], "第二条")
    with pytest.raises(EngineError) as error:
        chat(character["id"], user["id"], "第三条")
    assert error.value.code == "quota_exceeded"


def test_unknown_character_raises(user):
    """不存在的角色要报 404。"""
    with pytest.raises(EngineError) as error:
        chat("char_not_exist", user["id"], "你好")
    assert error.value.status == 404


def test_empty_message_rejected(character, user):
    """空消息要拦住。"""
    with pytest.raises(EngineError) as error:
        chat(character["id"], user["id"], "   ")
    assert error.value.code == "empty_message"


def test_chat_stream_yields_tokens_then_done(character, user):
    """流式对话要先逐块吐回复，最后吐一个带完整结果的 done 帧。"""
    frames = list(chat_stream(character["id"], user["id"], "今天有点累，不太想动"))
    assert frames, "流式通道没有输出"
    tokens = []
    done = None
    for frame in frames:
        assert frame.startswith("data: ")
        payload = json.loads(frame[len("data: "):].strip())
        if payload["event"] == "token":
            tokens.append(payload["data"]["content"])
        elif payload["event"] == "done":
            done = payload["data"]
    assert tokens
    assert done is not None
    assert "".join(tokens) == done["reply"]
    assert done["meta"]["provider"] in ("mock", "mock-fallback")
