---
name: ai-pulse-topic
version: 2.0.0
description: 单事件社区反馈。针对单个事件/话题（如 "Cursor agent mode"、某次发布）现抓多源社区反应（HN/V2EX 评论原文 + 中文热榜 + KOL B站/知乎/即刻/公众号 + Twitter best-effort），产出结构化数据供 agent 解读社区舆论，不出完整周报。触发：针对单个事件/话题问社区反应。属 ai-pulse 多-skill bundle，共享 ai-pulse-engine。
---

# AI Pulse · 单事件社区反馈（single-topic feedback）

ai-pulse bundle 的「单事件社区反馈」skill。共享引擎在 `<ENGINE_DIR>`（部署后为 `ai-pulse-engine/`），
数据零 LLM 机械产出；解读由你（agent）按 prompt 完成。

## 触发

针对**单个**事件/话题问社区反应（"社区对 X 怎么看"、"X 发布后大家反响如何"），但不要完整周报。

## 执行

```bash
bash <ENGINE_DIR>/scripts/topic-feedback.sh --query "Cursor agent mode"
# 可选：--days 14 / --no-comments（跳过 HN/V2EX 评论原文）/ --no-cache
```

透传参数给 `topic-feedback.py`（至少给 `--query`），未指定时自动注入
`--trendradar-dir` / `--output /tmp/td-topic.json` / `--markdown /tmp/td-topic.md`。
入口经 Git Bash + `PYTHONUTF8=1`，**禁止绕过 shell wrapper**。

源覆盖：HN（评论原文，默认抓 top5×5）、V2EX（零鉴权评论原文）、TrendRadar 中文热榜、
KOL（B站匿名 + 知乎/即刻/公众号需 `.env` 凭证，缺则 coverage=skip）、Twitter（best-effort）。

## 解读

- **CRITICAL — 先读 `<ENGINE_DIR>/follow-news-addons/references/prompts/topic-feedback.md` 并严格遵循其输入数据契约。**
- **不要编造链接**——只用数据里的 `url` 字段。
- 某源无结果时照实说明（如"该话题在中文热榜暂无命中"），不编造、不报错中断。
