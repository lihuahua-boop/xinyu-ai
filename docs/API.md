# API 接口说明

所有接口以 `/api` 开头，返回 JSON。错误统一为 `{"code": "...", "message": "..."}`。

## 元数据

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/meta/config` | 前端启动配置（模型、限额、年龄门槛） |
| GET | `/api/meta/templates` | 6 套人格模板 |
| GET | `/api/meta/relation-types` | 关系类型 |
| GET | `/api/meta/persona-params` | 11 个人格参数定义 |
| GET | `/api/meta/stages` | 关系阶段 |
| GET | `/api/meta/interview` | 人格访谈问题 |
| GET | `/api/meta/appearance` | 外貌选项 |
| GET | `/api/meta/emotions` | 情绪标签 |

## 用户

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/users` | 创建用户 `{nickname, age_verified}` |
| GET | `/api/users/{user_id}` | 用户信息 |
| PATCH | `/api/users/{user_id}/profile` | 更新画像 `{display_name, call_me, birthday, age_verified}` |

## 角色

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/characters` | 创建角色 `{user_id, name, relation_type, template_key, appearance, persona}` |
| GET | `/api/characters?user_id=` | 角色列表 |
| GET | `/api/characters/{id}` | 角色详情（含人格标签、记忆统计、关系状态） |
| PATCH | `/api/characters/{id}` | 调整名字 / 外观 / 人格参数 |
| GET | `/api/characters/{id}/avatar.svg` | 程序化生成的头像 |
| POST | `/api/characters/{id}/interview` | 回答访谈问题 `{user_id, question_key, option_key}` |
| GET | `/api/characters/{id}/relationship` | 亲密度、阶段、里程碑 |

## 聊天

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/characters/{id}/chat` | 发消息 `{user_id, text}` |
| GET | `/api/characters/{id}/messages?limit=60` | 聊天记录 |

`chat` 返回结构：

```json
{
  "reply": "这句话本身",
  "emotion": {"key": "tired", "label": "疲惫", "intensity": 0.62},
  "memories_used": [
    {"id": "mem_x", "category": "emotion", "category_label": "情绪记忆",
     "content": "用户因为工作压力失眠过", "reason": "和这次聊到的事直接相关", "score": 0.71}
  ],
  "memories_written": 1,
  "relationship": {
    "intimacy": 53.4, "intimacy_gain": 1.4, "stage": "close",
    "stage_label": "亲近", "stage_changed": false, "days_together": 3,
    "progress": {"next_stage": "intimate", "next_label": "亲密", "remaining": 17.6}
  },
  "safety": {"level": "none", "flags": []},
  "meta": {"provider": "mock", "latency_ms": 12, "usage": {"prompt_tokens_est": 900}}
}
```

## 记忆

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/characters/{id}/memories` | 记忆列表（含分组与统计） |
| POST | `/api/characters/{id}/memories` | 手动添加 `{category, content, importance}` |
| DELETE | `/api/memories/{memory_id}` | 让他忘掉这件事 |

## 主动陪伴

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/characters/{id}/proactive?materialize_now=1` | 生成到点的主动消息并返回历史 |
| POST | `/api/proactive/{record_id}/dismiss` | 关掉一条主动消息 |

主动陪伴受每日上限与静默期（默认 23:00–07:00）双重约束。
