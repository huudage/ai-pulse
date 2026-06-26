---
name: ai-pulse-weekly
version: 2.0.0
description: AI 圈社区情绪周报。现抓 7 天英文 RSS/HN + 中文热榜，按互动热度（HN/Twitter/中文热榜/多源覆盖）排序选题，产出结构化周报数据供 agent 按社区情绪分组（👍/👎/⚖️/🇨🇳）撰写。触发："周报" / "weekly" / "本周" / "AI 圈周报"。竞品官方源 + KOL 已迁至「按需竞品调研」skill，周报不再承载竞品段。属 ai-pulse 多-skill bundle，共享 ai-pulse-engine。
---

# AI Pulse · 周报（weekly community-sentiment digest）

ai-pulse bundle 的「周报」skill。共享引擎在 `<ENGINE_DIR>`（部署后为 `ai-pulse-engine/`），
数据零 LLM 机械产出；周报由你（agent）按 prompt 撰写。

## 触发

"周报" / "weekly" / "本周" / "this week" / "AI 圈周报"，或 "AI 社区对 <事件> 怎么看"（完整周报维度）。
（竞品官方动态/方向调研请走「按需竞品调研」skill，不在本周报。）

## 执行

```bash
bash <ENGINE_DIR>/scripts/weekly.sh
```

内部跑 `weekly-feedback.py --fetch-now`，产出
`/tmp/td-weekly-merged.json`（结构化）+ `/tmp/td-weekly.md`（渲染稿）。
**周报自给自足**——`--fetch-now` 触发时现抓 7 天英文源并现爬 TrendRadar 今日快照，不依赖日报或任何前置脚本。
入口经 Git Bash + `PYTHONUTF8=1`，**禁止绕过 shell wrapper**。

## 可选增强：中文热榜 7 天厚度

TrendRadar 热榜是不可回溯的快照，`--fetch-now` 只能现爬到「今天」。若想让周报的**中文热榜段**有 7 天厚度，
可（非必须）按日挂 `bash <ENGINE_DIR>/scripts/daily.sh` 让快照累积进 SQLite。
不跑也不影响周报产出——只是中文热榜段会偏薄，脚本会照实标注覆盖度。

## 撰写

- **CRITICAL — 先读 `<ENGINE_DIR>/follow-news-addons/references/prompts/competitor-monitor.md` 并严格遵循。**
  该模板定义社区讨论量入选门槛、按 `_engagement` 降序的选题规则、按情绪分组（👍/👎/⚖️/🇨🇳）撰写、
  🌐 跨事件社区反馈大章（floating_threads）、最终报告结构。
- 选题靠**互动热度**（`_engagement`：HN points+评论 / Twitter 互动 / 中文热榜排名 / 多源覆盖），不靠厂商白名单；
  厂商正则仅作 ×1.25 加成，`_tier` 仅作参考提示，不决定入选。
- 引用 `enriched_comments` / `floating_threads` 里的逐字评论（带 👍 数）；为空写"本周暂无显著社区讨论"，**不编造**。
- **不要编造链接**——只用数据里的 `url` 字段。信源缺失时优雅降级，照实说明覆盖度。
