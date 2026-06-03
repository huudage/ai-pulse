#!/usr/bin/env python3
"""
Topic feedback search — 单主题社区反馈检索

Given a user-provided topic (e.g. "Cursor agent mode"), concurrently search
Hacker News, Reddit, Twitter (best-effort), and TrendRadar Chinese hot lists
for community discussion in the last N days. Output a structured JSON + a
companion markdown digest for OpenClaw agent to write the final Chinese report.

Routed by SKILL.md Rule 6 ("Topic feedback search"). Companion prompt at
references/prompts/topic-feedback.md.

Design: zero LLM key. All semantic work (extracting topic from natural-language
input, sentiment classification, writing the report) is the agent's job.
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import ssl

SCRIPTS_DIR = Path(__file__).resolve().parent

CACHE_TTL_SECONDS = 600  # 10 min
CACHE_DIR = Path(tempfile.gettempdir()) / "topic-feedback-cache"
USER_AGENT = "FollowNews/3.0 (topic-feedback bot)"
TIMEOUT = 15
_SSL_CTX = ssl.create_default_context()

REDDIT_AI_SUBS = {
    "LocalLLaMA", "OpenAI", "ChatGPT", "MachineLearning",
    "ArtificialInteligence", "singularity", "ChatGPTCoding", "PromptEngineering",
}

logger = logging.getLogger("topic-feedback")


# ────────────────────────────────────────────────────────────────────────────
# Cache helpers (10-min TTL, keyed on (source, query))
# ────────────────────────────────────────────────────────────────────────────

def _cache_path(source: str, query: str) -> Path:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{source}-{digest}.json"


def cache_get(source: str, query: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(source, query)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(payload["cached_at"])
        if (datetime.now(timezone.utc) - cached_at).total_seconds() > CACHE_TTL_SECONDS:
            return None
        logger.debug(f"  ↻ cache hit: {source} '{query}'")
        return payload["data"]
    except Exception as e:
        logger.debug(f"  cache read failed for {source}: {e}")
        return None


def cache_put(source: str, query: str, data: Dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _cache_path(source, query)
    try:
        p.write_text(json.dumps({
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug(f"  cache write failed for {source}: {e}")


# ────────────────────────────────────────────────────────────────────────────
# HN search
# ────────────────────────────────────────────────────────────────────────────

def search_hn(query: str, days: int, enrich: bool) -> Dict[str, Any]:
    cached = cache_get("hn", f"{query}|{days}|{enrich}")
    if cached is not None:
        return cached

    epoch_floor = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    url = (
        "https://hn.algolia.com/api/v1/search?tags=story"
        f"&hitsPerPage=15&query={quote(query)}"
        f"&numericFilters=created_at_i>{epoch_floor}"
    )

    try:
        from importlib.machinery import SourceFileLoader
        enricher_path = SCRIPTS_DIR / "enrich_comments.py"
        if enricher_path.exists():
            enricher = SourceFileLoader("enrich_comments", str(enricher_path)).load_module()
            payload = enricher._http_get_json(url)
        else:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"status": f"error: {e}", "count": 0, "results": []}

    if not payload:
        return {"status": "error: empty response", "count": 0, "results": []}

    hits = payload.get("hits") or []
    results: List[Dict[str, Any]] = []
    for h in hits:
        story_id = h.get("objectID")
        if not story_id:
            continue
        results.append({
            "title": h.get("title") or "",
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
            "story_id": story_id,
            "points": h.get("points") or 0,
            "num_comments": h.get("num_comments") or 0,
            "author": h.get("author") or "",
            "created_at": h.get("created_at") or "",
            "top_comments": [],
        })

    # Sort by points desc, then enrich top 3
    results.sort(key=lambda r: r.get("points") or 0, reverse=True)

    if enrich and results:
        try:
            from importlib.machinery import SourceFileLoader
            enricher_path = SCRIPTS_DIR / "enrich_comments.py"
            if enricher_path.exists():
                enricher = SourceFileLoader("enrich_comments", str(enricher_path)).load_module()
                for r in results[:3]:
                    r["top_comments"] = enricher._fetch_hn_story_comments(r["story_id"], 3)
        except Exception as e:
            logger.debug(f"HN comment enrichment failed: {e}")

    out = {"status": "ok", "count": len(results), "results": results}
    cache_put("hn", f"{query}|{days}|{enrich}", out)
    return out


# ────────────────────────────────────────────────────────────────────────────
# Reddit search
# ────────────────────────────────────────────────────────────────────────────

def search_reddit(query: str, days: int) -> Dict[str, Any]:
    cached = cache_get("reddit", f"{query}|{days}")
    if cached is not None:
        return cached

    fr_path = SCRIPTS_DIR / "fetch-reddit.py"
    if not fr_path.exists():
        return {"status": "skipped: fetch-reddit.py not found in scripts dir", "count": 0, "results": []}

    try:
        from importlib.machinery import SourceFileLoader
        fr = SourceFileLoader("fetch_reddit", str(fr_path)).load_module()
    except Exception as e:
        return {"status": f"skipped: failed to load fetch-reddit.py: {e}", "count": 0, "results": []}

    token = fr._get_reddit_oauth_token()
    if not token:
        reason = fr._OAUTH_DISABLED_REASON or "REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET not set"
        return {"status": f"skipped: {reason}", "count": 0, "results": []}

    # Time filter: Reddit's `t` only supports week/month/year; pick closest.
    if days <= 7:
        t = "week"
    elif days <= 31:
        t = "month"
    else:
        t = "year"

    params = {
        "q": query,
        "sort": "relevance",
        "t": t,
        "limit": 50,
        "raw_json": 1,
    }
    url = f"https://oauth.reddit.com/search.json?{urlencode(params)}"

    try:
        req = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"bearer {token}",
            "Accept": "application/json",
        })
        with urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as e:
        return {"status": f"error: {e}", "count": 0, "results": []}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    children = data.get("data", {}).get("children", [])
    results: List[Dict[str, Any]] = []
    for child in children:
        post = child.get("data") or {}
        created = post.get("created_utc") or 0
        if created < cutoff:
            continue
        title = (post.get("title") or "").strip()
        if not title:
            continue

        sub = post.get("subreddit") or ""
        score = post.get("score") or 0
        weighted = score * 1.3 if sub in REDDIT_AI_SUBS else float(score)

        results.append({
            "title": title,
            "subreddit": sub,
            "is_ai_sub": sub in REDDIT_AI_SUBS,
            "url": f"https://www.reddit.com{post.get('permalink', '')}",
            "external_url": post.get("url") if not post.get("is_self") else None,
            "score": score,
            "weighted_score": round(weighted, 1),
            "num_comments": post.get("num_comments") or 0,
            "upvote_ratio": post.get("upvote_ratio") or 0,
            "created_at": datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
            "author": post.get("author") or "",
            "selftext": (post.get("selftext") or "")[:500],
        })

    results.sort(key=lambda r: r["weighted_score"], reverse=True)
    out = {"status": "ok", "count": len(results), "results": results}
    cache_put("reddit", f"{query}|{days}", out)
    return out


# ────────────────────────────────────────────────────────────────────────────
# Twitter search (best-effort via OpenCLI subcommand probe)
# ────────────────────────────────────────────────────────────────────────────

def search_twitter(query: str) -> Dict[str, Any]:
    opencli = shutil.which("opencli") or os.environ.get("OPENCLI_BIN")
    if not opencli:
        return {"status": "skipped: opencli binary not in PATH and OPENCLI_BIN not set",
                "count": 0, "results": []}

    cached = cache_get("twitter", query)
    if cached is not None:
        return cached

    # Probe with 60s timeout — Windows .cmd wrappers have slow cold start.
    # If `search` subcommand is missing, we'll get a clear non-zero rc + stderr
    # below, no need for an extra --help round-trip.
    try:
        proc = subprocess.run(
            [opencli, "twitter", "search", query, "--limit", "30", "-f", "json"],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"status": "error: opencli twitter search timed out after 180s "
                          "(opencli sometimes needs warm browser session for X scraping)",
                "count": 0, "results": []}
    except Exception as e:
        return {"status": f"error: opencli twitter search failed: {e}",
                "count": 0, "results": []}

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "")[-300:]
        if "unknown command" in stderr_tail.lower() or "not a command" in stderr_tail.lower():
            return {"status": "skipped: opencli build does not include 'twitter search' subcommand",
                    "count": 0, "results": []}
        return {"status": f"error: opencli rc={proc.returncode}: {stderr_tail}",
                "count": 0, "results": []}

    try:
        raw = json.loads(proc.stdout or "[]")
        if isinstance(raw, dict):
            tweets = raw.get("tweets") or raw.get("data") or raw.get("results") or []
        else:
            tweets = raw
    except json.JSONDecodeError as e:
        return {"status": f"error: opencli output not JSON: {e}; head={(proc.stdout or '')[:200]}",
                "count": 0, "results": []}

    # opencli 1.8.0 schema confirmed: id / author / text / likes / views / url / created_at
    results = []
    for t in tweets:
        if not isinstance(t, dict):
            continue
        results.append({
            "text": t.get("text") or t.get("content") or "",
            "author": t.get("author") or t.get("author_handle") or t.get("user") or "",
            "url": t.get("url") or "",
            "likes": int(t.get("likes") or t.get("favorite_count") or 0),
            "retweets": int(t.get("retweets") or t.get("retweet_count") or 0),
            "views": str(t.get("views") or ""),
            "created_at": t.get("created_at") or "",
            "tweet_id": t.get("id") or "",
        })

    results.sort(key=lambda r: r.get("likes") or 0, reverse=True)
    out = {"status": "ok", "count": len(results), "results": results}
    cache_put("twitter", query, out)
    return out


# ────────────────────────────────────────────────────────────────────────────
# TrendRadar Chinese SQLite search
# ────────────────────────────────────────────────────────────────────────────

def search_trendradar(query: str, trendradar_dir: Path, days: int) -> Dict[str, Any]:
    if not trendradar_dir or not trendradar_dir.exists():
        return {"status": f"skipped: trendradar-dir not found: {trendradar_dir}",
                "count": 0, "results": []}

    db_dir = trendradar_dir / "output" / "news"
    if not db_dir.exists():
        return {"status": f"skipped: {db_dir} not found",
                "count": 0, "results": []}

    # Pick the last N daily db files
    dbs = sorted(glob.glob(str(db_dir / "*.db")), reverse=True)[:days]
    if not dbs:
        return {"status": "skipped: no .db files in TrendRadar output dir",
                "count": 0, "results": []}

    # Split query on whitespace; AND each LIKE
    terms = [t for t in query.split() if t]
    if not terms:
        return {"status": "error: empty query after split", "count": 0, "results": []}
    where = " AND ".join(["title LIKE ? COLLATE NOCASE"] * len(terms))
    params = [f"%{t}%" for t in terms]

    sql = f"""
        SELECT n.title, p.name AS platform, n.url, n.last_crawl_time, n.rank
        FROM news_items n
        LEFT JOIN platforms p ON n.platform_id = p.id
        WHERE {where}
        ORDER BY n.last_crawl_time DESC
        LIMIT 50
    """

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"TrendRadar SQL: {sql.strip()}  params={params}")

    results: List[Dict[str, Any]] = []
    seen_titles = set()
    for db_path in dbs:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            for row in conn.execute(sql, params):
                title = row["title"]
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                results.append({
                    "title": title,
                    "platform": row["platform"] or "",
                    "url": row["url"] or "",
                    "crawl_time": row["last_crawl_time"] or "",
                    "rank": row["rank"] or 0,
                    "db_file": Path(db_path).name,
                })
            conn.close()
        except sqlite3.Error as e:
            logger.debug(f"  TrendRadar db {db_path} read failed: {e}")
            continue

    return {"status": "ok", "count": len(results), "results": results}


# ────────────────────────────────────────────────────────────────────────────
# Markdown rendering (companion to JSON)
# ────────────────────────────────────────────────────────────────────────────

def render_markdown(payload: Dict[str, Any]) -> str:
    q = payload["query"]
    days = payload["days"]
    sources = payload["sources"]

    lines: List[str] = [
        f"# 主题反馈检索：{q}",
        "",
        f"_检索窗口: 最近 {days} 天 · 生成时间: {payload['generated_at']}_",
        "",
    ]

    if payload.get("no_results_hint"):
        lines.append(f"⚠️ **无结果提示**: {payload['no_results_hint']}")
        lines.append("")

    counts = " / ".join(f"{k}={v.get('count', 0)}" for k, v in sources.items())
    lines.append(f"**计数**: {counts}")
    lines.append("")

    # HN
    hn = sources.get("hn", {})
    lines.append(f"## Hacker News  ({hn.get('count', 0)} 条)")
    lines.append(f"_{hn.get('status', '')}_")
    for r in hn.get("results", []):
        lines.append("")
        lines.append(f"### {r['title']}")
        lines.append(f"- 👍 {r.get('points', 0)} pts · 💬 {r.get('num_comments', 0)} comments · @{r.get('author', '')}")
        lines.append(f"- 链接: {r['url']}")
        lines.append(f"- HN 讨论: https://news.ycombinator.com/item?id={r['story_id']}")
        for c in r.get("top_comments", []):
            content = (c.get("content") or "").replace("\n", " ")[:300]
            lines.append(f"  - **[hn] {c.get('author', '')}**: {content}")
    lines.append("")

    # Reddit
    rd = sources.get("reddit", {})
    lines.append(f"## Reddit  ({rd.get('count', 0)} 条)")
    lines.append(f"_{rd.get('status', '')}_")
    for r in rd.get("results", [])[:25]:
        marker = " 🤖" if r.get("is_ai_sub") else ""
        lines.append("")
        lines.append(f"### r/{r['subreddit']}{marker}: {r['title']}")
        lines.append(
            f"- 👍 {r.get('score', 0)} (加权 {r.get('weighted_score', 0)}) "
            f"· 💬 {r.get('num_comments', 0)} · @{r.get('author', '')}"
        )
        lines.append(f"- 链接: {r['url']}")
        if r.get("selftext"):
            text = r["selftext"].replace("\n", " ")[:300]
            lines.append(f"- 正文摘要: {text}")
    lines.append("")

    # Twitter
    tw = sources.get("twitter", {})
    lines.append(f"## Twitter / X  ({tw.get('count', 0)} 条)")
    lines.append(f"_{tw.get('status', '')}_")
    for r in tw.get("results", [])[:20]:
        lines.append("")
        lines.append(f"- **@{r.get('author', '')}** · 👍 {r.get('likes', 0)} · 🔁 {r.get('retweets', 0)}")
        text = (r.get("text") or "").replace("\n", " ")[:280]
        lines.append(f"  > {text}")
        if r.get("url"):
            lines.append(f"  [链接]({r['url']})")
    lines.append("")

    # TrendRadar
    tr = sources.get("trendradar_cn", {})
    lines.append(f"## 中文社区（TrendRadar）  ({tr.get('count', 0)} 条)")
    lines.append(f"_{tr.get('status', '')}_")
    for r in tr.get("results", []):
        lines.append("")
        lines.append(f"- **[{r.get('platform', '')}]** {r['title']}")
        lines.append(f"  - 抓取时间: {r.get('crawl_time', '')} · 热榜排名: {r.get('rank', 0)}")
        if r.get("url"):
            lines.append(f"  - 原文: {r['url']}")
    lines.append("")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Topic feedback search across HN / Reddit / Twitter / TrendRadar CN",
    )
    parser.add_argument("--query", required=True, help="Topic keyword(s) to search for, e.g. 'Cursor agent mode'")
    parser.add_argument("--days", type=int, default=30, help="Time window in days (default: 30)")
    parser.add_argument("--trendradar-dir", type=Path, default=None,
                        help="Path to TrendRadar repo dir (contains output/news/*.db)")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument("--markdown", type=Path, default=None, help="Output markdown path (optional)")
    parser.add_argument("--enrich-hn-comments", action="store_true",
                        help="Fetch top 3 comments for top 3 HN stories (extra ~10s wall time)")
    parser.add_argument("--no-cache", action="store_true", help="Bypass 10-min TTL cache")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.no_cache:
        global CACHE_TTL_SECONDS
        CACHE_TTL_SECONDS = 0

    query = args.query.strip()
    if not query:
        logger.error("--query cannot be empty")
        return 2

    logger.info(f"🔍 Topic: '{query}' · 窗口: {args.days} 天")

    workers = {
        "hn":            lambda: search_hn(query, args.days, args.enrich_hn_comments),
        "reddit":        lambda: search_reddit(query, args.days),
        "twitter":       lambda: search_twitter(query),
        "trendradar_cn": lambda: search_trendradar(query, args.trendradar_dir, days=7),
    }

    sources: Dict[str, Any] = {}
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fn): name for name, fn in workers.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                sources[name] = fut.result()
            except Exception as e:
                sources[name] = {"status": f"error: {e}", "count": 0, "results": []}
            logger.info(f"  ✅ {name}: {sources[name].get('status', '?')} ({sources[name].get('count', 0)} 条)")

    elapsed = time.monotonic() - started
    total_count = sum(s.get("count", 0) for s in sources.values())

    no_results_hint: Optional[str] = None
    if total_count == 0:
        no_results_hint = "可能 query 太长或太具体，建议改为单一品牌名或缩短词组（例：'Cursor' 而非 'Cursor agent mode 在国外'）"

    payload = {
        "query": query,
        "days": args.days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "no_results_hint": no_results_hint,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📄 JSON → {args.output}")

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(payload), encoding="utf-8")
        logger.info(f"📝 Markdown → {args.markdown}")

    logger.info(f"✅ Done in {elapsed:.1f}s · 总命中: {total_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
