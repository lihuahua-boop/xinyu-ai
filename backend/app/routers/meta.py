# -*- coding: utf-8 -*-
"""元数据接口：把可选项交给前端，避免前端硬编码。"""

from fastapi import APIRouter

from ..avatar import appearance_options
from ..config import settings
from ..emotion import EMOTION_LABELS
from ..onboarding import INTERVIEW_QUESTIONS
from ..persona import ARCHETYPES, PARAMETER_DEFS, RELATION_TYPES, STAGES

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    """健康检查。"""
    return {"status": "ok", "app": settings.app_name, "version": settings.version}


@router.get("/meta/config")
def config():
    """前端启动时需要的配置。"""
    return settings.public()


@router.get("/meta/templates")
def templates():
    """人格模板。"""
    return {"items": ARCHETYPES}


@router.get("/meta/relation-types")
def relation_types():
    """关系类型。"""
    return {"items": RELATION_TYPES}


@router.get("/meta/persona-params")
def persona_params():
    """人格参数定义。"""
    return {"items": [
        {"key": key, "label": label, "low": low, "high": high}
        for key, label, low, high in PARAMETER_DEFS
    ]}


@router.get("/meta/stages")
def stages():
    """关系阶段。"""
    return {"items": STAGES}


@router.get("/meta/interview")
def interview():
    """人格访谈问题。"""
    return {"items": INTERVIEW_QUESTIONS}


@router.get("/meta/appearance")
def appearance():
    """外观选项。"""
    return appearance_options()


@router.get("/meta/emotions")
def emotions():
    """情绪标签。"""
    return {"items": [{"key": key, "label": label} for key, label in EMOTION_LABELS.items()]}
