# -*- coding: utf-8 -*-
"""通用工具：时间、ID、文本处理、token 估算。

保持纯标准库实现，方便在 Python 3.7 上零依赖运行。
"""

import datetime
import hashlib
import os
import re
import uuid

CST = datetime.timezone(datetime.timedelta(hours=8))

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def now():
    """当前时间（东八区）。"""
    return datetime.datetime.now(CST)


def now_iso():
    """当前时间的 ISO 字符串。"""
    return now().isoformat(timespec="seconds")


def parse_iso(value):
    """解析 ISO 字符串，失败返回 None。"""
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def hours_since(iso_value):
    """距离某个时间点过去了多少小时。"""
    moment = parse_iso(iso_value)
    if moment is None:
        return 24.0 * 30
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=CST)
    return max(0.0, (now() - moment).total_seconds() / 3600.0)


def days_since(iso_value):
    """距离某个时间点过去了多少天。"""
    return hours_since(iso_value) / 24.0


def new_id(prefix):
    """生成带前缀的短 ID。"""
    return "%s_%s" % (prefix, uuid.uuid4().hex[:16])


def stable_hash(text):
    """稳定的字符串哈希，用于可复现的随机选择。"""
    return int(hashlib.md5((text or "").encode("utf-8")).hexdigest()[:8], 16)


def pick(options, seed_text):
    """按种子从选项里稳定挑一项，避免同一句话反复出现。"""
    if not options:
        return ""
    return options[stable_hash(seed_text) % len(options)]


def est_tokens(text):
    """粗略估算 token：中文 1 字约 1 token，英文 4 字符约 1 token。"""
    if not text:
        return 0
    cjk = len(CJK_RE.findall(text))
    other = max(0, len(text) - cjk)
    return int(cjk + other / 4.0)


def bigrams(text):
    """抽取中文二字组与英文词，用于无依赖的近似匹配。"""
    text = (text or "").lower()
    chars = CJK_RE.findall(text)
    grams = []
    if len(chars) >= 2:
        grams.extend([chars[i] + chars[i + 1] for i in range(len(chars) - 1)])
    elif chars:
        grams.append(chars[0])
    grams.extend(re.findall(r"[a-z0-9]{2,}", text))
    return grams


def truncate(text, limit):
    """按字符数截断。"""
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def ensure_dir(path):
    """确保目录存在。"""
    if path and not os.path.isdir(path):
        os.makedirs(path)
    return path


def clamp(value, low=0.0, high=1.0):
    """把数值限制在区间内。"""
    return max(low, min(high, value))


def safe_int(value, default=0):
    """容错取整。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    """容错取浮点。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
