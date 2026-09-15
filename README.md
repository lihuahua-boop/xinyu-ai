# 心屿 AI（XinYu AI）

一个会认识你、理解你、陪伴你成长的 AI 情感伴侣。

> 他不是被选择出来的，而是在陪伴过程中逐渐成为只属于你的那个人。

本仓库是 **心屿 AI MVP 的可运行实现**，对应《心屿AI 专属AI情感伴侣产品规划与技术方案 V1.0》第十六章（MVP 范围）。

## 已实现（MVP 第一版）

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| AI 男友创建 | 已完成 | 关系类型 → 外貌 → 人格访谈（三步向导） |
| 人格定制 | 已完成 | 10 维人格参数 + 6 套人格模板 + 人格编译层 |
| 情感化聊天 | 已完成 | 情绪识别 → 情绪确认 → 共情 → 陪伴 → 按需建议 |
| 长期记忆 | 已完成 | 4 类记忆写入 + 混合召回 + 时间衰减 + 记忆回响 |
| 关系成长 | 已完成 | 亲密度 + 5 段关系阶段机，驱动称呼与主动性 |
| 主动陪伴 | 已完成 | 早安 / 晚安 / 纪念日 / 记忆回响，带频控与静默期 |
| AI 头像 | 已完成 | 程序化生成 SVG 头像，零成本且可复现 |
| 基础语音 | 预留 | 已留 TTS 适配层，MVP 不接外部付费语音 |
| 危机干预 | 已完成 | 自伤倾向识别 + 热线引导 + 人工兜底提示 |
| 合规护栏 | 已完成 | 年龄门槛、未成年人限制、依赖诱导拦截、AI 身份告知 |

明确不做（与方案一致）：自研大模型、3D 数字人、社区、商城。

## 快速开始

```powershell
# 本机 PATH 里的 Python 3.14 缺依赖，项目用的是已验证的 3.7 解释器
$py = "D:\biyesheji\python37\python.exe"

# 1. 安装依赖（已在本机 Python 3.7.7 验证）
& $py -m pip install -r requirements.txt

# 2. 灌入演示角色（含历史记忆，启动即可体验“他记得你”）
& $py scripts\seed_demo.py

# 3. 启动
& $py -m uvicorn backend.app.main:app --reload --port 8000
```

浏览器打开 http://127.0.0.1:8000
演示脚本会输出一个带 `?user_id=&character_id=` 的地址，直接打开就进入已灌好记忆的角色。
也可以直接双击 `start.bat` 或运行 `start.ps1`。

### 三种运行模式

默认 **mock 模式**：不联网、不花钱，用本地情感回复引擎跑通全流程，适合演示与开发。

接真实模型（任意 OpenAI 兼容接口，如 DeepSeek / 通义 / 豆包 / Moonshot / OpenAI）：

```powershell
$env:XINYU_LLM_PROVIDER="openai_compat"
$env:XINYU_LLM_BASE_URL="https://api.deepseek.com/v1"
$env:XINYU_LLM_API_KEY="sk-xxxx"
$env:XINYU_LLM_MODEL="deepseek-chat"
python -m uvicorn backend.app.main:app --port 8000
```

## 目录结构

```
xinyu-ai/
├── backend/app/
│   ├── main.py            FastAPI 入口 + 静态站点
│   ├── config.py          全部配置项（环境变量，带安全默认值）
│   ├── db.py              SQLite 连接与建表
│   ├── schemas.py         请求与响应模型
│   ├── common.py          时间、ID、token 估算等工具
│   ├── persona.py         人格系统：参数编译成系统提示
│   ├── emotion.py         情绪识别（词典 + 大模型双通道）
│   ├── safety.py          危机干预 / 依赖诱导拦截 / 身份告知
│   ├── relationship.py    亲密度与关系阶段机
│   ├── prompt_builder.py  分层提示词组装（带 token 预算裁剪）
│   ├── memory/            长期记忆：写入 / 召回 / 衰减
│   ├── llm/               模型适配层：mock（本地）与 openai 兼容
│   ├── engine.py          一轮对话的完整编排
│   ├── proactive.py       主动陪伴
│   └── routers/           HTTP 接口
├── web/                   移动端优先网页客户端
├── scripts/seed_demo.py   演示数据
├── tests/                 pytest 测试
└── docs/                  架构、记忆系统、合规清单
```

## 文档

- [架构设计](docs/架构设计.md)
- [记忆系统设计](docs/记忆系统设计.md)
- [合规与安全清单](docs/合规与安全清单.md)
- [API 接口说明](docs/API.md)

## 已知边界

- 语音只留了适配接口，未接付费 TTS / ASR。
- 向量检索留了 `embedding` 字段与适配位，当前用「字面相似度 + 重要度 + 时间衰减 + 亲密度」混合召回，无需向量库即可跑。
- 上线前必须完成：模型与算法备案、内容审核三方接入、实名与年龄门槛、数据加密与删除通道。详见合规清单。
