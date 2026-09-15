# -*- coding: utf-8 -*-
"""关系成长测试。"""

from backend.app.emotion import detect
from backend.app.relationship import (DAILY_GAIN_CAP, apply_gain, days_together,
                                      intimacy_gain, relationship_view)


def test_deep_talk_gains_more_than_small_talk():
    """说心里话比敷衍一句涨得多。"""
    deep = intimacy_gain("今天真的很难过，被领导当众说了，觉得自己特别没用",
                         detect("今天真的很难过，被领导当众说了，觉得自己特别没用"))
    shallow = intimacy_gain("嗯", detect("嗯"))
    assert deep > shallow


def test_memory_bonus():
    """产生记忆会额外加成。"""
    base = intimacy_gain("我喜欢猫", detect("我喜欢猫"))
    with_memory = intimacy_gain("我喜欢猫", detect("我喜欢猫"), wrote_memory=True)
    assert with_memory > base


def test_daily_cap(client, user, character):
    """一天之内关系不能刷满。"""
    character_row = dict(character)
    total = 0.0
    for _ in range(20):
        info = apply_gain(character_row, 5.0)
        total += info["intimacy_gain"]
        character_row["intimacy"] = info["intimacy"]
        character_row["stage"] = info["stage"]
    assert total <= DAILY_GAIN_CAP + 0.001


def test_intimacy_never_exceeds_100():
    """上限保护。"""
    info = apply_gain({"id": "char_test", "intimacy": 99.9, "stage": "bonded"}, 10.0)
    assert info["intimacy"] <= 100.0


def test_relationship_view(client, user, character):
    """关系视图要包含阶段与里程碑字段。"""
    view = relationship_view(character)
    assert view["stage"] == "stranger"
    assert view["days_together"] >= 1
    assert "milestones" in view
