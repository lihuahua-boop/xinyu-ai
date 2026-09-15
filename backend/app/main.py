# -*- coding: utf-8 -*-
"""FastAPI 入口。"""

import asyncio
import contextlib
import os

import edge_tts
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
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

    # 预置声音列表（Edge TTS 免费）
    VOICES = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 温柔女声（默认）
        "xiaoyi":   "zh-CN-XiaoyiNeural",     # 甜美女声
        "xiaochen": "zh-CN-XiaochenNeural",   # 知性女声
        "xiaomo":   "zh-CN-XiaomoNeural",     # 文艺女声
        "xiaoshuang":"zh-CN-XiaoshuangNeural",# 活泼女声
        "yunxi":    "zh-CN-YunxiNeural",      # 清朗男声
        "yunyang":  "zh-CN-YunyangNeural",    # 阳光男声
    }

    @app.get("/api/tts/voices")
    def list_voices():
        return JSONResponse({"voices": list(VOICES.keys())})

    @app.get("/api/tts")
    async def tts(text: str, voice: str = "xiaoxiao", speed: float = 1.0):
        """文字转语音，返回 mp3。"""
        v = VOICES.get(voice, VOICES["xiaoxiao"])
        rate = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"{int((speed - 1.0) * 100)}%"
        communicate = edge_tts.Communicate(text, v, rate=rate)
        # edge-tts 支持直接保存到 BytesIO
        from io import BytesIO
        buf = BytesIO()
        await communicate.save(buf)
        buf.seek(0)
        from fastapi.responses import Response
        return Response(buf.read(), media_type="audio/mpeg")

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
