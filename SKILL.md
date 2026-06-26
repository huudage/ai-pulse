---
name: ai-pulse
version: 2.0.0
description: AI 圈竞品监控 + 中文社区舆论 多-skill bundle。单仓自包含（vendored follow-news 引擎 + TrendRadar 中文热榜），git clone + setup.sh 一次即用，对外暴露 4 个 skill：日报 / 周报 / 单事件社区反馈 / 按需竞品调研。监控国产 Agent 竞品（通义灵码/Trae/Manus/WorkBuddy 等）官方动态 + 行业/岗位 KOL，聚合英文 RSS/HN + 中文热榜。
---

# AI Pulse — AI 竞品监控 / 社区舆论 多-skill bundle

**单仓多-skill bundle。** 本仓既是「共享引擎」也是 4 个 skill 的来源：
follow-news 聚合引擎 vendored 在 `follow-news-addons/`，TrendRadar 中文热榜 vendored 在 `trendradar/`，
4 个 skill 清单在 `skills/`。`git clone` + 一次 `setup.sh` 即获完整功能——无需克隆兄弟仓、无 patch 步骤。

## 4 个 skill（共享同一引擎）

| Skill | 触发 | 入口脚本 | agent 撰写用 prompt |
|---|---|---|---|
| **日报** `ai-pulse-daily` | "日报" / "daily" / "今天 AI 圈有什么" | `scripts/daily-digest.sh` | `references/digest-prompt.md` |
| **周报** `ai-pulse-weekly` | "周报" / "weekly" / "AI 圈周报" | `scripts/weekly.sh`（自给自足，现抓 7 天） | `references/prompts/competitor-monitor.md` |
| **单事件社区反馈** `ai-pulse-topic` | 针对单个事件问社区反应 | `scripts/topic-feedback.sh --query …` | `references/prompts/topic-feedback.md` |
| **按需竞品调研** `ai-pulse-brief` | "竞品调研" / "调研 <竞品>" / "<行业> agent 竞品" | `scripts/competitor-brief.sh`（无 flag=全量 / `--product` / `--industry`） | `references/prompts/competitor-brief.md` |

各 skill 的完整路由规则见 `skills/<name>/SKILL.md`。`scripts/daily.sh` 是**可选累积 cron**
（TrendRadar 快照攒 SQLite）——周报 `--fetch-now` 自给自足，跑 daily.sh 只为给中文热榜段补 7 天厚度，本身不是 skill。

## 安装（一次性，整个 bundle 共用）

```bash
bash setup.sh        # pip install + 本地化配置（解析 file:// 占位符 + 建 output 目录）
bash verify.sh       # 校验 vendored 文件齐全 + 模块可导入 + 入口 --help
bash doctor.sh       # 体检 .env API key 配置度（建议 ≥ 3/4）
```

要求 **Python ≥ 3.12**（TrendRadar 硬性要求）。API key 全部可选，缺失则对应能力优雅降级。

## 数据采集（确定性脚本，零 LLM）

```bash
bash scripts/daily.sh          # 可选累积：TrendRadar 中文热榜 → SQLite（仅为周报中文热榜段补 7 天厚度；快照不可回溯）
bash scripts/daily-digest.sh   # 日报：现抓 24h → /tmp/td-merged.json
bash scripts/weekly.sh         # 周报：现抓 7 天 RSS/HN/竞品官方源 + 拉 7 天中文热榜
bash scripts/topic-feedback.sh --query "…"      # 单事件社区反馈
bash scripts/competitor-brief.sh --product "…"  # 按需竞品调研
```

所有可执行入口经 Git Bash + `PYTHONUTF8=1` 调用——**禁止绕过 shell wrapper 直接 `python` 调 fetcher**
（会触发 Windows GBK 编码与 `/tmp` 路径错误）。数据由脚本机械产出；解读 / 撰写由各 skill 的 prompt 指引你完成。
**不要编造链接**——只用数据里的 `url` 字段。

## 部署为 OpenClaw skills

```bash
bash deploy-skill.sh   # 把共享引擎复制为 ~/.openclaw/skills/ai-pulse-engine/，
                       # 并 fan-out 4 个兄弟 skill 目录（ai-pulse-{daily,weekly,topic,brief}）
```

OpenClaw 平铺扫描 `~/.openclaw/skills/<name>/SKILL.md`（一层），故 4 个 skill 部署为 4 个兄弟顶层目录，
各自 SKILL.md 指向共享的 `ai-pulse-engine/`（引擎目录无 SKILL.md，不被注册为 skill）。

## 竞品清单配置

竞品产品与官方源在 `follow-news-addons/workspace/config/competitor-profiles.json`（`setup.sh` 复制骨架，
已存在则保留你填写的官方源）。补全各产品 `official_sources` 后竞品章才会有数据。

## 溯源（Provenance）

vendored 上游树相对 upstream GitHub 的差异记录见 `patches/*/upstream.patch` +
`follow-news-addons/PATCHES.md` + PINNED SHA（follow-news `640901d…`、TrendRadar `68db3a9…`）。
普通用户无需关心；维护者升级上游时据此重新 vendor。
