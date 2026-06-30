# 飞书云文档兼容 Markdown 输出模板

4 个 skill（日报 / 周报 / 单事件 / 竞品调研）的 agent 写完报告后，**除对话展示外，还要把最终报告另存为一个 `.md` 文件**，
该文件粘进飞书云文档（新建文档 → 粘贴 Markdown）能正确渲染。本文件是该输出文件的**权威规范**。

---

## 1. 文件名与落盘位置

- 目录固定 `reports/`（仓根下），写文件前先 `mkdir -p reports`（`reports/` 已 gitignore，是开箱即用产物目录，不入库）。
- 命名：`reports/<skill-id>-[<slug>-]<YYYY-MM-DD>.md`
  - `<skill-id>` ∈ `ai-pulse-daily` / `ai-pulse-weekly` / `ai-pulse-topic` / `ai-pulse-brief`。
  - `<YYYY-MM-DD>` 为报告生成当天日期。
  - `<slug>`：**仅 topic / brief 带**，由查询词/产品名小写化、空格与符号转连字符（如 `Claude Code` → `claude-code`，`通义灵码` → 保留中文亦可，建议转拼音或英文别名优先）。daily / weekly **不带 slug**。
- 示例：
  - `reports/ai-pulse-daily-2026-06-30.md`
  - `reports/ai-pulse-weekly-2026-06-30.md`
  - `reports/ai-pulse-topic-claude-code-2026-06-30.md`
  - `reports/ai-pulse-brief-tongyi-lingma-2026-06-30.md`
- 写完后**把文件相对路径告知用户**（如「已写入 `reports/ai-pulse-weekly-2026-06-30.md`」）。

---

## 2. 飞书兼容 Markdown 子集

飞书云文档支持标准 Markdown 的一个子集。**只用下列语法**：

| 允许 ✅ | 示例 |
|---|---|
| ATX 标题（`#`～`######`） | `## 模型动态` |
| GFM 表格 | `| 列 | 列 |` + 分隔行 |
| 有序 / 无序列表（**最多 2 层缩进**） | `- 项` / `1. 项` |
| 行内链接 | `[标题](https://example.com)` |
| 粗体 / 斜体 / 行内代码 | `**粗**` `*斜*` `` `code` `` |
| 引用 | `> 引用一段社区评论` |
| 围栏代码块 | ```` ```bash ```` |
| 分隔线 | `---` |
| emoji（直接字符） | 🧠 🤖 👍 👎 ⚖️ 🇨🇳 |

**禁止 ❌**（飞书渲染异常或被吞）：

- 裸 HTML 标签（`<div>` `<br>` `<span>` 等）——email 模板那套内联样式**不要**用在这里。
- 尖括号自动链接 `<https://...>`——一律写成 `[文字](https://...)`。
- 三层及以上的深层嵌套列表。
- 脚注 `[^1]`、任务列表 checkbox `- [ ]`、定义列表。
- 表格单元格内放复杂结构（换行/列表）——单元格只放纯文本 + 行内链接。

---

## 3. 链接纪律（硬约束）

- **只引用数据里真实存在的 `url`**（merged.json / weekly-merged.json / sources.*.results 的 `url`、官方源数据的链接）。
- **绝不编造、猜测、补全 URL**。某条目无链接就不写链接，宁可留空。
- 引用社区评论原文用 `>` 引用块，附其 `url`；无 `likes`/计数数据时不杜撰数字。

---

## 4. 最小骨架示例

```markdown
# AI 圈周报 — 2026-06-30

> 本周 AI 圈一句话总览（按互动热度选题，按社区情绪分组）。

---

## 🧠 模型

### OpenAI 发布 GPT-X（Tier 1）
- **是什么**：一句话。
- **为何重要**：一句话。
- **社区反应**：
  > 引用一条真实 HN 评论原文。 — [来源](https://news.ycombinator.com/item?id=123)

| 维度 | 要点 |
|---|---|
| 能力 | … |
| 定价 | … |

## 🤖 Agent 产品

- **某产品更新** — 一句话简述。[来源](https://example.com)

## 🇨🇳 中文社区视角

- 中文热榜/V2EX 相关讨论一句话。[来源](https://www.v2ex.com/t/123)

---

📊 数据来源：RSS / HN / GitHub / 中文热榜 / V2EX ｜ 去重后 N 条
```

各 skill 的具体段落结构以其 prompt 模板（`references/digest-prompt.md` / `references/prompts/*.md`）为准，
本模板只约束**落盘文件名 + 飞书兼容语法子集 + 链接纪律**。
