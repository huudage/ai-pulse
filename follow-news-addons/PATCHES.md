# follow-news Patch 参考

本文档说明 `patches/follow-news/upstream.patch` **修改了上游哪些文件、修改了什么**。用途：

- 升级上游 follow-news SHA 时知道要 rebase 哪些点
- 手动 debug 时定位 patch 触碰到的 hook 位置

**普通用户不需要看本文档** —— `install.sh` 已自动应用所有改动。

patch 共修改 follow-news 上游的 **3 个文件**。

---

## 1. `scripts/fetch-rss.py` — 加 `file://` 协议支持

找到 `fetch_feed_with_retry` 函数里 `for attempt in range(RETRY_COUNT + 1):` 循环内的 `try:` 块，把整段 cache + urlopen 逻辑改造成：

```python
        try:
            req_headers = {"User-Agent": "FollowNews/2.0"}

            # file:// — read local file directly, bypass HTTP cache/conditional headers.
            # Lets local exporters (e.g. TrendRadar) feed RSS into the pipeline without an HTTP server.
            if url.startswith("file://"):
                from urllib.request import url2pathname
                from urllib.parse import urlparse
                parsed = urlparse(url)
                local_path = url2pathname(parsed.path)
                with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                final_url = url
            else:
                # ... 原来的 HTTP cache + urlopen + URLError 处理逻辑全部缩进进 else 分支
```

约 8 行新增。原 HTTP 路径不变，只是缩进进 else 分支。

---

## 2. `scripts/run-pipeline.py` — 归档每日 merged JSON

在 `argparse` 区域 `--debug` 参数下面新增：

```python
parser.add_argument(
    "--no-archive-json",
    dest="archive_json",
    action="store_false",
    default=True,
    help="Skip archiving the final merged JSON into <archive-dir>/daily-json/<date>.json (default: archive)",
)
```

在 `if args.debug:` 块之后新增：

```python
    # Archive the final merged JSON into <archive-dir>/daily-json/YYYY-MM-DD.json.
    # Powers weekly-feedback.py: lets it pool the last N days of raw merged JSON
    # for cross-day announcement/reaction correlation. No-op when --archive-dir
    # is not provided, since there's no archive root to write into.
    if args.archive_json and args.archive_dir:
        import shutil
        from datetime import datetime as _dt
        try:
            daily_dir = args.archive_dir / "daily-json"
            daily_dir.mkdir(parents=True, exist_ok=True)
            date_str = _dt.utcnow().strftime("%Y-%m-%d")
            archived_path = daily_dir / f"{date_str}.json"
            shutil.copy2(str(args.output), str(archived_path))
            logger.info(f"📦 Archived merged JSON → {archived_path}")
        except Exception as e:
            logger.warning(f"Failed to archive daily JSON: {e}")
```

---

## 3. `SKILL.md` — 加路由规则 5

在 "Execution Routing Policy" 区域，第 4 条之后插入：

```markdown
5. **Weekly competitor monitor digest**
   - When user asks for a "weekly", "本周", "this week", "周报", "竞品监控", "AI 圈周报" digest, or asks "what did the AI community say about <event>".
   - Execute:
     ```bash
     python3 scripts/weekly-feedback.py \
       --archive-dir <workspace>/archive/follow-news \
       --days 7 \
       --output /tmp/td-weekly-merged.json \
       --markdown /tmp/td-weekly.md \
       --enrich-tier1
     ```
   - `--enrich-tier1` invokes `scripts/enrich_comments.py` to fetch real HN / V2EX top comment text for Tier 1 announcements (zero-auth JSON APIs, no API key required).
   - Then render the structured weekly JSON via `scripts/summarize-merged.py --input /tmp/td-weekly-merged.json --top 30` for inspection.
   - **CRITICAL — Read `references/prompts/competitor-monitor.md` first and follow it strictly when writing the natural-language report.** That template defines the Tier 1/2/3 rules, the 3 dimensions (模型 / 工程架构 / Agent 产品), the 5-question deep-dive template per Tier 1 event, and the final report structure. Do not improvise.
   - Each announcement article has a `_tier` heuristic pre-label; you may revise it per the prompt rules but must justify any change.
   - For Tier 1 events, quote 2-3 entries from `enriched_comments` (verbatim, with 👍 counts). If empty, write "本周暂无显著社区讨论" — do not fabricate.
   - Requires `<workspace>/archive/follow-news/daily-json/<YYYY-MM-DD>.json` to be present. If empty, run `run-pipeline.py --archive-dir <workspace>/archive/follow-news` once first to seed, and inform the user that the weekly digest will progressively fill out as daily archives accumulate.
```

完整内容也可以从 `follow-news-addons/skill-patches/routing-rule-5.md` 拷贝。

---

## 4. `SKILL.md` — 加路由规则：按需竞品调研

在 "Execution Routing Policy" 区域，紧接前一条之后插入：

```markdown
6. **On-demand competitor brief（按需竞品调研）**
   - When user asks to research a specific domestic agent product or industry, e.g.
     "调研一下通义灵码 / Trae / Manus 最近在做什么"、"<竞品> 最新动态/方向"、
     "<行业>（金融/医疗/教育/政务/电商/制造/法律/内容媒体）有哪些 agent 竞品在布局".
   - This is product/industry-scoped (NOT the weekly community digest, NOT single-topic
     community feedback). It pulls each tracked product's **official** updates and
     (when available) KOL industry/role content, then asks you to synthesize 方向/场景.
   - Execute (产品维度，--product 与 --industry 互斥)：
     ```bash
     PYTHONUTF8=1 python3 scripts/competitor-brief.py \
       --product "通义灵码" \
       --profiles workspace/config/competitor-profiles.json \
       --window-days 30 \
       --out-json /tmp/competitor-brief.json --out-md /tmp/competitor-brief.md
     ```
     行业维度改用 `--industry "金融"`（取值须在骨架字典内）。
   - **CRITICAL — Read `references/prompts/competitor-brief.md` first and follow it strictly.**
     That template defines the report structure, the 官方动态三要素（类型+标题+链接），the
     方向/场景 synthesis（必须标注"推断"），and the data contract. Do not improvise links.
   - `updates` 与 `kol_contents` 都为空时脚本写"暂无足够数据"——照实告知用户并建议放宽
     `--window-days` 或补全 `workspace/config/competitor-profiles.json` 的 official_sources。
   - KOL 采集依赖 005 抓取器，未就绪时 `kol_contents` 为空 → 跳过 KOL 小节，不报错、不编造。
   - 竞品清单与官方源配置在 `workspace/config/competitor-profiles.json`（install.sh 已复制骨架）。
```

完整内容也可以从 `follow-news-addons/skill-patches/routing-rule-6-competitor-brief.md` 拷贝。

> 国产 Agent 竞品的官方动态 + KOL 已从周报迁出，统一由「按需竞品调研」
> （`competitor-brief.py`，路由规则见上）承载——无 flag 默认抓全部录入竞品出长报告，
> 也可 `--product` / `--industry` 单点。周报（`weekly-feedback.py`）不再调用
> `fetch-competitor-official.py`，输出 JSON 也不再含 `competitor_official` / `competitor_kol`。

---

## workspace 自定义信源

把 `follow-news-addons/workspace-config/follow-news-sources.json` 拷贝到 follow-news 仓的 `workspace/config/follow-news-sources.json`，**注意修改里面 URL 中的 TrendRadar 输出路径** 为你机器上的实际路径。
