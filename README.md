# AI Pulse

> **AI 圈竞品监控 + 社区舆论 多-skill bundle** —— 国内+国外双源，模型 / 工程架构 / Agent 产品 三维度，
> 日报 / 周报 / 单事件社区反馈 / 按需竞品调研 四个 skill 共享一套零-LLM 引擎。
>
> vendored 整合 [TrendRadar](https://github.com/sansan0/TrendRadar)（中文热榜）+ [follow-news](https://github.com/tangwz/follow-news)（英文社区聚合），语义工作交给 [OpenClaw](https://openclaw.ai) agent。

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 这是什么

AI Pulse 是一个**自包含的单仓多-skill bundle**：`git clone` + 一次 `bash setup.sh` 即获完整功能，
**无需克隆兄弟仓、无 patch 步骤**。本仓既是「共享引擎」也是 4 个 OpenClaw skill 的来源——
follow-news 聚合引擎 vendored 在 `follow-news-addons/`，TrendRadar 中文热榜 vendored 在 `trendradar/`。

核心设计是**双脑分工**：

- **数据面（零 LLM）** —— 采集、去重、质量评分、Tier 启发式预标签全部由确定性脚本完成，**不调用任何 LLM API**，零 key 成本、行为可复现、可离线单测。
- **智能面（复用你的 agent token）** —— 语义去重、分类复议、翻译、报告撰写交给 OpenClaw agent，按 prompt 模板完成。

---

## 4 个 skill

| Skill | 做什么 | 触发词 | 入口 |
|---|---|---|---|
| **日报** `ai-pulse-daily` | 现抓最近 24h 英文 RSS/HN/GitHub/Web/播客 + 中文热榜，产出当日动态 | "日报" / "daily" / "今天 AI 圈有什么" | `scripts/daily-digest.sh` |
| **周报** `ai-pulse-weekly` | 现抓 7 天数据，按互动热度选题，按社区情绪分组（👍/👎/⚖️/🇨🇳）出深度周报 | "周报" / "weekly" / "本周" / "AI 圈周报" | `scripts/weekly.sh` |
| **单事件社区反馈** `ai-pulse-topic` | 针对单个事件现抓多源社区反应（HN/V2EX 评论原文 + 中文热榜 + KOL + Twitter） | "社区对 X 怎么看" / "X 发布后反响如何" | `scripts/topic-feedback.sh --query …` |
| **按需竞品调研** `ai-pulse-brief` | 抓录入竞品的官方动态 + 行业/岗位 KOL 内容，综合方向/场景分析 | "竞品调研" / "调研 <竞品>" / "<行业> agent 竞品" | `scripts/competitor-brief.sh` |

监控对象覆盖国产 Agent 竞品（通义灵码 / Trae / Manus 等）官方动态 + 行业/岗位 KOL，
并聚合英文 RSS / HN / GitHub / Web 搜索 / 播客 + 中文热榜。各 skill 完整路由规则见 `skills/<name>/SKILL.md`。

**核心特性**

- 🌏 **国内+国外双源** — 179 信源（RSS / Twitter / GitHub / 中文热榜 / Web 搜索 / 播客）
- 🧠 **AI 圈聚焦过滤** — AI 关键词词表过滤，不被泛科技/财经新闻污染
- 🎯 **三维度分类** — 模型 / 工程架构 / Agent 产品
- 🏆 **Tier 1/2/3 自动分级** — 35+ Tier 1 厂商白名单（OpenAI / Anthropic / DeepSeek / Cursor / …）
- 💬 **HN/V2EX 评论原文引用** — Top 评论文本，零鉴权 API
- 🔄 **按需 7 天回溯** — 周报触发时现抓 7 天数据，自给自足
- 💰 **零 LLM API key** — 去重和写作由你的 OpenClaw agent 完成

---

## 它怎么工作

```
你说"本周周报" (或 bash scripts/weekly.sh)
        │
        ▼
┌──────────────────────────────────────────────────┐
│ 数据采集（脚本侧，无 LLM）                         │
│                                                   │
│ - TrendRadar SQLite 7 天回溯 → 中文 RSS XML       │
│ - follow-news 并行抓 RSS / GitHub / Web /         │
│   Twitter / 播客                                  │
│ - 多源去重 + 质量评分 + 按 topic 分组             │
│ - 启发式 Tier 预标签（35+ 厂商正则白名单）         │
│ - HN/V2EX 评论 enrichment（仅 Tier 1）            │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ OpenClaw agent（智能侧，复用你的 agent token）     │
│                                                   │
│ - 读对应 prompt 模板拿到规则                       │
│ - 阶段 1: 语义去重                                │
│ - 阶段 2: 发布验证                                │
│ - 阶段 3: 三维度分类 + Tier 复议                  │
│ - 阶段 4: 按 5 问模板写自然语言报告               │
└──────────────────────────────────────────────────┘
        │
        ▼
   你看到的最终报告
```

详细架构见 [docs/data-flow.md](docs/data-flow.md)。

---

## 前置要求

- **Python ≥ 3.12**（TrendRadar 硬性要求）
- **Git**
- **Shell**：macOS / Linux 直接用；**Windows 必须用 Git Bash / WSL / msys2**（避免 `/tmp/` 路径解释错误与 GBK 编码问题）
- **OpenClaw 客户端** —— 触发对话式报告；命令行手动跑 `weekly.sh` 也能拿到结构化 JSON
- 可选：**OpenCLI**（Twitter KOL 抓取，零鉴权零成本，复用本机 Chrome 登录态）

---

## 安装 —— 从零到能跑

### Step 1 · 克隆本仓

```bash
git clone https://github.com/huudage/ai-pulse.git
cd ai-pulse
```

### Step 2 · 配置 API key

```bash
cp .env.example .env
# 编辑 .env：至少配 GITHUB_TOKEN（不配 GitHub 22 个 repo 全失败）
```

`.env` 里所有 key 都是可选的，没填的功能自动跳过。推荐配置见 [Configuration](#configuration)。

### Step 3 · 一次性安装（pip install + 本地化）

```bash
bash setup.sh
```

`setup.sh` 自动做：

1. `pip install` 引擎依赖
2. 解析 workspace 配置占位符（把 TrendRadar 实际路径填进 `file://` 信源；复制竞品 profiles 骨架）
3. 建好 `trendradar/output/` 运行时目录

**无外部 clone、无 patch** —— 上游已 vendored 进本仓。可选参数：

```bash
bash setup.sh --skip-deps    # 跳过 pip install（自己装依赖）
```

> `install.sh` / `update.sh` 仍可用，已转为 `setup.sh` 的薄封装（向后兼容）。

### Step 4 · 验证安装

```bash
bash verify.sh    # 校验 vendored 文件齐全 + 4 skill 清单 + wrapper + 模块可导入 + 入口 --help
bash doctor.sh    # 体检 .env API key 配置度，给出补救建议
```

`verify.sh` 全绿即安装完整；`doctor.sh` 评分 ≥ 3/4 就可以跑报告了。

### Step 5 · 试跑（命令行直接验证）

```bash
bash scripts/daily-digest.sh        # 日报：现抓 24h → /tmp/td-merged.json
bash scripts/weekly.sh              # 周报：现抓 7 天 → /tmp/td-weekly-{merged.json,.md}
bash scripts/topic-feedback.sh --query "Claude Code"   # 单事件社区反馈
bash scripts/competitor-brief.sh --product "通义灵码"   # 按需竞品调研
```

所有入口经 Git Bash + `PYTHONUTF8=1` 调用——**禁止绕过 shell wrapper 直接 `python` 调 fetcher**
（会触发 Windows GBK 编码与 `/tmp` 路径错误）。

### Step 6 · 部署为 OpenClaw skills（可选）

```bash
bash deploy-skill.sh
```

`deploy-skill.sh` 把共享引擎复制为 `~/.openclaw/skills/ai-pulse-engine/`（无 SKILL.md ⇒ 不被注册），
再 fan-out 4 个兄弟 skill 目录（`ai-pulse-{daily,weekly,topic,brief}`），各自 SKILL.md 指向共享引擎。

```bash
bash deploy-skill.sh --skills-dir /custom/path   # 默认 ~/.openclaw/skills
bash deploy-skill.sh --skip-doctor               # 跳过 doctor.sh
```

部署后在 OpenClaw 里直接说「本周 AI 圈周报」「调研一下 Manus」「社区对 Claude Code 怎么看」即可触发。

---

## Configuration

`.env` 里所有 key 均可选，缺失的功能优雅降级（自动跳过，不中断）。下面这些**强烈推荐**：

### 必配

| 变量 | 用途 | 不配的后果 |
|---|---|---|
| `GITHUB_TOKEN` | GitHub release / trending | 匿名 60 req/h，22 个 repo 全失败 |

### 推荐

| 变量 | 用途 | 申请地址 |
|---|---|---|
| `BRAVE_API_KEYS` 或 `TAVILY_API_KEY` | Web 搜索 | [Brave](https://brave.com/search/api/) (2000 query/月) / [Tavily](https://app.tavily.com/) (1000 query/月) |
| OpenCLI 安装 | Twitter KOL 抓取 | [opencli releases](https://github.com/jackwener/opencli/releases) + Chrome 扩展 + 登录 X.com |

### 可选

| 变量 | 用途 |
|---|---|
| `HTTPS_PROXY` / `HTTP_PROXY` | 国内访问 github / twitter 用代理 |
| `ENABLE_KOL_BLOGS` | AI KOL 深度博客 11 个（默认开启） |
| `BILIBILI_COOKIE` / `ZHIHU_COOKIE` / `JIKE_ACCESS_TOKEN` / `WEIXIN_SEARCH_URL` | 竞品 KOL 多平台采集（缺则该平台跳过） |
| `GETX_API_KEY` / `X_BEARER_TOKEN` / `TWITTERAPI_IO_KEY` | OpenCLI 不可用时的 Twitter 备选 API |

`PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` 在 Windows 上**必须保留**。完整选项见 [.env.example](.env.example)。

### 竞品清单配置

竞品产品与官方源在 `follow-news-addons/workspace/config/competitor-profiles.json`（`setup.sh` 复制骨架，
已存在则保留你填写的官方源）。补全各产品 `official_sources` 后竞品调研才会有数据。

---

## 日常使用

| 场景 | 命令 |
|---|---|
| 日报（现抓 24h） | `bash scripts/daily-digest.sh` |
| 周报（现抓 7 天，建议周日触发） | `bash scripts/weekly.sh` |
| 单事件社区反馈 | `bash scripts/topic-feedback.sh --query "…"` |
| 按需竞品调研 | `bash scripts/competitor-brief.sh --product "…"` |
| 可选：累积中文热榜厚度（建议挂 cron 早 8 点） | `bash scripts/daily.sh` |
| 检查 `.env` 配置度 | `bash doctor.sh` |
| 检查安装完整性 | `bash verify.sh` |

> `scripts/daily.sh` 是**可选累积 cron**：周报 `--fetch-now` 自给自足，跑 daily.sh 只为给周报中文热榜段补 7 天厚度（TrendRadar 快照不可回溯），本身不是 skill、非周报前置。

或直接在 OpenClaw 对话里说触发词，由 agent 路由触发。

---

## 升级

```bash
bash update.sh    # git pull 本仓 + 重跑 setup.sh
```

用户的 `follow-news-addons/workspace/config/` 本地化配置会保留，不被覆盖。
升级 vendored 上游 SHA 是维护者操作，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 卸载

```bash
rm -rf ~/.openclaw/skills/ai-pulse-engine ~/.openclaw/skills/ai-pulse-*
rm -rf ai-pulse
```

我们没装到系统级，也没改 `~/.bashrc`。

---

## 文档

- [docs/data-flow.md](docs/data-flow.md) —— 每日 / 每周数据流详细图
- [docs/data-sources.md](docs/data-sources.md) —— 179 信源完整清单
- [docs/features.md](docs/features.md) —— 功能与脚本职责
- [docs/prompt-design.md](docs/prompt-design.md) —— prompt 模板设计思路
- [CONTRIBUTING.md](CONTRIBUTING.md) —— 维护者向（升级 vendored 上游 SHA、加新平台评论抓取、改 Tier 1 厂商白名单）

---

## Troubleshooting

| 症状 | 排查 |
|---|---|
| `pip install` 失败 | Python ≥ 3.12；国内用 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| GitHub release 全失败 | 没设 `GITHUB_TOKEN`（[Configuration](#configuration)） |
| Web 搜索 0 items | 没设 `BRAVE_API_KEYS` 或 `TAVILY_API_KEY` |
| Twitter 0 items | OpenCLI 没装 / 扩展未连 / 未登录 X.com；跑 `opencli doctor` 看详情 |
| Windows `'gbk' codec can't decode` | 确认 `.env` 里有 `PYTHONUTF8=1` 且通过本仓 shell 脚本调用（不要绕过直接 `python` 调 fetcher） |
| HN/V2EX 评论抓不到 | 网络访问 `hacker-news.firebaseio.com` 和 `sov2ex.com` / `v2ex.com` 不通；可能需要代理 |
| 竞品 KOL 某平台无数据 | 该平台凭证未配（`ZHIHU_COOKIE` 等）→ 自动跳过，属预期行为 |

进一步排查可跑 `python follow-news-addons/scripts/run-pipeline.py --hours 24 --verbose` 看哪一路失败。

---

## 鸣谢

- [TrendRadar](https://github.com/sansan0/TrendRadar) by @sansan0 —— 中文热榜聚合工具
- [follow-news](https://github.com/tangwz/follow-news) by @tangwz —— AI 圈日报 OpenClaw Skill
- [OpenClaw](https://openclaw.ai) —— Skill 平台

---

## License

[MIT](LICENSE)
