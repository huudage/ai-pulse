## 仓库布局（自包含单仓多-skill bundle — v2 vendored）

ai-pulse 是**单仓多-skill bundle**：`git clone` + 一次 `setup.sh` 即获完整功能，无外部上游 clone、无 patch 步骤。
本仓既是「共享引擎」也是 4 个 skill 的来源。

- `trendradar/` — vendored 的 TrendRadar 中文热榜爬虫（`python -m trendradar` 抓取；
  `python -m trendradar.report.weekly_export` 旁路导出 7 天中文 RSS）。`output/` 是运行时状态（gitignore，仅留 `.gitkeep` 骨架）。
- `follow-news-addons/` — vendored 的 follow-news 聚合引擎 + ai-pulse 自有脚本：
  - `scripts/` — 引擎闭包（run-pipeline / config_loader / merge-sources / fetch-* / summarize-merged）+ 竞品监测脚本（weekly-feedback / fetch-competitor-* / competitor-brief / topic-feedback）。脚本经 `Path(__file__).parent` 解析同级，**勿移动 / 勿拆分**（拆分会破坏相对解析与单一 SQLite）。
  - `config/defaults/` — 引擎基础配置（run-pipeline 解析 `../config/defaults`）。
  - `workspace-config/` — ai-pulse 自定义信源 + 竞品 profiles 模板（含 `<TRENDRADAR_PATH>` 占位符）。
  - `workspace/config/` — `setup.sh` 解析占位符后的本地化产物（gitignore）。
  - `references/digest-prompt.md` + `references/prompts/` — agent 撰写日报/周报/竞品调研/单事件反馈用的 prompt 模板。
- `scripts/` — 入口 wrapper（共享引擎 dev 模式直接跑）：
  - `daily.sh` — **可选累积 cron**（TrendRadar 快照攒 SQLite）：周报 `--fetch-now` 自给自足，跑它只为给周报中文热榜段补 7 天厚度，本身不是 skill、非周报前置。
  - `daily-digest.sh`（日报）/ `weekly.sh`（周报）/ `topic-feedback.sh`（单事件）/ `competitor-brief.sh`（竞品调研）。
- `skills/` — 4 个 skill 清单（部署模板），各含一个 SKILL.md（路由规则 + `<ENGINE_DIR>` 占位符）：
  `ai-pulse-{daily,weekly,topic,brief}`。`deploy-skill.sh` 把共享引擎复制为 `~/.openclaw/skills/ai-pulse-engine/`
  （**无 SKILL.md ⇒ 不被注册**），并 fan-out 这 4 个兄弟 skill 目录（替换 `<ENGINE_DIR>` 为引擎绝对路径）。
  OpenClaw 平铺扫描 `<skills>/<name>/SKILL.md`（一层），故 4 个 skill = 4 个兄弟顶层目录。
- 根 `SKILL.md` — bundle 总览（列 4 个 skill + 共享安装），**不**作为 skill 清单部署。

## 安装与运行

```bash
bash setup.sh                # pip install + 本地化（解析 file:// 占位符 + 建 output 目录），无 clone
bash verify.sh               # 校验 vendored 文件 + 4 skill 清单 + wrapper + 模块可导入 + 入口 --help
bash doctor.sh               # 体检 .env API key
bash scripts/daily.sh        # 可选：累积中文热榜厚度（非周报前置）
bash scripts/daily-digest.sh # 日报：现抓 24h → /tmp/td-merged.json
bash scripts/weekly.sh       # 周报：现抓 7 天 → /tmp/td-weekly-{merged.json,.md}
bash scripts/topic-feedback.sh --query "…"      # 单事件社区反馈
bash scripts/competitor-brief.sh --product "…"  # 按需竞品调研
bash deploy-skill.sh         # fan-out 共享引擎 + 4 个 skill 到 ~/.openclaw/skills/（可选）
```

`install.sh` / `update.sh` 已转为 `setup.sh` 的薄封装（向后兼容）。

## 治理

核心原则（约束所有改动，优先于个人习惯）：
- **Vendored 上游 + 溯源**：上游集成树直接 commit 进本仓并可编辑（`trendradar/`、`follow-news-addons/`）；
  `setup.sh` 只做本地化，不 clone/patch。差异记录在 `patches/*/upstream.patch` + `follow-news-addons/PATCHES.md`
  + PINNED SHA，作为可审计溯源——build 时**不再应用**，仅供维护者升级上游时重新 vendor。
- **双脑分工——数据面零 LLM**：采集/去重/评分/Tier 预标签全由确定性脚本完成，不调任何 LLM API；语义工作交给 OpenClaw agent。
- **脚本与 prompt 同步纪律**：改 Tier 白名单 / 检索源时，脚本侧（`weekly-feedback.py` / `topic-feedback.py`）
  与 prompt 侧（`references/prompts/*.md`）必须同步改，否则行为不可预期。
- **优雅降级**：`.env` 中所有 API key 均可选；缺失功能自动跳过而非中断。
- Python ≥ 3.12 为硬性要求。改 vendored 树须同步刷新溯源记录。
