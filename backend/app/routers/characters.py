# -*- coding: utf-8 -*-
"""AI 角色相关接口。"""

from fastapi import APIRouter, Response

from ..avatar import generate_svg
from ..common import new_id, now_iso
from ..db import as_json, dump_json, execute, insert, query_all, query_one
from ..engine import EngineError
from ..memory import memory_stats
from ..onboarding import apply_answer, next_question, progress
from ..persona import (ARCHETYPES, PARAMETER_DEFS, RELATION_TYPES, STAGES,
                       default_persona, normalize_persona, persona_tags,
                       stage_label)
from ..relationship import relationship_view
from ..schemas import CharacterCreate, CharacterUpdate, InterviewRequest

router = APIRouter(prefix="/api/characters", tags=["characters"])


def character_view(character, with_relationship=True):
    """对外返回的角色结构。"""
    view = {
        "id": character["id"],
        "user_id": character["user_id"],
        "name": character["name"],
        "relation_type": character.get("relation_type"),
        "relation_label": _relation_label(character.get("relation_type")),
        "template_key": character.get("template_key"),
        "template_label": _template_label(character.get("template_key")),
        "appearance": as_json(character.get("appearance"), {}),
        "persona": normalize_persona(as_json(character.get("persona"), {})),
        "persona_tags": persona_tags(as_json(character.get("persona"), {})),
        "voice": as_json(character.get("voice"), {}),
        "avatar_url": "/api/characters/%s/avatar.svg" % character["id"],
        "created_at": character.get("created_at"),
        "memory": memory_stats(character["id"]),
    }
    if with_relationship:
        view["relationship"] = relationship_view(character)
    return view


def _relation_label(key):
    for item in RELATION_TYPES:
        if item["key"] == key:
            return item["label"]
    return "男朋友"


def _template_label(key):
    for item in ARCHETYPES:
        if item["key"] == key:
            return item["label"]
    return "自定义"


@router.post("")
def create_character(payload: CharacterCreate):
    """创建专属 AI 男友。"""
    user = query_one("SELECT * FROM users WHERE id=?", (payload.user_id,))
    if not user:
        raise EngineError("user_not_found", "用户不存在", 404)
    if payload.relation_type not in [item["key"] for item in RELATION_TYPES]:
        raise EngineError("bad_relation_type", "关系类型不支持", 400)

    base = default_persona(payload.template_key)
    persona = dict(base)
    for key, value in (payload.persona or {}).items():
        if key in persona:
            persona[key] = value
    persona = normalize_persona(persona)

    character_id = new_id("char")
    insert("characters", {
        "id": character_id,
        "user_id": payload.user_id,
        "name": payload.name.strip(),
        "relation_type": payload.relation_type,
        "template_key": payload.template_key,
        "appearance": dump_json(payload.appearance or {}),
        "persona": dump_json(persona),
        "voice": dump_json(payload.voice or {}),
        "intimacy": 0.0,
        "stage": STAGES[0]["key"],
        "created_at": now_iso(),
    })
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    view = character_view(character)
    profile = as_json(user.get("profile"), {})
    view["interview"] = {
        "progress": progress(profile),
        "next_question": next_question(profile),
    }
    return view


@router.get("")
def list_characters(user_id: str):
    """某个用户的角色列表。"""
    rows = query_all(
        "SELECT * FROM characters WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    )
    return {"items": [character_view(row) for row in rows]}


@router.get("/{character_id}")
def get_character(character_id: str):
    """角色详情。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    return character_view(character)


@router.patch("/{character_id}")
def update_character(character_id: str, payload: CharacterUpdate):
    """调整人格参数、外观或名字。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    updates = {}
    if payload.name:
        updates["name"] = payload.name.strip()
    if payload.appearance is not None:
        updates["appearance"] = dump_json(payload.appearance)
    if payload.persona is not None:
        merged = normalize_persona(as_json(character.get("persona"), {}))
        for key, value in payload.persona.items():
            if key in merged:
                merged[key] = value
        updates["persona"] = dump_json(normalize_persona(merged))
    if payload.voice is not None:
        updates["voice"] = dump_json(payload.voice)
    if updates:
        columns = ",".join(["%s=?" % key for key in updates])
        execute("UPDATE characters SET %s WHERE id=?" % columns,
                tuple(updates.values()) + (character_id,))
    return character_view(query_one("SELECT * FROM characters WHERE id=?", (character_id,)))


@router.get("/{character_id}/avatar.svg")
def get_avatar(character_id: str):
    """程序化生成的头像。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    svg = generate_svg(character.get("name") or "他",
                       as_json(character.get("appearance"), {}),
                       seed=character_id)
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.post("/{character_id}/interview")
def answer_interview(character_id: str, payload: InterviewRequest):
    """回答一个访谈问题，实时改人格。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    user = query_one("SELECT * FROM users WHERE id=?", (payload.user_id,))
    if not user:
        raise EngineError("user_not_found", "用户不存在", 404)

    persona = as_json(character.get("persona"), {})
    profile = as_json(user.get("profile"), {})
    persona, profile, option = apply_answer(persona, profile, payload.question_key, payload.option_key)
    if option is None:
        raise EngineError("bad_option", "这个选项不存在", 400)

    execute("UPDATE characters SET persona=? WHERE id=?",
            (dump_json(normalize_persona(persona)), character_id))
    execute("UPDATE users SET profile=? WHERE id=?", (dump_json(profile), payload.user_id))

    # 访谈结论也写成记忆，之后他"记得你为什么这样对他"
    from ..memory.store import add_memory
    add_memory(
        character_id, "preference",
        "用户在人格访谈里说过：%s" % option["label"],
        key="interview_" + payload.question_key,
        importance=0.85,
        confidence=1.0,
        tags=["人格设定"],
    )

    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    view = character_view(character)
    view["interview"] = {
        "progress": progress(profile),
        "next_question": next_question(profile),
        "applied": option,
    }
    return view


@router.get("/{character_id}/relationship")
def get_relationship(character_id: str):
    """关系状态：亲密度、阶段、里程碑。"""
    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    if not character:
        raise EngineError("character_not_found", "角色不存在", 404)
    view = relationship_view(character)
    view["stage_label"] = stage_label(view["stage"])
    return view
