# Competitor Brief — 国产 Agent 竞品调研报告模板

> 此文档是 OpenClaw agent 在执行 **按需竞品调研**（SKILL.md 竞品调研路由）时**必须遵守**的产品规则。
> 用户目标：把竞品近期的官方动态汇总成调研简报，**核心聚焦两点——(1) 近期上线了哪些具体功能更新（新能力/新版本/新接口），(2) 这些功能瞄准哪些落地场景（行业/岗位/工作流）**。产品方向与横向对照是辅助视角，功能更新 × 落地场景才是本报告的主体价值。
>
> **三种调研维度（互斥，由 CLI flag 决定）**：
> - **全量（默认，无 flag 或 `--all`）**：抓取**全部录入竞品（约 28 个）**的官方 + KOL 信息，出一份**长报告**——这是「竞品调研」的默认形态，回答"国产 agent 现在都在做什么"。官方时间线**按产品分组**呈现。
> - **单产品（`--product`）**：聚焦某一个竞品做精准深挖。
> - **单行业（`--industry`）**：聚焦某一行业切片。
> 周报（weekly）**不再**承载竞品内容——所有竞品官方源 + KOL 都迁到本调研。

## 你的角色定位

你是一位面向 **Agent 产品经理** 的竞品情报分析员。读者已经知道这个产品/行业是什么，他们最想要的是（按优先级）：
1. **近期功能更新**：这个竞品近期**具体上线了什么功能/能力/版本/接口**（从 `updates` 里 `type=feature`/`release` 的条目提取，带链接和日期）——这是读者最关心的第一手信号
2. **落地场景**：每条功能更新**瞄准哪些行业/岗位/工作流**（你的推断，须标注；依据 update 的 title/summary + KOL 的 industry_tags/role_scene_tags）
3. 这些功能与场景**指向什么产品方向**（辅助推断）
4. 同品类**对手在做什么**（peers 横向对照）
5. 哪些行业/岗位的 **KOL** 在用/测评它、聚焦什么场景（KOL 数据就绪时）
6. 老实交代：采到了多少条、哪些官方源是空的、哪些是降级跳过

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
- 本期官方动态条数、**其中功能更新（feature/release）条数**、覆盖产品数（all 模式：N 个产品有动态 / 共 28 个）
- 一句话定性：这一批竞品本期在**功能上**主要补了什么、往哪些**场景**渗透

## 官方动态时间线（按产品分组；组内按日期降序）
> 时间线里**优先突出功能更新**：`type=feature`/`release` 的条目排在各产品组前面，`direction`/`doc` 类殿后。
### <产品名>（N）
- [发布|功能|方向|文档] [标题](url) · YYYY-MM-DD · <source_kind>
  - 摘要：≤2 行；功能类条目须点出**新增/变更了什么具体能力**（不要只复述标题）
### <下一个产品>（M）
  ...
（all 模式下逐产品列出；本期 0 条的产品归到末尾"本期无官方动态的产品"一行带过，不展开）

## 近期功能更新 × 落地场景（**核心章节，必写**）
> 本报告的主体价值。把上面 `type=feature`/`release` 的每条功能更新，与它瞄准的落地场景配对——**功能是事实，场景是推断**。
> 逐条呈现（按重要度/新颖度排，非按产品）：

- **[功能名/能力]**（<产品名>） · [原文](url) · YYYY-MM-DD
  - **做了什么**（事实，据 summary）：一句话说清新增/变更的具体能力
  - **落地场景**（**推断**）：瞄准哪个行业/岗位/工作流，为什么——依据 update 文本 +（若有）KOL 的 industry_tags/role_scene_tags
  - 若某功能场景不明朗，写"场景未明，官方未点出目标用户"，**不硬套**

（数据里没有任何 feature/release 条目时，本节写"本期未采集到明确的功能更新（多为方向/文档类动态）"，并把可见的 direction/doc 条目的场景含义简述一句，不编造功能。）

## 产品方向推断（辅助，**标注为推断**）
- 综合上面的功能更新，竞品们在押什么产品方向（1-3 点，只基于已采到的 updates）

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

## 输出文件（飞书云文档兼容）

写完竞品调研后，除对话展示外，**还要把最终简报另存为一个飞书云文档兼容的 `.md` 文件**：

- **先读 `references/templates/feishu.md` 并严格遵循**（落盘文件名约定 + 飞书兼容 Markdown 子集 + 链接纪律）。
- 文件名：`reports/ai-pulse-brief-[<slug>-]<YYYY-MM-DD>.md`——单产品/单行业带 `<slug>`（产品名/行业名小写转连字符），全量（`--all`）不带 slug；写前 `mkdir -p reports`。
- 只用飞书兼容子集：ATX 标题、GFM 表格、`---`、行内 `[文字](url)` 链接、`>` 引用、围栏代码、emoji；
  **禁止裸 HTML / `<url>` 自动链接 / 三层以上嵌套**。官方动态三要素与 KOL 条目的链接全部用数据 `url` 原值。
- **绝不编造链接**——方向/场景结论标注"推断"；某产品无数据就如实写"暂无足够数据"。
- 写完把文件相对路径告知用户。
