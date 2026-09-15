# -*- coding: utf-8 -*-
"""FastAPI 入口。"""

import asyncio
import contextlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .db import init_db, query_all
from .engine import EngineError
from .proactive import materialize
from .routers import characters, chat, memory, meta, users

WEB_DIR = os.path.join(BASE_DIR, "web")
PROACTIVE_INTERVAL_SECONDS = 900


def create_app():
    """创建应用。"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="会认识你、记住你、陪伴你成长的 AI 情感伴侣（MVP）",
    )

    # 开发期全放开，上线要收敛到自有域名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(EngineError)
    def handle_engine_error(request, error):
        """把业务错误统一转成结构化响应。"""
        return JSONResponse(
            status_code=error.status,
            content={"code": error.code, "message": error.message},
        )

    app.include_router(meta.router)
    app.include_router(users.router)
    app.include_router(characters.router)
    app.include_router(chat.router)
    app.include_router(memory.router)

    state = {"task": None}

    @app.on_event("startup")
    async def on_startup():
        """建表 + 拉起主动陪伴巡检。"""
        init_db()
        if settings.proactive_enabled:
            state["task"] = asyncio.ensure_future(_proactive_loop())

    @app.on_event("shutdown")
    async def on_shutdown():
        """停掉后台任务。"""
        task = state.get("task")
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    if os.path.isdir(WEB_DIR):
        # 放在最后：前面所有 /api 路由优先匹配
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    else:
        os.makedirs(WEB_DIR)
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    return app


async def _proactive_loop():
    """后台巡检：定期检查谁该被主动关心一下。"""
    while True:
        try:
            await asyncio.sleep(PROACTIVE_INTERVAL_SECONDS)
            rows = query_all("SELECT id, user_id FROM characters")
            for row in rows:
                await asyncio.get_event_loop().run_in_executor(
                    None, materialize, row["id"], row["user_id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            # 主动陪伴失败绝不能影响主服务
            await asyncio.sleep(60)


app = create_app()
