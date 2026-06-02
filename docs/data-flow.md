# 数据流详解

## 每日工作流

```
═══════════════════════════════════════════════════════════════
  Step 1: TrendRadar 抓中文热榜（~30 秒）
═══════════════════════════════════════════════════════════════

  python -m trendradar
  │
  ├─► NewsNow API:抓 11 个中文热榜
  │     output/news/YYYY-MM-DD.db (SQLite，TrendRadar 自留长期存储)
  │
  ├─► 关键词过滤 (ai_focus.txt)
  │     只保留 AI 圈相关条目
  │
  ├─► 评论抓取 (可选，仅白名单平台 Top N)
  │     CommentDispatcher → BilibiliCommentFetcher 等
  │     注入 self.comments_map
  │
  ├─► 生成 HTML 报告
  │     output/html/<date>/*.html
  │     output/html/latest/<mode>.html
  │
  ├─► 推送通知（如配置了飞书/钉钉 webhook）
  │     评论自动嵌入到每条热榜下面
  │
  └─► RSS 旁路导出 ★
        output/rss/ai_focus.xml ← 给 follow-news 的入口

═══════════════════════════════════════════════════════════════
  Step 2: follow-news 主管道（~60-120 秒）
═══════════════════════════════════════════════════════════════

  python3 scripts/run-pipeline.py \
    --config workspace/config \
    --archive-dir workspace/archive/follow-news \
    --hours 24
  │
  ├─► 并行抓 7 路信源
  │     fetch-rss.py     (含 TrendRadar 那条 file:// URL)
  │     fetch-twitter.py (OpenCLI 后端)
  │     fetch-github.py
  │     fetch-trending.py
  │     fetch-reddit.py
  │     fetch-web.py     (Tavily/Brave)
  │     fetch-podcast.py
  │
  ├─► merge-sources.py
  │     URL 归一化去重 → title 相似度去重
  │     多源交叉检测（multi_source = true / source_count）
  │     质量评分（priority / recent / engagement / multi-source bonus）
  │     按 primary_topic 分组（llm / ai-agent / frontier-tech / ...）
  │
  ├─► /tmp/td-merged.json（当日最终输出）
  │     /tmp/td-merged.meta.json（跑批元数据）
  │
  └─► 旁路归档（ai-pulse 加的） ★
        workspace/archive/follow-news/daily-json/YYYY-MM-DD.json

═══════════════════════════════════════════════════════════════
  Step 3: OpenClaw 日报呈现（按需）
═══════════════════════════════════════════════════════════════

  你说"今日 AI 圈新闻" → agent 看 SKILL.md 路由 1
  → 跑 summarize-merged.py 读 /tmp/td-merged.json
  → agent 自己写自然语言摘要 → 返回给你
```

---

## 每周工作流（建议周日跑）

