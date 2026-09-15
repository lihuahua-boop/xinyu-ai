# -*- coding: utf-8 -*-
"""请求与响应模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """注册/进入。"""

    nickname: str = Field("", max_length=32)
    age_verified: bool = False


class CharacterCreate(BaseModel):
    """创建专属 AI 男友。"""

    user_id: str
    name: str = Field(..., min_length=1, max_length=16)
    relation_type: str = "boyfriend"
    template_key: str = "gentle_healer"
    appearance: Dict[str, Any] = Field(default_factory=dict)
    persona: Dict[str, Any] = Field(default_factory=dict)
    voice: Dict[str, Any] = Field(default_factory=dict)


class CharacterUpdate(BaseModel):
    """调整角色设定。"""

    name: Optional[str] = None
    appearance: Optional[Dict[str, Any]] = None
    persona: Optional[Dict[str, Any]] = None
    voice: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """发一条消息。"""

    user_id: str
    text: str = Field(..., max_length=2000)


class InterviewRequest(BaseModel):
    """回答人格访谈的一个问题。"""

    user_id: str
    question_key: str
    option_key: str


class MemoryCreate(BaseModel):
    """手动补一条记忆。"""

    category: str = "basic"
    content: str = Field(..., max_length=300)
    importance: float = 0.7


class ProfileUpdate(BaseModel):
    """更新用户画像。"""

    display_name: Optional[str] = None
    call_me: Optional[str] = None
    birthday: Optional[str] = None
    age_verified: Optional[bool] = None


class ApiError(BaseModel):
    """错误结构。"""

    code: str
    message: str
