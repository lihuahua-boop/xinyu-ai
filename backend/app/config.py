# -*- coding: utf-8 -*-
"""配置：全部来自环境变量，且都有可直接跑起来的默认值。"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")


def _bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _load_dotenv(path):
    """极简 .env 解析：只支持 KEY=VALUE 与 # 注释，且不覆盖已存在的环境变量。"""
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except (OSError, ValueError):
        pass


class Settings(object):
    """应用配置。"""

    def __init__(self):
        self.app_name = "心屿 AI"
        self.version = "0.1.0"

        # 数据落盘位置（MVP 用 SQLite 单文件，上线换 PostgreSQL）
        self.data_dir = os.environ.get("XINYU_DATA_DIR") or DEFAULT_DATA_DIR
        self.db_path = os.environ.get("XINYU_DB_PATH") or os.path.join(self.data_dir, "xinyu.db")

        # 模型：默认 mock，本地情感引擎，不联网不花钱
        self.llm_provider = os.environ.get("XINYU_LLM_PROVIDER", "mock")
        self.llm_base_url = os.environ.get("XINYU_LLM_BASE_URL", "")
        self.llm_api_key = os.environ.get("XINYU_LLM_API_KEY", "")
        self.llm_model = os.environ.get("XINYU_LLM_MODEL", "deepseek-chat")
        self.llm_timeout = _int("XINYU_LLM_TIMEOUT", 60)
        self.llm_temperature = _float("XINYU_LLM_TEMPERATURE", 0.85)
        self.llm_max_tokens = _int("XINYU_LLM_MAX_TOKENS", 600)
        # 接真实模型时，是否用大模型做记忆的结构化抽取（规则始终兜底）
        self.llm_memory_extraction = _bool("XINYU_LLM_MEMORY_EXTRACTION", True)

        # 记忆系统
        self.memory_top_k = _int("XINYU_MEMORY_TOP_K", 5)
        self.memory_min_score = _float("XINYU_MEMORY_MIN_SCORE", 0.22)
        self.memory_half_life_days = _float("XINYU_MEMORY_HALF_LIFE_DAYS", 45.0)
        self.memory_prompt_budget = _int("XINYU_MEMORY_PROMPT_BUDGET", 900)
        self.recent_turns = _int("XINYU_RECENT_TURNS", 12)

        # 成本与限额
        self.free_daily_quota = _int("XINYU_FREE_DAILY_QUOTA", 60)

        # 安全
        self.age_gate_required = _bool("XINYU_AGE_GATE_REQUIRED", True)
        self.min_age = _int("XINYU_MIN_AGE", 18)
        # 上线必须接第三方内容审核，这里留开关与适配位
        self.moderation_enabled = _bool("XINYU_MODERATION_ENABLED", False)

        # 主动陪伴
        self.proactive_enabled = _bool("XINYU_PROACTIVE_ENABLED", True)
        self.proactive_daily_limit = _int("XINYU_PROACTIVE_DAILY_LIMIT", 2)
        self.quiet_start_hour = _int("XINYU_QUIET_START_HOUR", 23)
        self.quiet_end_hour = _int("XINYU_QUIET_END_HOUR", 7)

        self.debug = _bool("XINYU_DEBUG", True)

    def public(self):
        """可安全暴露给前端的配置。"""
        model = "local-emotion-engine" if self.llm_provider == "mock" else self.llm_model
        return {
            "app_name": self.app_name,
            "version": self.version,
            "llm_provider": self.llm_provider,
            "llm_model": model,
            "proactive_enabled": self.proactive_enabled,
            "age_gate_required": self.age_gate_required,
            "min_age": self.min_age,
        }

_load_dotenv(os.path.join(BASE_DIR, ".env"))
settings = Settings()
