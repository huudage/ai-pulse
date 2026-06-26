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
  Step 1: weekly-feedback.py 现抓 7 天 + 互动热度聚合
═══════════════════════════════════════════════════════════════

  python3 scripts/weekly-feedback.py \
    --fetch-now \
    --trendradar-dir <path>/trendradar \
    --days 7 \
    --output /tmp/td-weekly-merged.json \
    --markdown /tmp/td-weekly.md \
    --enrich-top 20
  │
  ├─► fetch_now() 现抓 7 天英文源 + 现爬 TrendRadar 今日快照
  │     （自给自足，不依赖 daily-json 累积；有累积则中文热榜段更厚）
  │
  ├─► merge-sources.deduplicate_articles()
  │     跨日 URL 归一化去重
  │
  ├─► merge-sources.merge_article_sources()
  │     跨日多源识别（同一事件多平台多日报道）
  │     multi_source / source_count / all_sources 重新计算
  │
  ├─► classify_article() — 三分类
  │     news:       github / podcast / priority RSS + release 词
  │     discussion: twitter / web / HN-like RSS（标题+正文进候选池，一等舆论）
  │     neutral:    其他
  │
  ├─► engagement_score() — 互动热度评分 ★（入选与排序的唯一依据）
  │     HN points+评论 / Twitter 互动 /
  │     中文热榜排名+抓取次数 / 多源覆盖的 log-damped 加性归一
  │     厂商正则仅作 ×1.25 加成（不再是门槛）；SDK/clickbait 降权
  │     结果存 _engagement；assign_tier 保留但仅作 _tier 提示，不决定抓评论
  │
  ├─► dedup_same_project() 合并同项目连续版本
  │
  ├─► pair_reactions() — 配对
  │     每条 news 抽 ≤6 anchor，discussion 命中 anchor 才配对
  │     时间晚于 announcement
  │
  └─► enrich_comments.py ★（对热度 Top-N 候选，news+discussion 混合）
        直链 / 品牌主动搜索 → HN Algolia、V2EX sov2ex ES
        抓回评论原文注入 article["enriched_comments"]
        未挂到任何公告的高热讨论串 → 顶层 floating_threads 数组

═══════════════════════════════════════════════════════════════
  Step 2: 输出
═══════════════════════════════════════════════════════════════

  /tmp/td-weekly-merged.json
        候选按 _engagement 降序 + floating_threads + output_stats
        （engagement_top_n / enriched_count / floating_threads_count）
  /tmp/td-weekly.md（备份）

═══════════════════════════════════════════════════════════════
  Step 3: OpenClaw 周报呈现
═══════════════════════════════════════════════════════════════

  你说"本周 AI 圈周报 / weekly" → agent 匹配 ai-pulse-weekly skill
  → 跑 weekly.sh（内部 weekly-feedback.py --fetch-now --enrich-top 20）
  → 读 references/prompts/competitor-monitor.md（强制）★
  → 按规则做：
      1. 社区讨论量为入选硬门槛，按 _engagement 降序选题（不评 Tier）
      2. 按情绪分组（👍 正面 / 👎 负面 / ⚖️ 争议 / 🇨🇳 中文视角）
      3. 引用 enriched_comments 里的 HN/V2EX 逐字原文（带 👍 数）
      4. 🌐 跨事件社区反馈大章：渲染 floating_threads（带链接+计数）
  → 输出自然语言周报给你
  （竞品官方动态 + KOL 已迁至 competitor-brief.py，见竞品调研数据流）
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
| follow-news GitHub | 14 天 release | 内置 |
| follow-news Web 搜索 | 24 小时 | `--freshness pd` |
| 周报数据底盘 | 7 天 daily JSON | `--days 7` |
