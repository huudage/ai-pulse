---
name: ai-pulse-daily
version: 2.0.0
description: AI 圈每日新闻摘要（日报）。follow-news 聚合引擎现抓最近 24h 英文 RSS/HN/GitHub/Web/播客 + 中文热榜，产出结构化数据供 agent 撰写日报。触发："日报" / "daily" / "今天 AI 圈有什么" / "今日动态"。属 ai-pulse 多-skill bundle，共享 ai-pulse-engine。
---

# AI Pulse · 日报（daily news digest）

ai-pulse bundle 的「日报」skill。共享引擎在 `<ENGINE_DIR>`（部署后为 `ai-pulse-engine/`），
数据由确定性脚本机械产出，**零 LLM**；日报由你（agent）按 prompt 撰写。

## 触发

"日报" / "daily" / "今天/今日 AI 圈有什么" / "今日动态"。

## 执行

```bash
bash <ENGINE_DIR>/scripts/daily-digest.sh
```

内部跑 `run-pipeline.py --hours 24 --freshness pd`（现抓 24h）→ `summarize-merged.py`，
产出 `/tmp/td-merged.json`。所有入口经 Git Bash + `PYTHONUTF8=1`，**禁止绕过 shell wrapper 直接 `python` 调 fetcher**。

## 撰写

- **CRITICAL — 先读 `<ENGINE_DIR>/follow-news-addons/references/digest-prompt.md` 并严格遵循。**
  该模板定义日报结构、命名主体（Named-Subject）段规则。
- 按需用 `<ENGINE_DIR>/follow-news-addons/references/templates/{chat,discord,email,pdf}.md` 渲染。
- **不要编造链接**——只用数据里的 `url` 字段。
- 信源缺失（API key 未配 / 抓取失败）时优雅降级，照实说明覆盖度，不报错中断。
- **输出报告文件**：写完后按 `<ENGINE_DIR>/follow-news-addons/references/templates/feishu.md` 规范，
  把最终报告另存为 `reports/ai-pulse-daily-<YYYY-MM-DD>.md`（飞书云文档兼容，先 `mkdir -p reports`），并把文件路径告知用户。
