# -*- coding: utf-8 -*-
"""用户相关接口。"""

from fastapi import APIRouter

from ..common import new_id, now_iso
from ..config import settings
from ..db import as_json, dump_json, execute, insert, query_one
from ..engine import EngineError
from ..schemas import ProfileUpdate, UserCreate

router = APIRouter(prefix="/api/users", tags=["users"])


def user_view(user):
    """对外返回的用户结构。"""
    return {
        "id": user["id"],
        "nickname": user.get("nickname") or "",
        "age_verified": bool(user.get("age_verified")),
        "membership": user.get("membership") or "free",
        "profile": as_json(user.get("profile"), {}),
        "daily_quota": settings.free_daily_quota,
        "created_at": user.get("created_at"),
        "last_active_at": user.get("last_active_at"),
    }


@router.post("")
def create_user(payload: UserCreate):
    """创建用户（MVP 免登录，用本地 ID 标识）。"""
    user_id = new_id("user")
    insert("users", {
        "id": user_id,
        "nickname": payload.nickname or "",
        "age_verified": 1 if payload.age_verified else 0,
        "membership": "free",
        "profile": dump_json({}),
        "created_at": now_iso(),
        "last_active_at": now_iso(),
    })
    return user_view(query_one("SELECT * FROM users WHERE id=?", (user_id,)))


@router.get("/{user_id}")
def get_user(user_id: str):
    """取用户信息。"""
    user = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user:
        raise EngineError("user_not_found", "用户不存在", 404)
    return user_view(user)


@router.patch("/{user_id}/profile")
def update_profile(user_id: str, payload: ProfileUpdate):
    """更新画像与年龄门槛。"""
    user = query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user:
        raise EngineError("user_not_found", "用户不存在", 404)
    profile = as_json(user.get("profile"), {})
    for field in ("display_name", "call_me", "birthday"):
        value = getattr(payload, field)
        if value is not None:
            profile[field] = value
    updates = {"profile": dump_json(profile)}
    if payload.age_verified is not None:
        updates["age_verified"] = 1 if payload.age_verified else 0
    columns = ",".join(["%s=?" % key for key in updates])
    execute("UPDATE users SET %s WHERE id=?" % columns,
            tuple(updates.values()) + (user_id,))
    return user_view(query_one("SELECT * FROM users WHERE id=?", (user_id,)))
