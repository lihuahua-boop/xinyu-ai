# -*- coding: utf-8 -*-
"""记忆系统测试：写入、去重、召回、遗忘。"""

from backend.app.emotion import detect
from backend.app.memory import extract_memories, list_memories, recall
from backend.app.memory.extractor import extract_profile_updates
from backend.app.memory.store import add_memory, deactivate_memory, memory_stats


def test_extract_preference():
    """喜欢/不喜欢要被抓成偏好记忆。"""
    result = extract_memories("我特别喜欢喝美式咖啡，但是很讨厌冷处理",
                              detect("我特别喜欢喝美式咖啡，但是很讨厌冷处理"))
    contents = " ".join(item["content"] for item in result)
    assert "美式" in contents
    assert any(item["category"] == "preference" for item in result)


def test_extract_basic_info():
    """生日、城市这类基础信息要被记住。"""
    result = extract_memories("我生日是3月14日，我现在在上海工作", detect("我生日是3月14日"))
    contents = " ".join(item["content"] for item in result)
    assert "3" in contents and "月" in contents
    assert any(item["category"] == "basic" for item in result)


def test_extract_expectation():
    """用户对陪伴方式的期待必须被记住。"""
    result = extract_memories("我希望你别讲大道理", detect("我希望你别讲大道理"))
    assert any("希望" in item["content"] for item in result)
    assert result[0]["importance"] >= 0.85


def test_extract_explicit_remember_is_high_importance():
    """用户明确要求记住的事，重要度要拉满。"""
    result = extract_memories("记住我下周三要面试", detect("记住我下周三要面试"))
    assert result
    assert max(item["importance"] for item in result) >= 0.9


def test_one_sentence_does_not_become_two_memories():
    """同一句话里已经有明确事实时，不要再记一条泛泛的心事。"""
    text = "我特别喜欢喝美式咖啡，每天早上都要一杯"
    result = extract_memories(text, detect(text))
    assert len(result) == 1
    assert result[0]["category"] == "preference"


def test_event_memory_reads_naturally():
    """经历类记忆的措辞要像人话，不能是机器复述。"""
    text = "今天跟同事吵架了，特别难过，觉得自己很没用"
    result = extract_memories(text, detect(text))
    assert result
    content = result[0]["content"]
    assert not content.startswith("用户提到")
    assert "用户" in content


def test_profile_updates():
    """结构化画像要跟着更新。"""
    profile = extract_profile_updates("我喜欢猫和咖啡，我住在杭州", {})
    assert "猫" in " ".join(profile["interests"])
    assert profile["city"] == "杭州"


def test_add_and_dedupe(client, user, character):
    """重复写入同一件事应该合并而不是堆叠。"""
    character_id = character["id"]
    first = add_memory(character_id, "preference", "用户喜欢猫", key="like")
    second = add_memory(character_id, "preference", "用户喜欢猫", key="like")
    assert first == second
    items = [item for item in list_memories(character_id, "preference")
             if item["key"] == "like"]
    assert len(items) == 1


def test_recall_matches_query(client, user, character):
    """问到相关话题时，要能想起相关记忆。"""
    character_id = character["id"]
    add_memory(character_id, "emotion", "用户因为工作压力失眠过", importance=0.9)
    add_memory(character_id, "preference", "用户喜欢猫", importance=0.6)
    results = recall(character_id, "我最近又失眠了，工作好烦", detect("我最近又失眠了，工作好烦"))
    assert results
    assert any("失眠" in item["content"] for item in results)
    assert results[0]["score"] > 0


def test_recall_marks_usage(client, user, character):
    """召回后要打点，避免下次还念叨同一件事。"""
    character_id = character["id"]
    memory_id = add_memory(character_id, "emotion", "用户面试前很紧张")
    recall(character_id, "明天要面试了", detect("明天要面试了"))
    items = [item for item in list_memories(character_id) if item["id"] == memory_id]
    assert items[0]["recall_count"] >= 1


def test_forget(client, user, character):
    """用户有权让他忘掉某件事。"""
    character_id = character["id"]
    memory_id = add_memory(character_id, "emotion", "用户提过一件不想被记住的事")
    deactivate_memory(memory_id)
    assert not [item for item in list_memories(character_id) if item["id"] == memory_id]
    assert memory_stats(character_id)["total"] >= 0


def test_irrelevant_fact_is_not_recalled(client, user, character):
    """聊情绪时不该突然提起生日这种不相关的事实。"""
    character_id = character["id"]
    add_memory(character_id, "basic", "用户的生日是 3 月 14 日", importance=0.9)
    text = "今天加班到十点，好累，什么都不想干"
    results = recall(character_id, text, detect(text))
    assert not [item for item in results if "生日" in item["content"]]


def test_relevant_fact_is_still_recalled(client, user, character):
    """但用户主动问到相关事实时，必须想起来。"""
    character_id = character["id"]
    add_memory(character_id, "basic", "用户的生日是 3 月 14 日", importance=0.9)
    results = recall(character_id, "你还记得我生日是几号吗", detect("你还记得我生日是几号吗"))
    assert [item for item in results if "生日" in item["content"]]
