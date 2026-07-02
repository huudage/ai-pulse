---
name: ai-pulse-brief
version: 2.0.0
description: 按需竞品调研。默认抓全部录入竞品（约 28 个）的官方动态 + KOL 内容出长报告；也可 --product 单产品 / --industry 单行业（金融/医疗/教育/政务/电商/制造/法律/内容媒体）精准深挖。产出结构化简报供 agent 撰写竞品方向/场景分析。触发："竞品调研"、"国产 agent 都在做什么"、"调研 <竞品>"、"<竞品>最新动态/方向"、"<行业>有哪些 agent 竞品"。属 ai-pulse 多-skill bundle，共享 ai-pulse-engine。
---

# AI Pulse · 按需竞品调研（on-demand competitor brief）

ai-pulse bundle 的「按需竞品调研」skill。共享引擎在 `<ENGINE_DIR>`（部署后为 `ai-pulse-engine/`），
数据零 LLM 机械产出；简报由你（agent）按 prompt 撰写。

> ⚠️ **执行顺序（强制，不可跳过）**：本 skill 的一切数据**只能**来自下面「第 1 步」脚本产出的 JSON。
> **必须先运行脚本、拿到 JSON，再撰写**。脚本跑出数据前，**禁止**凭训练知识 / 记忆 / 网页搜索自行编写任何竞品简报内容；
> 若本次会话还没跑过该脚本，现在立即运行。这是零-LLM 数据面与 agent 撰写面的分工底线——跳过脚本直接写 = 错误产出。

## 触发

- **全量（默认）**：泛指的「竞品调研」「国产 agent 现在都在做什么」「盘一下竞品近况」——无具体产品/行业 → 抓全部录入竞品出长报告。
- **单产品**：调研某个具体产品，如"调研一下通义灵码 / Trae / Manus 最近在做什么"、"<竞品> 最新动态/方向"。
- **单行业**："<行业>（金融/医疗/教育/政务/电商/制造/法律/内容媒体）有哪些 agent 竞品在布局"。

## 第 1 步 · 执行脚本（必须先跑，不可跳过）

`--all` / `--product` / `--industry` 三选一互斥；**无 flag 默认全量（约 28 个竞品，长报告）**。

```bash
# 全量（默认）
bash <ENGINE_DIR>/scripts/competitor-brief.sh --window-days 30

# 单产品
bash <ENGINE_DIR>/scripts/competitor-brief.sh --product "通义灵码" --window-days 30
```

行业维度改用 `--industry "金融"`（取值须在骨架字典内）。透传参数给 `competitor-brief.py`，
`--window-days` 默认 30；未指定时自动注入 `--profiles workspace/config/competitor-profiles.json` /
`--out-json /tmp/competitor-brief.json` / `--out-md /tmp/competitor-brief.md`。
入口经 Git Bash + `PYTHONUTF8=1`，**禁止绕过 shell wrapper**。

## 第 2 步 · 撰写（脚本产出 JSON 之后）

- **前置检查**：确认第 1 步脚本已在本次会话跑过并产出 `/tmp/competitor-brief.json`；没有就先回到第 1 步，**绝不跳过、绝不凭记忆/训练知识/网页搜索代替**。
- **CRITICAL — 先读 `<ENGINE_DIR>/follow-news-addons/references/prompts/competitor-brief.md` 并严格遵循。**
  该模板定义报告结构、官方动态三要素（类型+标题+链接）、**核心章节「近期功能更新 × 落地场景」（功能是事实、场景标注"推断"）**、产品方向 synthesis、数据契约。
- `updates` 与 `kol_contents` 都为空时脚本写"暂无足够数据"——照实告知并建议放宽 `--window-days`
  或补全 `<ENGINE_DIR>/follow-news-addons/workspace/config/competitor-profiles.json` 的 official_sources。
  KOL 未就绪时跳过该小节，不报错、不编造。
- **不要编造链接**——只用数据里的 `url` 字段。
- **输出报告文件**：写完后按 `<ENGINE_DIR>/follow-news-addons/references/templates/feishu.md` 规范，
  把最终报告另存为 `reports/ai-pulse-brief-[<slug>-]<YYYY-MM-DD>.md`（单产品/单行业带 `<slug>`，全量不带；飞书云文档兼容，先 `mkdir -p reports`），并把文件路径告知用户。
