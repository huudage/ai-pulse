# AI Pulse

> **AI 圈竞品监控 + 社区反馈周报** —— 模型 / 工程架构 / Agent 产品 三维度，国内+国外，每周自动出深度解读
>
> 基于 [TrendRadar](https://github.com/sansan0/TrendRadar)（中文热榜）+ [follow-news](https://github.com/tangwz/follow-news)（英文社区聚合）+ [OpenClaw](https://openclaw.ai)（AI 助手）的整合方案。

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 这个项目能做什么

每周给你一份**有深度的 AI 圈周报**：

```
本周 AI 圈竞品监控周报 (2026-05-15 ~ 2026-05-21)

## 摘要
本周共识别 4 件 Tier 1 / 7 件 Tier 2 / 12 件 Tier 3。
最值得注意的 3 个趋势：
1. DeepSeek 与 Anthropic 同周发布主力模型，国产前沿首次贴近闭源旗舰
2. ...

## Tier 1 深度解读

### 模型

#### DeepSeek v4.0 发布（2026-05-18）
**1. 是什么** —— DeepSeek 发布 V4 系列，引入新 MoE 架构...
**2. 为什么重要** —— ...
**3. 技术亮点** —— ...
**4. 竞品对照** —— 同期 Anthropic Claude 5 在编码任务上 +15%，但...
**5. 社区反响**
  > "Way better than I expected." — JKCalhoun (HN, 👍 245)
  > "Beats Claude on my eval set." — u/researcher42 (r/LocalLLaMA, 👍 543)
  ...
```

**核心特性**

- 🌏 **国内+国外双源** — 165+ 信源（RSS / Twitter / GitHub / Reddit / 中文热榜 / Web 搜索 / 播客）
- 🧠 **AI 圈聚焦过滤** — AI 关键词词表过滤，不被科技/财经新闻污染
- 🎯 **三维度分类** — 模型 / 工程架构 / Agent 产品
- 🏆 **Tier 1/2/3 自动分级** — 35+ Tier 1 厂商白名单（OpenAI / Anthropic / DeepSeek / Cursor / ...）
- 💬 **HN/Reddit 评论原文引用** — Top 评论文本，零鉴权 API
- 🔄 **按需 7 天回溯** — 周报触发时现抓 7 天数据
- 💰 **零 LLM API key** — 智能去重和写作由你的 OpenClaw agent 处理

---

## 它是怎么工作的

```
你说"本周周报" (或 bash weekly.sh)
        │
        ▼
┌──────────────────────────────────────────────────┐
│ 数据采集（脚本侧，无 LLM）                         │
│                                                   │
│ - TrendRadar SQLite 7 天回溯 → 中文 RSS XML       │
│ - follow-news 并行抓 RSS / GitHub / Web /         │
│   Twitter / 播客 / Reddit                         │
│ - 多源去重 + 质量评分 + 按 topic 分组             │
│ - 启发式 Tier 预标签（35+ 厂商正则白名单）         │
│ - HN/Reddit 评论 enrichment（仅 Tier 1）          │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ OpenClaw agent（智能侧，复用你的 agent token）     │
│                                                   │
│ - 读 competitor-monitor.md 拿到产品规则           │
│ - 阶段 1: 语义去重                                │
│ - 阶段 2: 发布验证                                │
│ - 阶段 3: 三维度分类 + Tier 复议                  │
│ - 阶段 4: 按 5 问模板写自然语言周报               │
└──────────────────────────────────────────────────┘
        │
        ▼
   你看到的最终周报
```

详细架构见 [docs/data-flow.md](docs/data-flow.md)。

---

## 前置要求

- **Python ≥ 3.10**（TrendRadar 要求）
- **Git**
- **Shell**：macOS / Linux 直接用；**Windows 必须用 Git Bash / WSL / msys2**（避免 `/tmp/` 路径解释错误）
- **OpenClaw 客户端** —— 触发对话式周报；命令行手动跑 `weekly.sh` 也能拿到结构化 JSON
- 可选：**OpenCLI**（Twitter KOL 抓取，零鉴权零成本，复用本机 Chrome 登录态）

---

## 部署 —— 从零到能跑

### Step 1 · 克隆本仓

```bash
git clone https://github.com/<你的用户名>/ai-pulse.git
cd ai-pulse
```

### Step 2 · 配置 API key

```bash
cp .env.example .env
# 编辑 .env：至少配 GITHUB_TOKEN（不配 GitHub 22 个 repo 全失败）
```

`.env` 里的所有 key 都是可选的，没填的功能自动跳过。推荐配置见 [Configuration](#configuration) 章节。

### Step 3 · 安装上游 + 应用 patches + 装依赖

```bash
bash install.sh
```

`install.sh` 自动做以下事情：

1. 克隆 TrendRadar 和 follow-news 到 `../upstream/`
2. checkout 到固定的上游 SHA（保证 patch 干净应用）
3. 应用 `patches/*/upstream.patch`（修改 8 个上游文件：评论模块 hook / RSS 旁路 / SQLite 周导出 / SKILL.md 路由等）
4. 复制 `*-addons/` 下的新增文件到上游对应位置
5. 写入 `follow-news/workspace/config/follow-news-sources.json`，把 TrendRadar 实际路径填进去
6. `pip install` 上下游依赖
7. 跑一次 import 验证

可选参数：

```bash
bash install.sh --target /your/custom/path   # 默认 ../upstream
bash install.sh --skip-deps                  # 跳过 pip install（自己装依赖）
```

### Step 4 · 验证安装

```bash
bash verify.sh    # 检查 patches/addons 都已应用 + Python 模块可导入
bash doctor.sh    # 检查 .env 里的 API key 配置度，给出补救建议
```

`verify.sh` 全 ✅ 就说明安装完整；`doctor.sh` 评分 ≥ 3/4 就可以跑周报了。

### Step 5 · 安装为 OpenClaw skill

```bash
bash deploy-skill.sh
```

`deploy-skill.sh` 自动做：

1. 把 `../upstream/follow-news/` 整个复制到 `~/.openclaw/skills/ai-pulse/`（skill 在 OpenClaw 中以 `ai-pulse` 名字注册，原 follow-news 上游被作为底层 pipeline 收编）
2. 写 `.ai-pulse-config` 固化 `AI_PULSE_DIR` / `TRENDRADAR_DIR`（`weekly.sh` 启动时 source 它定位 TrendRadar）
3. 复制 `scripts/{weekly,daily}.sh` 到 `skill/scripts/ai-pulse/`，让 skill 触发时直接看到入口

可选参数：

```bash
bash deploy-skill.sh --skills-dir /custom/path   # 默认 ~/.openclaw/skills
bash deploy-skill.sh --skip-install              # 跳过 install.sh（已装过）
bash deploy-skill.sh --skip-doctor               # 跳过 doctor.sh
```

如果 `--target` 自定义了 upstream 目录，deploy 时要传同一个值。

### Step 6 · 首次试跑

```bash
# 每日 —— 累积 TrendRadar 中文热榜（SQLite）+ Reddit hot 列表
bash scripts/daily.sh

# 每周 —— 现抓 7 天数据 + 评级 + 评论 → 写出周报底盘
bash scripts/weekly.sh
```

`weekly.sh` 跑完会输出：

- `/tmp/td-weekly-merged.json` —— 结构化数据
- `/tmp/td-weekly.md` —— 原始 markdown（含 Tier + HN/Reddit 评论）

### Step 7 · 在 OpenClaw 里触发周报

打开 OpenClaw 客户端，说：

> "本周 AI 圈竞品监控周报"

agent 自动按 `SKILL.md` 路由 5 触发 `weekly-feedback.py`，再按 `references/prompts/competitor-monitor.md` 的 4 阶段规则（语义去重 → 发布验证 → 三维度分类 → 5 问模板撰写）输出自然语言周报。

---

## Configuration

`.env` 里的所有 key 都是可选的，但下面这些**强烈推荐**配置：

### 必配

| 变量 | 用途 | 不配的后果 |
|---|---|---|
| `GITHUB_TOKEN` | GitHub release / trending | 匿名 60 req/h，22 个 repo 全失败 |

### 推荐

| 变量 | 用途 | 申请地址 |
|---|---|---|
| `BRAVE_API_KEYS` 或 `TAVILY_API_KEY` | Web 搜索 | [Brave](https://brave.com/search/api/) (2000 query/月) / [Tavily](https://app.tavily.com/) (1000 query/月) |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | Reddit OAuth | [reddit prefs/apps](https://www.reddit.com/prefs/apps)，2023 起匿名 403 |
| OpenCLI 安装 | Twitter KOL 抓取 | [opencli releases](https://github.com/jackwener/opencli/releases) + Chrome 扩展 + 登录 X.com |

### 可选

| 变量 | 用途 |
|---|---|
| `HTTPS_PROXY` / `HTTP_PROXY` | 国内访问 reddit / github / twitter 用代理 |
| `ENABLE_KOL_BLOGS` | AI KOL 深度博客 11 个（默认开启） |
| `GETX_API_KEY` / `X_BEARER_TOKEN` / `TWITTERAPI_IO_KEY` | OpenCLI 不可用时的 Twitter 备选 API |

完整选项与申请步骤见 [.env.example](.env.example)。

---

## 日常使用

| 场景 | 命令 |
|---|---|
| 每天累积数据（建议挂 cron 早 8 点） | `bash scripts/daily.sh` |
| 出周报（建议周日 22 点或按需触发） | `bash scripts/weekly.sh` |
| 检查 `.env` 配置度 | `bash doctor.sh` |
| 检查安装完整性 | `bash verify.sh` |

或直接在 OpenClaw 对话里说"本周周报"由 agent 触发。

---

## 升级

```bash
bash update.sh
```

`update.sh` 自动 `git pull` 本仓 + 重跑 `install.sh`。

用户的 `follow-news/workspace/config/` 配置会保留，不会被覆盖。

如果上游 TrendRadar / follow-news 出了新版本你想升级 pin SHA，那是维护者操作，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 卸载

```bash
rm -rf ../upstream
rm -rf ~/.openclaw/skills/ai-pulse
# 旧版本残留可能需要一并清除：
# rm -rf ~/.openclaw/skills/follow-news
rm -rf ai-pulse
```

我们没装到系统级，也没改 `~/.bashrc`。

---

## 文档

- [docs/data-flow.md](docs/data-flow.md) —— 每日 / 每周数据流详细图
- [docs/data-sources.md](docs/data-sources.md) —— 165+ 信源完整清单
- [docs/prompt-design.md](docs/prompt-design.md) —— `competitor-monitor.md` 设计思路
- [CONTRIBUTING.md](CONTRIBUTING.md) —— 维护者向（升级上游 SHA、加新平台评论抓取、改 Tier 1 厂商白名单）

---

## Troubleshooting

| 症状 | 排查 |
|---|---|
| `pip install` 失败 | Python ≥ 3.10；国内用 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| GitHub release 全失败 | 没设 `GITHUB_TOKEN`（[Configuration](#configuration)） |
| Reddit 全 403 | 没设 `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` |
| Web 搜索 0 items | 没设 `BRAVE_API_KEYS` 或 `TAVILY_API_KEY` |
| Twitter 0 items | OpenCLI 没装 / 扩展未连 / 未登录 X.com；跑 `opencli doctor` 看详情 |
| Windows `'gbk' codec can't decode` | 确认 `.env` 里有 `PYTHONUTF8=1` 且通过本仓 shell 脚本调用（不要绕过直接 `python` 调 fetcher） |
| `weekly-feedback.py` 报 "No daily archives found" | 走默认 `--fetch-now` 模式不需要 daily archive；如果手动指定了 `--archive-dir` 才需要先跑过 `daily.sh` |
| HN/Reddit 评论抓不到 | 网络访问 `hacker-news.firebaseio.com` 和 `reddit.com` 不通；可能需要代理 |

进一步排查可跑 `python scripts/run-pipeline.py --hours 24 --verbose` 看哪一路具体失败。

---

## 鸣谢

- [TrendRadar](https://github.com/sansan0/TrendRadar) by @sansan0 —— 中文热榜聚合工具
- [follow-news](https://github.com/tangwz/follow-news) by @tangwz —— AI 圈日报 OpenClaw Skill
- [OpenClaw](https://openclaw.ai) —— Skill 平台

---

## License

[MIT](LICENSE)