```
═══════════════════════════════════════════════════════════════
  Step 1: weekly-feedback.py 跨日聚合
═══════════════════════════════════════════════════════════════

  python3 scripts/weekly-feedback.py \
    --archive-dir workspace/archive/follow-news \
    --days 7 \
    --output /tmp/td-weekly-merged.json \
    --markdown /tmp/td-weekly.md \
    --enrich-tier1
  │
  ├─► collect_daily_files() 找出最近 7 天 daily-json/*.json
  │
  ├─► flatten_daily_json() 把所有 topics[*].articles 摊平
  │     ~7 × 400 = ~2800 篇候选文章
  │
  ├─► merge-sources.deduplicate_articles()
  │     跨日 URL 归一化去重 → ~700 篇
  │
  ├─► merge-sources.merge_article_sources()
  │     跨日多源识别（同一事件多平台多日报道）
  │     multi_source / source_count / all_sources 重新计算
  │
  ├─► classify_article() — 三分类
  │     announcement: github / podcast / priority RSS + release 词
  │     reaction:     reddit / twitter / web / HN-like RSS
  │     neutral:      其他
  │
  ├─► assign_tier() — Tier 启发式 ★
  │     tierX:  标题党 (震惊/刚刚！/太可怕 等)
  │     tier1:  匹配 35+ Tier1 厂商正则
  │             OR source_count >= 3
  │             OR quality_score >= 22
  │     tier2:  multi_source AND source_count >= 2
  │             OR quality_score >= 15
  │     tier3:  其余 announcement
  │
  ├─► pair_reactions() — 配对
  │     每个 announcement 找 ≤ 5 个 reactions
  │     共享 normalized_title bucket、同 primary_topic
  │     时间晚于 announcement
  │
  └─► （可选 --enrich-tier1）enrich_comments.py ★
        对 Tier 1 的 announcement 和它的 reactions
        若 URL 在 news.ycombinator.com → 抓 HN Top 评论
        若 URL 在 reddit.com → 抓 Reddit Top 评论
        注入 article["enriched_comments"]

═══════════════════════════════════════════════════════════════
  Step 2: 输出
═══════════════════════════════════════════════════════════════

  /tmp/td-weekly-merged.json
        ↓ summarize-merged.py 渲染（结构化文本）
  /tmp/td-weekly.md（备份）

═══════════════════════════════════════════════════════════════
  Step 3: OpenClaw 周报呈现
═══════════════════════════════════════════════════════════════

  你说"本周 AI 圈竞品监控周报" → agent 看 SKILL.md 路由 5
  → 跑 weekly-feedback.py --enrich-tier1
  → 读 references/prompts/competitor-monitor.md（强制）★
  → 按规则做：
      1. 复议 _tier（必要时上调/下调）
      2. 三维度（模型/工程架构/Agent）分类 Tier 1 事件
      3. 每个 Tier 1 事件回答 5 个问题
      4. 引用 enriched_comments 里的 HN/Reddit 原文
      5. 写国内外横切观察段
  → 输出自然语言周报给你
```

---

## 数据落盘位置一览

```
TrendRadar/
├── output/
│   ├── news/YYYY-MM-DD.db        # 中文热榜历史（SQLite，长期）
│   ├── html/<date>/*.html        # HTML 报告（含评论）
│   ├── html/latest/*.html        # 最新版（被覆盖）
│   └── rss/ai_focus.xml          # ← follow-news 的入口（每跑覆盖）

follow-news/
├── workspace/
│   ├── config/follow-news-sources.json   # 自定义信源（含 TrendRadar）
│   └── archive/follow-news/
│       ├── *.md                          # 每日 markdown 摘要（14 天滚动）
│       └── daily-json/
│           └── YYYY-MM-DD.json           # ← 周报的数据底盘（无限期，建议加清理策略）
│
└── /tmp/                                  # Windows 上 Git Bash 翻译为 %TEMP%
    ├── td-pipeline-XXXXXX/                # 单次跑的中间产物（跑完自动清）
    ├── td-merged.json                     # 当日合并（被覆盖）
    ├── td-merged.meta.json                # 元数据
    ├── td-weekly-merged.json              # 周报 JSON（被覆盖）
    ├── td-weekly.md                       # 周报 markdown
    ├── follow-news-rss-cache.json         # HTTP 304 缓存
    └── follow-news-podcast-cache.json     # 播客元数据缓存
```

---

## 时间窗口与新鲜度

| 数据 | 时间窗口 | 控制 |
|---|---|---|
| TrendRadar 热榜 | 当前快照 | NewsNow API 实时 |
| follow-news RSS | 24-48 小时 | `--hours 24` |
| follow-news Twitter | 24 小时 | OpenCLI 默认 |
| follow-news Reddit | 24-48 小时（hot listing） | API 限制 |
| follow-news GitHub | 14 天 release | 内置 |
| follow-news Web 搜索 | 24 小时 | `--freshness pd` |
| 周报数据底盘 | 7 天 daily JSON | `--days 7` |
