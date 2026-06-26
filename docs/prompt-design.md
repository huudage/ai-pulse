# Prompt 设计思路

## 为什么需要这份提示词

follow-news **不内置 LLM 调用**——所有自然语言由 OpenClaw 的 agent 临场执行。这有好处（不用配 API key），但也有问题：**每次 agent 执行行为可能漂移**——同样的数据，今天可能写得很深入，明天可能写得很浅。

[competitor-monitor.md](../follow-news-addons/references/prompts/competitor-monitor.md) 解决的就是这个问题：**把产品规则固化成文档，agent 每次执行都按相同规则走**。

---

## 设计原则

### 1. 角色定位先于规则

文档第一段就明确："你是社区情报分析员，不是新闻播报员。周报独立成篇、不依赖日报，要的是社区在吵什么而非谁发了什么。" 这是为了把 agent 的行为从"信息搬运工"扭转为"分析师"。否则它会倾向于复述。

### 2. 互动热度驱动选题（不是厂商门槛）

周报的入选与排序唯一依据是**社区互动热度**，由 `weekly-feedback.py` 的 `engagement_score()` 算出，存进 `_engagement`：

- **HN**：`log1p(points) + 1.5*log1p(num_comments)`
- **TrendRadar 中文热榜**：`max(0,30-rank)/10 + log1p(crawl_count)`
- **多源覆盖**：`+ 1.2*log1p(source_count)`
- **厂商正则**：命中 `TIER1_VENDOR_RE` 只作 `×1.25` 加成（**不再是门槛**）
- **降权**：clickbait `-1`；SDK 版本号 bump `×0.3`

log-damped 加性归一让不同源可比，避免单一巨量值碾压。**社区讨论量是硬门槛**：哪怕事件多重磅，社区零讨论就不上周报正文（最多进末尾"本周冷清的大新闻"附录）。

### 3. 讨论类文章是一等舆论

`classify_article` 把 HN/Lobsters/TrendRadar 这类讨论源判为 `discussion`，其**标题 + 正文本身**进入候选池参与热度排序，而不是只作某条公告的陪衬。`_tier` 启发式预标签仍保留，但**仅作参考提示**，不决定入选——真正的排序键是 `_engagement`。

### 4. 社区情绪分组，强制落到原文

周报正文按情绪分组（👍 正面 / 👎 负面 / ⚖️ 争议 / 🇨🇳 中文视角），事件背景只占 1 句话，其余全是**社区原文逐字引用 + 👍 数**。这是反"水文"用的——agent 总有冲动写"重磅发布、行业瞩目"，强制引用具体评论才能落到社区真实声音上。

### 5. 引用纪律

引用**只能来自 `enriched_comments` / `floating_threads` 里的原文，不要编造**。这是关键——agent 如果脑补"社区可能会说..."，整份报告就废了。这些字段是 HN/V2EX 实抓数据，引用必须 verbatim + 带 👍 数 + 真实链接（数据里的 `url`/`link` 原值）。

### 6. 跨事件社区反馈大章（floating_threads）

🌐 大章不是"浮空感受"，而是**高互动但未配到任何公告的独立讨论串**：`pair_reactions` 没挂上的高热 thread 单列出来，每条带具体标题 + 真实 URL + points/score/comments 计数 + 2-3 条逐字评论。这回答了"不针对事件你反馈的到底是什么"——它针对的就是这些独立热议串本身。

### 7. 不要做的事

文档专门有一节"不要做的事"，列出高频反模式：

- 不要走新闻 5 问模板复述"谁发了什么"，事件背景只占 1 句话
- 不要给事件评 Tier——这是讨论量驱动周报，差异只在讨论规模和情绪基调
- 社区零讨论的大新闻进附录，不展开
- 不知道就说不知道（标记低置信度），绝不编造评论/链接

---

## 厂商正则的更新策略

厂商正则 `TIER1_VENDOR_RE` 仍写在 `scripts/weekly-feedback.py`，但角色已从"Tier 门槛"降级为"`×1.25` 热度加成"——大厂发布在同等讨论量下略占优，但**不再压制高热社区话题**。

**更新触发**：新厂商崛起 / 旧厂商不再活跃 / 关注重心变化。
**更新流程**：改 `TIER1_VENDOR_RE` 正则 → 跑一次合成数据测试，验证 `_engagement` 排序符合预期（不再需要同步文字白名单，因为 agent 不再据厂商名分级）。

---

## OpenClaw agent 怎么读这份文档

在 `skills/ai-pulse-weekly/SKILL.md` 里写明：

> **CRITICAL — Read `references/prompts/competitor-monitor.md` first and follow it strictly when writing the natural-language report.**

agent 按 OpenClaw 框架的设计会：

1. 看到用户问"周报"
2. 匹配 ai-pulse-weekly skill 路由
3. 执行 `weekly.sh`（内部 `weekly-feedback.py --fetch-now --enrich-top 20`）
4. 读结果 JSON（候选已按 `_engagement` 降序，含 `floating_threads`）+ competitor-monitor.md 模板
5. 按模板严格输出（情绪分组 + 跨事件大章）

**这里的关键**：SKILL.md 是路由说明，competitor-monitor.md 是行为说明，两者**互相引用**，缺一不可。

---

## 调优经验

第一次使用时，你可能会发现：

- 正文太长 → 调高 `--enrich-top`/正文入选的 `_engagement` 阈值，或在 prompt 里限制每个情绪组的条数
- 大厂公告淹没社区话题 → 检查 `×1.25` 加成是否偏高，或确认社区讨论量门槛是否生效
- 社区原文不准 → 检查 `enriched_comments`/`floating_threads` 数据，可能 URL 不对应 / 评论被删
- 中文社区段偏薄 → 挂 `daily.sh` 累积 TrendRadar 7 天快照厚度

---

## 后续可扩展

- **中文评论正文补全**：V2EX 已零鉴权实抓（`enrich_comments.py` 的 `find_v2ex_topic_by_brand` + `fetch_v2ex_comments`）；知乎/B站为 cred-gated stub，补 cookie 后可启用
- **加历史回溯**："上周这个热议事件现在回看怎么样" → 翻 archive 找老的 daily-json
- **加趋势对比**：把本周高热话题的 `_engagement` 分布画成图，追踪某话题的讨论密度变化
- **加 RSS 输出**：把周报 markdown 转 RSS，给其他订阅者用
