# AGENTS.md —— 引导用户安装配置 ai-pulse 的 agent 指南

> **读者是 agent，不是终端用户。** 另一个 agent 打开本仓时，读本文即可**一步步引导用户把 ai-pulse 从零装到能跑**。
> 深度细节（每个 key 怎么申请、每个变量什么含义）在 [`README.md`](README.md) 的 [安装](README.md#安装--从零到能跑) 与 [Configuration](README.md#configuration) 两节——本文给你**流程、决策点、检查点、排错**，需要展开时把用户指向 README 对应锚点即可。

---

## 你的任务

把用户领过 6 步安装流程，最终达成**完成标准**：

1. `bash verify.sh` 全绿（`✅ N 通过 / ❌ 0 失败`）——结构完整。
2. `bash doctor.sh` ≥ **3/4** 分——配置就绪。
3. 至少一条 `bash scripts/*.sh` 试跑能出数据。

达成即引导结束；未达成则按下面的**排错**定位卡点，逐项补齐。

---

## 硬约束（任何时候都不能违反）

- **Windows 必须用 Git Bash / WSL / msys2** 跑所有 `.sh`——**绝不**让用户用 PowerShell / CMD 直接跑（会踩 `/tmp` 路径解释与 GBK 编码坑）。先确认用户在哪种 shell 里。
- **所有入口经 shell wrapper + `PYTHONUTF8=1`**——**禁止**引导用户绕过 wrapper 直接 `python` 调 fetcher（触发 Windows GBK 乱码与 `/tmp` 路径错误）。
- **`.env` 绝不提交、绝不外传**——它已被 gitignore；不要把用户的 key 回显到会话摘要或写进任何入库文件。
- **优雅降级是设计，不是 bug**——除 `GITHUB_TOKEN` 外所有 key 可选，缺失功能自动跳过。看到 “某源 0 条 / skip” 先判断是不是“该 key 没配”，别当故障修。
- **绝不为凑数编造**——competitor 官方源、报告链接一律用 web 核实源 / 数据 `url` 原值；**宁可留空也不填猜测 URL**。

---

## 引导流程（对应 README Step 0–6）

每步给出：**让用户做什么 → 你怎么验证 → 决策/岔路**。

### Step 0 · 前置环境（缺一不可）

让用户在目标 shell 里跑：

```bash
python --version     # 需 ≥ 3.12（TrendRadar 硬性要求，低于此中文热榜模块无法 import）
git --version
bash --version       # Windows 上应显示 Git Bash / msys2 的 bash
```

- **验证**：三条都成功且 `python` ≥ 3.12。
- **岔路**：
  - `python` 报错或 < 3.12 → 指向 [python.org](https://www.python.org/downloads/) 装 3.12+。提醒 Windows 上 `python3` 常是微软商店占位 shim，`setup.sh` 会**优先用 `python`** 再退 `python3`。
  - `bash` 显示的是系统自带而非 Git Bash（Windows）→ 让用户改在 Git Bash 里操作。

### Step 1 · 克隆 + 进目录

```bash
git clone https://github.com/huudage/ai-pulse.git
cd ai-pulse
```

本仓自包含（follow-news 引擎 vendored 在 `follow-news-addons/`，TrendRadar 在 `trendradar/`）——**无需克隆任何兄弟仓、无 patch 步骤**。若用户已在仓内，跳过。

### Step 2 · 建 `.env`

```bash
cp .env.example .env
```

- 让用户**至少填 `GITHUB_TOKEN`**（唯一必配项）。其余按需，见下面的 **配置决策树**。
- 提醒：`.env` 已 gitignore；`setup.sh` / `doctor.sh` / 各 wrapper 启动会自动 `source`，无需手动 `export`。
- **此时就把想用的 key 填好再进 Step 3**，省得来回。

### Step 3 · 一次性安装

```bash
bash setup.sh
```

幂等，按序做 4 件事（前置检查 → `pip install -r requirements.txt` → 建 `trendradar/output/{news,rss,html}` → 写 `follow-news-addons/workspace/config/`（解析 `<TRENDRADAR_PATH>` 占位符 + 复制竞品 profiles 骨架）→ 冒烟验证）。

- **验证**：屏幕逐条打勾、无红色报错退出。
- **岔路**：
  - `pip install` 失败（网络慢/装不上）→ 让用户换清华镜像重跑：
    `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`，或用户自管依赖时 `bash setup.sh --skip-deps`。
  - 缺 `trendradar/` 或引擎脚本报错 → 让用户重新 `git clone`（仓不完整）。
  - 需要 PDF 周报 / YouTube 播客 → 可选依赖手动装：`pip install weasyprint` / `pip install yt-dlp`。
  - 想隔离环境 → 先 `python -m venv .venv && source .venv/Scripts/activate`（Windows Git Bash）再跑 `setup.sh`。

### Step 4 · 验证（两把尺子，都要跑）

```bash
bash verify.sh    # 结构完整性
bash doctor.sh    # 配置就绪度
```

- **`verify.sh`** → 见下面「读 verify.sh」。有 ❌ 先修结构，别急着跑报告。
- **`doctor.sh`** → 见下面「读 doctor.sh」。据 N/4 分和缺项提示引导用户补 key。

### Step 5 · 试跑（出数据即成功）

```bash
bash scripts/daily-digest.sh                          # 日报（现抓 24h）
bash scripts/weekly.sh                                # 周报（现抓 7 天）
bash scripts/topic-feedback.sh --query "Claude Code"  # 单事件社区反馈
bash scripts/competitor-brief.sh --product "通义灵码"  # 按需竞品调研
```

跑不出数据 → 先回看 `doctor.sh` 评分，多半是某个 key 没配（尤其 `GITHUB_TOKEN` / Web 搜索 / OpenCLI）。

### Step 6 · 部署为 OpenClaw skills（可选）

```bash
bash deploy-skill.sh          # 复制共享引擎 + fan-out 4 个 skill 到 ~/.openclaw/skills/
```

部署后用户可在 OpenClaw 里直接说「本周 AI 圈周报」「调研一下 Manus」「社区对 Claude Code 怎么看」触发。命令行 `scripts/*.sh` 不部署也能用。

---

## 配置决策树（引导用户填 `.env`）

按重要度排序，逐项帮用户判断填不填、怎么填。展开申请步骤时指向 [README Configuration](README.md#configuration)。

| 项 | 必要性 | 引导话术要点 |
|---|---|---|
| `GITHUB_TOKEN` | **必配** | 不配则匿名 60 req/h、GitHub release/trending 全 403。classic token，**无需勾任何 scope**（只读 public）。配后升到 5000 req/h。 |
| Web 搜索（`BRAVE_API_KEYS` 或 `TAVILY_API_KEY`） | 推荐，二选一 | 都不配则 Web 搜索段 0 条，其他源不受影响。Brave 2000 q/月、Tavily 1000 q/月，均免费。`WEB_SEARCH_BACKEND=auto` 有哪个用哪个。 |
| Twitter/X（OpenCLI） | 推荐 | 默认 OpenCLI 后端，复用本机已登录 Chrome，零鉴权零成本。**四步**：装二进制 → 装 Chrome 扩展 → 登录 x.com → 在 OpenClaw 装 `jackwener/opencli` Skill → `opencli doctor` 三项全 `[OK]`。本仓建议 `OPENCLI_MAX_WORKERS=3`（调低更稳）。 |
| Twitter/X（付费 API 备选） | 仅 OpenCLI 不可用时 | CI/无浏览器环境才用：`GETX_API_KEY` / `TWITTERAPI_IO_KEY` / `X_BEARER_TOKEN` 任一，`auto` 会自动回退。 |
| 竞品 KOL 凭证 | 可选，按平台 | 缺哪个平台凭证就跳过哪个平台。B站匿名可用；`ZHIHU_COOKIE` / `JIKE_ACCESS_TOKEN` / `WEIXIN_SEARCH_URL`(+`WEIXIN_API_KEY`) 按需。 |
| `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` | **Windows 必须保留** | `.env.example` 已带，别让用户删。 |
| `HTTPS_PROXY` / `HTTP_PROXY` | 按需 | 国内访问 github/twitter/x.com 慢时配。 |

> 竞品官方源清单在 `follow-news-addons/workspace/config/competitor-profiles.json`（`setup.sh` 复制骨架，已存在则保留用户填的）。补全各产品 `official_sources` 后竞品调研才有官方数据；**无源竞品留 null + `_source_note` 说明，不猜 URL**。

---

## 怎么读 `verify.sh` 输出

- 末行 `✅ N 通过 / ❌ M 失败`。**M > 0 → 非零退出**，说明结构不完整（vendored 文件缺失 / patch 未 bake-in / skill 清单缺 `<ENGINE_DIR>` 占位 / 模块 import 失败 / 入口 `--help` 挂）。
- **处理**：先看红色行具体缺什么。多数情况让用户**重跑 `bash setup.sh`**；若报缺 `trendradar/` 等 vendored 目录，则仓克隆不完整，重新 clone。
- **verify 全绿是跑报告的前提**——结构没通就别进 Step 5。

## 怎么读 `doctor.sh` 输出

- 给一个 **N/4 分**：GitHub / Web 搜索 / Twitter(OpenCLI 或 KOL 或 X-API) / `PYTHONUTF8`。
- **≥ 3/4 即可跑报告**。分低时 doctor 会**直接打印每项缺什么 + 申请链接 + 补救建议**——照着念给用户即可。
- OpenCLI 项：doctor 会探测二进制 + 跑 `opencli doctor` 找 “Everything looks good”；也会在 `OPENCLI_MAX_WORKERS > 5` 时告警（建议降到 3）。

---

## 常见故障 → 排查（对应 README Troubleshooting）

| 症状 | 你该引导的动作 |
|---|---|
| `pip install` 失败 | 确认 Python ≥ 3.12；国内换清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。 |
| GitHub release 全失败 / 403 | 没设 `GITHUB_TOKEN`——让用户补（Configuration §1）。 |
| Web 搜索 0 items | 没设 `BRAVE_API_KEYS` 或 `TAVILY_API_KEY`——二选一补。 |
| Twitter 0 items | OpenCLI 没装 / 扩展未连 / 未登录 x.com——让用户跑 `opencli doctor` 看三项状态。 |
| Windows `'gbk' codec can't decode` | 确认 `.env` 有 `PYTHONUTF8=1`，且**通过 shell wrapper 调用**（别绕过直接 `python`）。 |
| HN/V2EX 评论抓不到 | 网络到 `hacker-news.firebaseio.com` / `sov2ex.com` / `v2ex.com` 不通——可能要代理。 |
| 竞品 KOL 某平台无数据 | 该平台凭证未配 → 自动跳过，**属预期**，不是故障。 |
| 深挖哪一路失败 | `python follow-news-addons/scripts/run-pipeline.py --hours 24 --verbose` 看逐源结果。 |

---

## 引导时的边界

- **不替用户填 key**：key 是用户私有的，引导用户自己填进 `.env`，不要求用户把 key 贴进会话；若已贴，别回显、别写入任何入库文件。
- **不擅自提交**：装配过程只改用户本地 `.env` 与运行时产物（`workspace/config/`、`trendradar/output/`、`reports/` 均 gitignore）。不 `git commit` / `git push`，除非用户明确要求。
- **不猜链接/不编数据**：竞品官方源无可核实 URL 就留空 + 备注；报告链接只用数据 `url` 原值。
- **降级如实说**：某源 skip/0 条时，如实告诉用户“是缺 X key 导致跳过”还是“确实没搜到”，不掩盖也不当 bug 修。
