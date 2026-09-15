# -*- coding: utf-8 -*-
"""人格系统测试。"""

from backend.app.persona import (ARCHETYPES, compile_persona, default_persona,
                                 next_stage, normalize_persona, persona_tags,
                                 stage_progress, style_flags)


def test_normalize_fills_all_params():
    """参数缺失时要补全，越界要收敛。"""
    persona = normalize_persona({"gentleness": 120, "humor": -5})
    assert persona["gentleness"] == 100
    assert persona["humor"] == 0
    assert len(persona) == len(normalize_persona({}))


def test_all_templates_are_complete():
    """每套模板都要有完整的参数，否则会渲染出默认值污染人格。"""
    reference = set(default_persona("gentle_healer").keys())
    for archetype in ARCHETYPES:
        assert set(default_persona(archetype["key"]).keys()) == reference


def test_tags_reflect_params():
    """低说教、高温柔要能被翻译成人话标签。"""
    tags = persona_tags({"gentleness": 95, "preachiness": 10, "humor": 85})
    assert "高共情" in tags
    assert "低说教" in tags
    assert "会调侃" in tags


def test_compile_persona_contains_key_sections():
    """系统提示必须包含称呼、行为准则与底线。"""
    persona = default_persona("quiet_listener")
    prompt = compile_persona(persona, "沈屿", "boyfriend", "close", 55.0,
                             user_nickname="小满", days_together=12)
    assert "沈屿" in prompt
    assert "小满" in prompt
    assert "不要说教" in prompt
    assert "12356" in prompt
    assert "关系状态" in prompt


def test_low_preaching_disables_advice_by_default():
    """低说教人格不能主动给方案。"""
    flags = style_flags({"preachiness": 10, "gentleness": 90}, "close")
    assert flags["advise_only_when_asked"] is True


def test_stage_progression():
    """阶段阈值与下一阶段提示要一致。"""
    assert next_stage(0) == "stranger"
    assert next_stage(50) == "close"
    assert next_stage(95) == "bonded"
    progress = stage_progress(30)
    assert progress["next_stage"] == "close"
    assert progress["remaining"] > 0
