# -*- coding: utf-8 -*-
"""灌入一个演示角色：一打开就能体验到「他记得你」。

用法：
    python scripts/seed_demo.py
输出里的地址直接打开就能进入这个角色的聊天。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Windows 控制台默认 GBK，遇到 emoji 会直接抛异常，这里统一成 UTF-8 容错输出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass

import json  # noqa: E402

from backend.app.common import new_id, now_iso  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.db import dump_json, execute, init_db, insert, query_all, query_one  # noqa: E402
from backend.app.engine import chat  # noqa: E402
from backend.app.memory.store import add_memory  # noqa: E402
from backend.app.persona import default_persona  # noqa: E402
from backend.app.relationship import add_milestone  # noqa: E402

DEMO_NICKNAME = "小满"

DEMO_TURNS = [
    "我今天又被加班拖到十点，回家连饭都不想吃",
    "其实我最怕的不是累，是回到家一个人特别安静",
    "下周三有个面试，我紧张得睡不着",
]

MEMORIES = [
    ("basic", "用户在上海工作，做产品相关的工作", 0.8, ["职业", "城市"]),
    ("basic", "用户的生日是 3 月 14 日", 0.85, ["生日"]),
    ("preference", "用户喜欢美式咖啡，早上一定要一杯", 0.7, ["喜欢", "咖啡"]),
    ("preference", "用户喜欢猫，家里有一只叫团子的橘猫", 0.75, ["喜欢", "猫"]),
    ("preference", "用户不喜欢被冷处理，需要被认真回应", 0.9, ["不喜欢", "沟通偏好"]),
    ("preference", "用户说过：难过的时候先安慰我，不要讲大道理", 0.95, ["沟通偏好"]),
    ("emotion", "用户因为工作压力失眠过，晚上容易想太多", 0.9, ["日常压力"]),
    ("emotion", "用户下周三有面试，很紧张", 0.9, ["事件"]),
]


def cleanup_previous_demo():
    """清掉上一次的演示数据，保证脚本可以反复运行。"""
    for row in query_all("SELECT id FROM users WHERE nickname=?", (DEMO_NICKNAME,)):
        for character in query_all("SELECT id FROM characters WHERE user_id=?", (row["id"],)):
            for table in ("messages", "memories", "milestones",
                          "proactive_messages", "intimacy_log"):
                execute("DELETE FROM %s WHERE character_id=?" % table, (character["id"],))
            execute("DELETE FROM characters WHERE id=?", (character["id"],))
        execute("DELETE FROM users WHERE id=?", (row["id"],))


def main():
    """建用户、建角色、写记忆，并跑几轮真实对话。"""
    init_db()
    cleanup_previous_demo()

    user_id = new_id("user")
    insert("users", {
        "id": user_id,
        "nickname": DEMO_NICKNAME,
        "age_verified": 1,
        "membership": "vip",
        "profile": dump_json({"display_name": "小满", "call_me": "小满", "city": "上海"}),
        "created_at": now_iso(),
        "last_active_at": now_iso(),
    })

    character_id = new_id("char")
    insert("characters", {
        "id": character_id,
        "user_id": user_id,
        "name": "沈屿",
        "relation_type": "boyfriend",
        "template_key": "gentle_healer",
        "appearance": dump_json({"vibe": "温柔", "style": "白衬衫", "hairstyle": "soft", "age_range": "26-29"}),
        "persona": dump_json(default_persona("gentle_healer")),
        "voice": dump_json({}),
        "intimacy": 52.0,
        "stage": "close",
        "first_chat_at": now_iso(),
        "created_at": now_iso(),
    })

    for category, content, importance, tags in MEMORIES:
        add_memory(character_id, category, content, importance=importance,
                   confidence=0.9, tags=tags)

    add_milestone(character_id, "first_chat", "第一次聊天",
                  "你说的第一句话是：「今天有点累」。", occurred_at=now_iso())
    add_milestone(character_id, "stage_close", "关系进入「亲近」",
                  "你们的距离又近了一点。", occurred_at=now_iso())

    for text in DEMO_TURNS:
        result = chat(character_id, user_id, text)
        print("你：%s" % text)
        print("%s：%s" % ("沈屿", result["reply"]))
        if result["memories_used"]:
            print("  （他想起：%s）" % result["memories_used"][0]["content"])
        print("")

    character = query_one("SELECT * FROM characters WHERE id=?", (character_id,))
    session = {
        "user_id": user_id,
        "character_id": character_id,
        "name": character["name"],
        "stage": character["stage"],
        "intimacy": character["intimacy"],
        "url": "http://127.0.0.1:8000/?user_id=%s&character_id=%s" % (user_id, character_id),
    }
    session_path = os.path.join(settings.data_dir, "demo_session.json")
    with open(session_path, "w", encoding="utf-8") as handle:
        json.dump(session, handle, ensure_ascii=False, indent=2)

    print("演示数据已就绪")
    print("  用户 ID：%s" % user_id)
    print("  角色 ID：%s" % character_id)
    print("  当前关系：%s / 亲密度 %s" % (character["stage"], character["intimacy"]))
    print("")
    print("打开这个地址即可进入演示：")
    print("  http://127.0.0.1:8000/?user_id=%s&character_id=%s" % (user_id, character_id))


if __name__ == "__main__":
    main()
