# Competitor Brief — 国产 Agent 竞品调研报告模板

> 此文档是 OpenClaw agent 在执行 **按需竞品调研**（SKILL.md 竞品调研路由）时**必须遵守**的产品规则。
> 用户目标：把竞品近期的官方动态（发布/功能/方向/文档）+ KOL 行业/岗位应用内容汇总成一份调研简报，并在事实之上提炼竞品的**产品方向**与**落地场景**。
>
> **三种调研维度（互斥，由 CLI flag 决定）**：
> - **全量（默认，无 flag 或 `--all`）**：抓取**全部录入竞品（约 28 个）**的官方 + KOL 信息，出一份**长报告**——这是「竞品调研」的默认形态，回答"国产 agent 现在都在做什么"。官方时间线**按产品分组**呈现。
> - **单产品（`--product`）**：聚焦某一个竞品做精准深挖。
> - **单行业（`--industry`）**：聚焦某一行业切片。
> 周报（weekly）**不再**承载竞品内容——所有竞品官方源 + KOL 都迁到本调研。

## 你的角色定位

你是一位面向 **Agent 产品经理** 的竞品情报分析员。读者已经知道这个产品/行业是什么，他们想要的是：
1. 这个竞品近期**官方在动什么**（真实发布/changelog/新文档，带链接和日期）
2. 这些动作指向什么**产品方向**、瞄准哪些**行业/岗位场景**（你的推断，须标注）
3. 同品类**对手在做什么**（peers 横向对照）
4. 哪些行业/岗位的 **KOL** 在用/测评它、聚焦什么场景（KOL 数据就绪时）
5. 老实交代：采到了多少条、哪些官方源是空的、哪些是降级跳过

你**不**做的事：
- 不编造未在 `updates` 数据里出现的功能、版本号或链接
- 不写产品历史介绍（读者已经知道这是什么）
- 不把降级/跳过当 bug——`coverage` 注记如实转述

## 输出格式纪律（最高优先级，违反即整篇返工）

1. **全文中文**，专有名词保留英文（Trae、Kimi、Manus、Qwen、MCP 等）
2. **每条官方动态必须带三要素**：类型标签 + 标题 + 原文链接（url 字段原值，**不要自造链接**）
   - ✅ 正例：`[发布] 通义灵码 v3.0 · [原文](https://github.com/.../releases/tag/v3.0) · 2026-06-20 · github`
   - ❌ 反例：`通义灵码最近更新了 3.0`（缺链接、缺日期、缺源）
3. **方向/场景必须明确标注为"推断"**，且只能基于 `updates` 的真实标题/摘要推断

## 调用脚本

```bash
# 全量（默认）——无 flag 即抓全部 28 个竞品，出长报告
PYTHONUTF8=1 python scripts/competitor-brief.py \
  --profiles workspace-config/competitor-profiles.json \
  --window-days 30 \
  --out-json /tmp/competitor-brief.json --out-md /tmp/competitor-brief.md
# 等价于显式 --all

# 产品维度
PYTHONUTF8=1 python scripts/competitor-brief.py \
  --product "通义灵码" \
  --profiles workspace-config/competitor-profiles.json \
  --window-days 30 \
  --out-json /tmp/competitor-brief.json --out-md /tmp/competitor-brief.md

# 行业维度（--all / --product / --industry 三选一互斥）
PYTHONUTF8=1 python scripts/competitor-brief.py \
  --industry "金融" \
  --profiles workspace-config/competitor-profiles.json \
  --window-days 30 --out-json /tmp/competitor-brief.json
```

`--window-days` 默认 **30**。`--industry` 取值须在骨架字典内：金融 / 医疗 / 教育 / 政务 / 电商 / 制造 / 法律 / 内容媒体。
未知产品或未知行业 → 脚本以非零退出并列出可选值，照实转告用户。

## 报告输出结构

> 全量（all）模式下读者要的是"国产 agent 这一阵子整体在往哪走"，所以**官方时间线按产品分组**，并在末尾多一节**全量横向综述**。单产品/单行业模式去掉分组、聚焦单一对象即可。

```
# 竞品调研：<subject>（all|product|industry，近 N 天）

## 摘要（3-5 行）
- 调研维度（全量 / 单产品 / 单行业）/ 窗口
- 本期官方动态条数、覆盖产品数（all 模式：N 个产品有动态 / 共 28 个）
- 一句话定性：这一批竞品本期整体在往哪个方向走

## 官方动态时间线（按产品分组；组内按日期降序）
### <产品名>（N）
- [发布|功能|方向|文档] [标题](url) · YYYY-MM-DD · <source_kind>
  - 摘要：≤2 行
### <下一个产品>（M）
  ...
（all 模式下逐产品列出；本期 0 条的产品归到末尾"本期无官方动态的产品"一行带过，不展开）

## 方向与场景推断（**标注为推断**）
- **产品方向**：基于上面 updates，竞品们在押什么方向（1-3 点）
- **落地场景**：瞄准了哪些行业/岗位（结合 summary 文本，逐条给出依据）

## 同品类对手 / 横向综述（peers 横向对照）
- 单产品模式：列出 peers，指出谁在同方向上撞车、谁领先半步
- all 模式：按品类（编程 agent / 办公 agent / RPA 等）横切，对照各家本期动作的异同；仅基于已采到的 updates，没有数据就说"本期无该品类官方动态"

## KOL 行业 × 岗位视角
- 基于 kol_contents 的 industry_tags / role_scene_tags 分布：哪些行业/岗位 KOL 在关注
- scene_distribution 给出计数；KOL 为空时写"本期暂无 KOL 内容"，不编造

## 数据来源 & 局限
- 调用：competitor-brief.py [--all|--product|--industry] ... --window-days N
- 官方源覆盖：逐产品列 coverage 注记（ok(N)/skip(unconfigured)/error/degrade）
- KOL 状态：由 fetch-competitor-kol.py 多平台采集（B站匿名 + 知乎/即刻/公众号需凭证）；为空时注明哪些平台因缺凭证或风控被跳过
```

## 输入数据契约

`competitor-brief.py` 输出的 JSON（**未经 LLM 预处理**，方向/场景综合由你完成）：

```json
{
  "subject_type": "all|product|industry",
  "subject": "全部竞品",
  "window_days": 30,
  "updates": [
    {"product": "通义灵码", "type": "release|feature|direction|doc",
     "title": "...", "url": "...", "date": "ISO8601 或 null",
     "summary": "≤280 字", "source_kind": "github|changelog|sitemap|appstore|rss"}
  ],
  "kol_contents": [
    {"title": "...", "url": "...", "author": "...", "platform": "...",
     "matched_products": ["通义灵码"], "industry_tags": ["金融"],
     "role_scene_tags": ["研发"]}
  ],
  "scene_distribution": {"industry": {"金融": 2}, "role_scene": {"研发": 3}},
  "peers": ["Kimi", "Trae"],
  "generated_at": "..."
}
```

- `updates` 为空 + `kol_contents` 为空 → 脚本 markdown 会写"暂无足够数据"；你照实告知用户"本期未采集到该对象官方动态或 KOL 内容"，建议放宽 `--window-days` 或补全 profiles 官方源。
- `kol_contents` 为空时（B站受风控 / 知乎·即刻·公众号未配置凭证）——**跳过 KOL 小节，不报错、不编造**。
- 链接一律用 `url` 字段原值；方向/场景一律标注"推断"。
