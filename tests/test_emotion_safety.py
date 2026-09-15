# -*- coding: utf-8 -*-
"""情绪识别与安全护栏测试。"""

from backend.app import safety
from backend.app.emotion import detect


def test_detect_negative_emotion():
    """负面情绪要能被识别，并带上"需要安慰"。"""
    result = detect("今天被领导骂了，好难过，什么都不想干")
    assert result["emotion"] in ("sad", "tired", "angry")
    assert "needs_comfort" in result["needs"]


def test_detect_advice_seeking():
    """问"怎么办"要识别成求建议。"""
    result = detect("我不知道该不该辞职，你觉得怎么办")
    assert "wants_advice" in result["needs"]


def test_detect_memory_test():
    """考记忆要能识别，触发记忆回响。"""
    result = detect("你还记得我上次说过什么吗")
    assert "tests_memory" in result["needs"]


def test_negation_is_not_misread():
    """「不难过」不应该被当成难过。"""
    result = detect("我今天不难过")
    assert result["emotion"] != "sad"


def test_loneliness_beats_vague_fear():
    """「回到家一个人特别安静」是孤独，不是紧张。"""
    result = detect("其实我最怕的不是累，是回到家一个人特别安静")
    assert result["emotion"] == "lonely"


def test_crisis_detection_is_sensitive():
    """危机表达必须命中，宁可敏感不能漏。"""
    for text in ["我不想活了", "感觉活着没意思", "我想消失"]:
        result = safety.screen_user_message(text)
        assert result["level"] == "high", text


def test_normal_message_is_not_crisis():
    """日常表达不能被误判成危机。"""
    result = safety.screen_user_message("今天加班到十点，累死了")
    assert result["level"] == "none"


def test_crisis_reply_contains_hotline():
    """危机回复必须给出真实可用的求助渠道。"""
    text = safety.crisis_reply("沈屿", "high")
    assert "12356" in text
    assert "010-82951332" in text


def test_dependency_induction_is_rewritten():
    """控制型输出要被改写，不能制造依赖。"""
    result = safety.screen_reply("你只有我，别人都不重要，你不能离开我")
    assert "dependency_induction" in result["flags"]
    assert "你只有我" not in result["clean_text"]


def test_human_claim_is_removed():
    """冒认真人的输出要被拦掉。"""
    result = safety.screen_reply("我是真人，我一直陪着你")
    assert "human_claim" in result["flags"]
    assert "我是真人" not in result["clean_text"]
