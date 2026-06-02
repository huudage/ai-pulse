# Prompt 设计思路

## 为什么需要这份提示词

follow-news **不内置 LLM 调用**——所有自然语言由 OpenClaw 的 agent 临场执行。这有好处（不用配 API key），但也有问题：**每次 agent 执行行为可能漂移**——同样的数据，今天可能写得很深入，明天可能写得很浅。

[competitor-monitor.md](../follow-news-addons/references/prompts/competitor-monitor.md) 解决的就是这个问题：**把产品规则固化成文档，agent 每次执行都按相同规则走**。

---

## 设计原则

### 1. 角色定位先于规则

文档第一段就明确："你是资深 AI 行业分析师，不是新闻播报员。读者已经看过了日报。" 这是为了把 agent 的行为从"信息搬运工"扭转为"分析师"。否则它会倾向于复述。

### 2. 分级而不是排序

"Top 10" 之类排序对 agent 很难，因为它需要全局比较，而上下文有限。**分桶（Tier 1/2/3/X）** 是更稳定的指令，每个桶都有明确判定规则。

### 3. 启发式预标签 + LLM 复议

`weekly-feedback.py` 给每条 announcement 打 `_tier`（基于厂商正则白名单），agent **可以复议**，但需要给理由。这样：
- 大多数情况下脚本已经给对了，agent 不需要重新判断
- 少数边缘案例由 agent 提供智能补救
- 复议必须给理由 → 避免 agent 任意改动

### 4. 五问模板强制深度

Tier 1 事件必须回答 5 个问题：
1. 是什么
2. 为什么重要（差异点）
3. 技术亮点
4. 竞品对照（具体到产品名）
5. 社区反响（引原文+👍数）

这五问是反"水文"用的——agent 总有冲动写"重磅发布、行业瞩目"，五问强制它落到具体技术决策上。

### 5. 引用纪律

第 5 题"社区反响"明确：**只引用 `enriched_comments` 里的原文，不要编造**。这是关键——agent 如果脑补"社区可能会说..."，整份报告就废了。`enriched_comments` 是 HN/Reddit 实抓数据，引用必须 verbatim + 带 👍 数。

### 6. 不要做的事

文档专门有一节"不要做的事"，列出 4 条反模式：
- 不要把日报里的事再重复一遍
- Tier 1 不超过 7 件
- Tier 3 就是标题列表，不要展开
- 不知道就说不知道（标记低置信度）

这些是高频陷阱，明确写出来 agent 才不会犯。

---

## 三维度分类的取舍

| 维度 | 包含什么 | 不包含什么 |
|---|---|---|
| **模型** | 基础模型版本号迭代、推理模型、新模态 | 模型应用、模型评测综述 |
| **工程架构** | 协议（MCP）、训练/推理框架、Agent 框架开源 | 业务集成、单个 RAG 项目 |
| **Agent 产品** | 旗舰 Agent 产品的能力质变（Cursor 加 agent 模式）| 小功能升级（Cursor 加个快捷键）|

**关键判定**：能不能"质变"看是否影响其他产品。Cursor 加 agent 模式 → Cline / Aider 要跟进 → 这是质变。Cursor 改 UI 配色 → 无人跟 → 不是质变。

---

## Tier 1 厂商白名单的更新策略

白名单**写死**在两处：
1. `scripts/weekly-feedback.py` 的 `TIER1_VENDOR_PATTERNS` —— 用 regex 匹配标题+源名
2. `references/prompts/competitor-monitor.md` —— 用文字列表给 agent 看

**更新触发条件**：
- 新厂商首次发主流产品（如有个新独角兽崛起）
- 旧厂商不再活跃（移到 Tier 2）
- 你的关注重心变化

**更新流程**：
1. 在 `TIER1_VENDOR_PATTERNS` 加/删正则
2. 在 `competitor-monitor.md` 的 "Tier 1 评级规则"段同步加/删文字
3. **跑一次合成数据测试**，验证 `_tier` 启发式打标符合预期

---

## OpenClaw agent 怎么读这份文档

在 [SKILL.md 路由规则 5](../follow-news-addons/PATCHES.md) 里写明：

> **CRITICAL — Read `references/prompts/competitor-monitor.md` first and follow it strictly when writing the natural-language report.**

agent 按 OpenClaw 框架的设计会：
1. 看到用户问"周报"
2. 匹配 SKILL.md 路由 5
3. 执行命令行（weekly-feedback.py --enrich-tier1）
4. 读结果 JSON + competitor-monitor.md 模板
5. 按模板严格输出

**这里的关键**：SKILL.md 是路由说明，competitor-monitor.md 是行为说明，两者**互相引用**，缺一不可。

---

## 调优经验

第一次使用时，你可能会发现：
- Tier 1 太多（5 条以上）→ 调高 `_tier` 的 quality_score 阈值（脚本里 22 → 25）
- Tier 1 太少 → 在 `TIER1_VENDOR_PATTERNS` 加更多正则
- 社区原文不准 → 检查 `enriched_comments` 数据，可能 URL 不对应 / 评论被删
- 报告太长 → 在 prompt 里加"严格限制 Tier 1 不超过 5 件，超出的下调到 Tier 2"

---

## 后续可扩展

- **加 V2EX / 知乎中文社区评论抓取**：扩 `enrich_comments.py`（需 V2EX/知乎 API 支持）
- **加历史回溯**："上周这个 Tier 1 事件现在回看怎么样" → 翻 archive 找老的 daily-json
- **加趋势对比**：把本周 Tier 1 厂商分布画成图（matplotlib），追踪某厂商发布密度
- **加 RSS 输出**：把周报 markdown 转 RSS，给其他订阅者用
