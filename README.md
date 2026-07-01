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

全程 6 步，约 5–10 分钟（含 pip install）。**Windows 用户请在 Git Bash / WSL / msys2 里操作**，
不要用 PowerShell / CMD 直接跑 `.sh`（会踩 `/tmp` 路径与 GBK 编码坑）。

### Step 0 · 确认前置环境

开工前先核一遍（缺一不可）：

```bash
python --version     # 需 ≥ 3.12（TrendRadar 硬性要求；低于此中文热榜模块无法导入）
git --version        # 任意较新版本即可
bash --version       # Windows 上应显示 Git Bash / msys2 的 bash
```

> Windows 上 `python3` 常是微软商店的占位 shim，`setup.sh` 会**优先用 `python`**、其次 `python3`。
> 若 `python --version` 报错或 <3.12，先去 [python.org](https://www.python.org/downloads/) 装 3.12+ 再继续。

### Step 1 · 克隆本仓

```bash
git clone https://github.com/huudage/ai-pulse.git
cd ai-pulse
```

本仓**自包含**：follow-news 引擎已 vendored 在 `follow-news-addons/`，TrendRadar 已 vendored 在 `trendradar/`，
**无需克隆任何兄弟仓、无 patch 步骤**。

### Step 2 · 配置 API key

```bash
cp .env.example .env
# 用编辑器打开 .env，至少填 GITHUB_TOKEN
```

`.env` 里**除 `GITHUB_TOKEN` 外全部可选**，没填的功能自动跳过（优雅降级，不中断）。
每个变量怎么申请、怎么填，见下面的 [Configuration](#configuration) 分节指南——建议现在就把想用的 key 填好，再进 Step 3。

> `.env` 已被 gitignore，不会误提交。`setup.sh` / `doctor.sh` / 各 wrapper 启动时会自动 `source` 它，无需手动 `export`。

### Step 3 · 一次性安装（依赖 + 本地化）

```bash
bash setup.sh
```

`setup.sh` 幂等，按顺序做 4 件事，跑完屏幕会逐条打勾：

| 阶段 | 动作 | 说明 |
|---|---|---|
| 前置检查 | 探测 `python`(≥3.12)、确认 vendored 目录齐全 | 缺 `trendradar/` 或引擎脚本会直接报错让你重 clone |
| Step 1 | `pip install -r requirements.txt` | 装引擎依赖（见下「依赖清单」）；失败不中断，提示你可 `--skip-deps` 手动装 |
| Step 2 | 建 `trendradar/output/{news,rss,html}` | TrendRadar 运行时目录（gitignore） |
| Step 3 | 写 `follow-news-addons/workspace/config/` | 把 `<TRENDRADAR_PATH>` 占位符解析成仓内绝对路径填进 `file://` 信源；复制竞品 profiles 骨架（已存在则保留你填的官方源） |
| Step 4 | 冒烟验证 | import TrendRadar 主模块 + 4 个竞品脚本 `--help` |

**依赖清单**（`requirements.txt`）——两块：

- **TrendRadar 依赖（固定版本）**：`requests` / `pytz` / `PyYAML` / `fastmcp` / `websockets` / `feedparser` / `boto3` / `litellm` / `json-repair` / `tenacity`。锁版本是为了保证中文热榜模块 import 干净。
- **follow-news 引擎依赖**：`jsonschema`（建议装，缺则对应校验降级）。
- **可选依赖（默认注释掉，按需手动装）**：
  ```bash
  pip install weasyprint   # 仅当你要 PDF 周报渲染
  pip install yt-dlp       # 仅当你要抓 YouTube 播客元数据 + 转录
  ```

**常见依赖问题**：

```bash
# 国内 pip 慢 / 装不上 → 换清华镜像：
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 自己管依赖（如用 conda/venv 已装好）→ 跳过 setup 的 pip 步骤：
bash setup.sh --skip-deps
```

> `install.sh` / `update.sh` 仍可用，已转为 `setup.sh` 的薄封装（向后兼容）。
> 想隔离环境的话，先 `python -m venv .venv && source .venv/Scripts/activate`（Windows Git Bash）再跑 `setup.sh`。

### Step 4 · 验证安装

```bash
bash verify.sh    # 结构完整性：vendored 文件 + patch bake-in + 4 skill 清单 + wrapper 语法 + 模块可导入 + 入口 --help
bash doctor.sh    # 配置就绪度：读 .env，逐项报告哪些功能已就绪、缺哪个 key、怎么补
```

- **`verify.sh`** 打印 `✅ N 通过 / ❌ M 失败`；只要有 ❌ 就会以非零码退出并提示重跑 `setup.sh`。**全绿 = 安装结构完整。**
- **`doctor.sh`** 给一个 **N/4 分**（GitHub / Web 搜索 / Twitter-或-KOL-或-X-API / `PYTHONUTF8`）。**≥ 3/4 即可跑报告**；分低时它会直接给出每项的申请链接和补救建议。

### Step 5 · 试跑（命令行直接验证）

```bash
bash scripts/daily-digest.sh        # 日报：现抓 24h → /tmp/td-merged.json
bash scripts/weekly.sh              # 周报：现抓 7 天 → /tmp/td-weekly-{merged.json,.md}
bash scripts/topic-feedback.sh --query "Claude Code"   # 单事件社区反馈
bash scripts/competitor-brief.sh --product "通义灵码"   # 按需竞品调研
```

所有入口经 Git Bash + `PYTHONUTF8=1` 调用——**禁止绕过 shell wrapper 直接 `python` 调 fetcher**
（会触发 Windows GBK 编码与 `/tmp` 路径错误）。跑不出数据先回看 `doctor.sh` 的评分，多半是某个 key 没配。

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

所有配置都在 `.env`（从 `.env.example` 复制）。**除 `GITHUB_TOKEN` 外全部可选**——缺失的功能优雅降级（自动跳过，不中断）。
按下面分节逐项配；配完跑 `bash doctor.sh` 看评分（≥3/4 即可跑报告）。

### 1 · GitHub（必配）

| 变量 | 用途 | 不配的后果 |
|---|---|---|
| `GITHUB_TOKEN` | GitHub release / trending 抓取 | 匿名仅 60 req/h，23 个 repo 全 403 失败 |

获取：登录 GitHub → [Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens) →
**Generate new token (classic)** → **无需勾选任何 scope**（只读公开数据）→ 复制填入 `.env`：

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

配了 token 后限额升到 5000 req/h。

### 2 · Web 搜索（推荐，二选一）

日报/周报的 Web 搜索源需要 Brave **或** Tavily 其一；都不配则 Web 搜索段为 0 条（其他源不受影响）。

| 变量 | 用途 | 申请地址（免费额度） |
|---|---|---|
| `BRAVE_API_KEYS`（可逗号分隔多 key 轮换）或 `BRAVE_API_KEY` | Brave Search | [brave.com/search/api](https://brave.com/search/api/)（2000 query/月） |
| `TAVILY_API_KEY` | Tavily Search | [app.tavily.com](https://app.tavily.com/)（1000 query/月） |
| `WEB_SEARCH_BACKEND` | 后端选择，默认 `auto`（有哪个用哪个） | `auto` / `brave` / `tavily` |

```bash
BRAVE_API_KEYS=BSAxxxxxxxx
# 或
TAVILY_API_KEY=tvly-xxxxxxxx
WEB_SEARCH_BACKEND=auto
```

### 3 · OpenCLI（Twitter / X，推荐）

Twitter/X 抓取默认走 **OpenCLI 后端**——它复用你本机**已登录的 Chrome 会话**，零鉴权、零 API 成本，
不必申请任何 Twitter API key。CI / 无浏览器环境 / 已有 API key 的用户可改用 §3.2 的备选 API 后端。

#### 3.1 安装 OpenCLI（4 步）

1. **装可执行文件** — 从 [opencli releases](https://github.com/jackwener/opencli/releases) 下载对应平台二进制，
   放到 `PATH` 上；若不在 `PATH`，用 `OPENCLI_BIN` 指向其绝对路径。
2. **装 Chrome 扩展** — 打开 `chrome://extensions` → 开启「开发者模式」→「加载已解压的扩展程序」→ 选 opencli 包内的 `extension/` 目录。
3. **登录 X.com** — 在该 Chrome 里正常登录 [x.com](https://x.com)，保持登录态（OpenCLI 复用此会话）。
4. **在 OpenClaw 装 `jackwener/opencli` Skill** — 这样 agent 能跑 `opencli doctor`、检查浏览器桥接、协助排查登录态问题。

装完跑 `opencli doctor`，三项都显示 `[OK]` 即就绪。OpenCLI 的稳定性取决于本机浏览器扩展桥接状态。

#### 3.2 OpenCLI 环境变量（均可选，有默认值）

| 变量 | 默认 | 用途 |
|---|---|---|
| `TWITTER_API_BACKEND` | `auto` | 后端优先级 `auto`（opencli > getxapi > twitterapiio > official）；可锁定为 `opencli` |
| `OPENCLI_BIN` | PATH 上的 `opencli` | opencli 不在 PATH 时指向其绝对路径 |
| `OPENCLI_MAX_WORKERS` | 本仓建议 **3**（上限 10） | OpenCLI 并发数；调低更稳，调高更快但易触发风控 |
| `OPENCLI_CLOSE_TABS_AFTER_RUN` | `1` | 抓取后关闭本次新建的 X/Twitter 标签页 |
| `OPENCLI_CLOSE_CHROME_WINDOWS_AFTER_RUN` | `1`（macOS） | 关闭 OpenCLI 本次打开的 Chrome 自动化窗口（不关执行前已存在的窗口） |
| `OPENCLI_BROWSER_SESSION` | `follow-news` | 浏览器会话名（OpenCLI 1.8.0+）；本仓可设 `ai-pulse` 隔离会话 |

#### 3.3 备选：付费 Twitter API（OpenCLI 不可用时）

无法用 OpenCLI（如 CI 环境）时，配下面任一 API key，后端会按 `auto` 优先级自动回退：

| 变量 | 后端 |
|---|---|
| `GETX_API_KEY` | GetXAPI |
| `TWITTERAPI_IO_KEY` | twitterapi.io |
| `X_BEARER_TOKEN` | 官方 X API v2 |

### 4 · 竞品 KOL 多平台凭证（可选）

竞品调研 / 单事件反馈的 KOL 段按平台采集，**缺哪个平台的凭证就跳过哪个平台**（B站匿名可用，无需凭证）：

| 变量 | 平台 |
|---|---|
| `BILIBILI_COOKIE` | B站（匿名可用，配 cookie 更稳） |
| `ZHIHU_COOKIE` | 知乎 |
| `JIKE_ACCESS_TOKEN` | 即刻 |
| `WEIXIN_SEARCH_URL` / `WEIXIN_API_KEY` | 公众号 |

### 5 · 其他（可选）

| 变量 | 用途 |
|---|---|
| `HTTPS_PROXY` / `HTTP_PROXY` | 国内访问 github / twitter / x.com 走代理 |
| `ENABLE_KOL_BLOGS` | AI KOL 深度博客 11 个（默认开启） |
| `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` | **Windows 上必须保留**（避免 GBK 乱码） |

完整选项与注释见 [.env.example](.env.example)。

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

> 每个 skill 的 agent 写完报告后，除对话展示外**还会把最终报告落地为 `reports/<skill-id>-…-<日期>.md`**——
> 一个**飞书云文档兼容**的 Markdown 文件（新建飞书文档 → 粘贴即渲染）。格式规范见
> [`follow-news-addons/references/templates/feishu.md`](follow-news-addons/references/templates/feishu.md)。
> `reports/` 是运行时产物目录，已 gitignore、不入库。

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
