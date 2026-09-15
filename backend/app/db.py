# -*- coding: utf-8 -*-
"""SQLite 存储层。

MVP 用单文件 SQLite，接口统一收敛成 query / execute，
以后换 PostgreSQL 只需要替换本文件。
"""

import json
import sqlite3

from .common import ensure_dir, now_iso
from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    nickname TEXT NOT NULL DEFAULT '',
    age_verified INTEGER NOT NULL DEFAULT 0,
    membership TEXT NOT NULL DEFAULT 'free',
    profile TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_active_at TEXT
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'boyfriend',
    template_key TEXT NOT NULL DEFAULT 'gentle_healer',
    appearance TEXT NOT NULL DEFAULT '{}',
    persona TEXT NOT NULL DEFAULT '{}',
    voice TEXT NOT NULL DEFAULT '{}',
    intimacy REAL NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'stranger',
    first_chat_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion TEXT NOT NULL DEFAULT 'neutral',
    emotion_intensity REAL NOT NULL DEFAULT 0,
    safety_flag TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.6,
    tags TEXT NOT NULL DEFAULT '[]',
    source_message_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_recalled_at TEXT,
    recall_count INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    embedding TEXT
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intimacy_log (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    gain REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proactive_messages (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    sent_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_character ON messages(character_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memories_character ON memories(character_id, active);
CREATE INDEX IF NOT EXISTS idx_proactive_character ON proactive_messages(character_id, status);
"""


def connect():
    """建立连接（每次调用独立连接，避免多线程共享问题）。"""
    ensure_dir(settings.data_dir)
    conn = sqlite3.connect(settings.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """建表，幂等。"""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def query_all(sql, params=()):
    """查询多行，返回 dict 列表。"""
    conn = connect()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def query_one(sql, params=()):
    """查询单行，返回 dict 或 None。"""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """写操作，返回受影响行数。"""
    conn = connect()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def insert(table, data):
    """插入一行。"""
    columns = list(data.keys())
    placeholders = ",".join(["?"] * len(columns))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(columns), placeholders)
    execute(sql, tuple(data[column] for column in columns))
    return data


def update(table, row_id, data):
    """按 id 更新一行。"""
    columns = list(data.keys())
    assignments = ",".join(["%s=?" % column for column in columns])
    sql = "UPDATE %s SET %s WHERE id=?" % (table, assignments)
    return execute(sql, tuple(data[column] for column in columns) + (row_id,))


def as_json(value, default):
    """解析 JSON 字段，脏数据不炸。"""
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dump_json(value):
    """序列化成紧凑 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def touch_user(user_id):
    """更新用户最近活跃时间。"""
    execute("UPDATE users SET last_active_at=? WHERE id=?", (now_iso(), user_id))
