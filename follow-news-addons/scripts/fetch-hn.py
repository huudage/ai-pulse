#!/usr/bin/env python3
"""
Fetch AI-relevant Hacker News stories AND their top comment threads.

Why this exists:
    The weekly community-feedback report needs real comment-section text, not
    "news discussing news". HN is the densest AI discussion venue and exposes a
    zero-auth API. Unlike the old enrich path (which only scraped comments for
    Tier 1/2 vendor *announcements*), this fetcher pulls discussion-heavy stories
    directly and attaches their top comments as `enriched_comments`, so they
    bypass the announcement→tier funnel entirely.

Mechanism:
    1) HN Algolia search → AI-relevant stories in the time window, ranked by points
    2) HN Algolia items/{id} → top-level comments for each story (one request/story)

Usage:
    python3 fetch-hn.py [--hours 168] [--min-points 30] [--limit 30]
                        [--comments-per-story 6] [--output FILE] [--verbose]

Environment:
    No API key required. Uses the public hn.algolia.com API.
"""

import argparse
import html
import json
import logging
import re
import ssl
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_SSL_CTX = ssl.create_default_context()
USER_AGENT = "ai-pulse/1.0 (+https://github.com/huudage/ai-pulse)"
TIMEOUT = 30

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEM = "https://hn.algolia.com/api/v1/items/{id}"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"

# Title keywords that mark a story as AI-relevant. Word-boundary matched so
# "ml" doesn't fire on "html" and "ai" doesn't fire on "email".
AI_KEYWORDS = [
    r"\bai\b", r"\ba\.i\.\b", r"\bllms?\b", r"\bgpts?\b", r"\bgpt-\d", r"\bclaude\b",
    r"\bgemini\b", r"\bmistral\b", r"\bllama\b", r"\bdeepseek\b", r"\bqwen\b",
    r"\bgrok\b", r"\bopenai\b", r"\banthropic\b", r"\bhugging\s*face\b",
    r"\bagentic?\b", r"\bagents?\b", r"\bmachine\s+learning\b", r"\bdeep\s+learning\b",
    r"\bneural\b", r"\btransformers?\b", r"\bdiffusion\b", r"\bembeddings?\b",
    r"\binference\b", r"\bfine[\s-]?tun", r"\brag\b", r"\bvector\s+(db|database|search)\b",
    r"\bprompt(ing|s)?\b", r"\bcopilot\b", r"\bcursor\b", r"\bmcp\b",
    r"\blangchain\b", r"\bvllm\b", r"\bollama\b", r"\bmultimodal\b",
    r"\breinforcement\s+learning\b", r"\bgenerative\b", r"\bfoundation\s+model",
    r"\bchatbot\b", r"\bnlp\b", r"\bcomputer\s+vision\b", r"\bagi\b",
]
_AI_RE = re.compile("|".join(AI_KEYWORDS), re.IGNORECASE)

# Topic hints → primary_topic so regroup_by_topic in weekly-feedback can place them.
TOPIC_RULES = [
    ("ai-agent", re.compile(r"agent|mcp|langchain|copilot|cursor|tool\s*use", re.I)),
    ("llm", re.compile(r"llm|gpt|claude|gemini|mistral|llama|deepseek|qwen|model|inference|fine[\s-]?tun|rag|prompt", re.I)),
    ("frontier-tech", re.compile(r"agi|research|paper|neural|transformer|diffusion|reinforcement", re.I)),
]


def _http_get_json(url: str, logger: logging.Logger, retries: int = 3) -> Optional[Any]:
    # The public API occasionally resets the TLS handshake on a cold connection
    # (probabilistic GFW interference), so retry a few times with backoff.
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except (HTTPError, URLError, ValueError, TimeoutError, ssl.SSLError) as e:
            logger.debug(f"HTTP fetch failed for {url} (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return None


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = text.replace("<p>", "\n").replace("</p>", "")
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _primary_topic(title: str) -> str:
    for topic, pat in TOPIC_RULES:
        if pat.search(title):
            return topic
    return "llm"


def search_ai_stories(
    cutoff_epoch: int, min_points: int, logger: logging.Logger
) -> List[Dict[str, Any]]:
    """Return AI-relevant HN stories created after cutoff, with >= min_points.

    HN Algolia only allows `created_at_i` in numericFilters (points/num_comments
    are not in numericAttributesForFiltering → 400), so points is filtered
    client-side. /search default ranking already surfaces popular stories.
    """
    url = (
        f"{ALGOLIA_SEARCH}?tags=story"
        f"&numericFilters={quote(f'created_at_i>{cutoff_epoch}')}"
        f"&hitsPerPage=200"
    )
    payload = _http_get_json(url, logger)
    if not payload:
        return []
    hits = payload.get("hits", []) or []
    stories: List[Dict[str, Any]] = []
    for h in hits:
        title = h.get("title") or ""
        oid = h.get("objectID")
        if not oid or not title:
            continue
        if (h.get("points") or 0) < min_points:
            continue
        if not _AI_RE.search(title):
            continue
        stories.append(
            {
                "object_id": str(oid),
                "title": title,
                "story_url": h.get("url") or HN_ITEM_URL.format(id=oid),
                "points": h.get("points") or 0,
                "num_comments": h.get("num_comments") or 0,
                "author": h.get("author") or "",
                "created_at_i": h.get("created_at_i") or 0,
            }
        )
    stories.sort(key=lambda s: s["points"], reverse=True)
    logger.info(
        f"HN Algolia: {len(hits)} stories in window, "
        f"{len(stories)} AI-relevant with >={min_points} points"
    )
    return stories


def fetch_top_comments(
    object_id: str, max_count: int, logger: logging.Logger
) -> List[Dict[str, Any]]:
    """Fetch top-level comments for an HN story via the Algolia items endpoint."""
    payload = _http_get_json(ALGOLIA_ITEM.format(id=object_id), logger)
    if not payload:
        return []
    comments: List[Dict[str, Any]] = []
    for child in payload.get("children", []) or []:
        if len(comments) >= max_count:
            break
        if child.get("type") != "comment":
            continue
        content = _strip_html(child.get("text") or "")
        author = child.get("author") or ""
        if not content or not author:  # deleted/dead comments
            continue
        cid = child.get("id")
        comments.append(
            {
                "platform": "hn",
                "content": content[:1200],
                "author": author,
                "likes": 0,  # HN API does not expose per-comment karma
                "url": HN_ITEM_URL.format(id=cid),
            }
        )
    return comments


def build_articles(
    cutoff_epoch: int,
    min_points: int,
    limit: int,
    comments_per_story: int,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    stories = search_ai_stories(cutoff_epoch, min_points, logger)[:limit]
    articles: List[Dict[str, Any]] = []
    enriched_total = 0
    for s in stories:
        comments = fetch_top_comments(s["object_id"], comments_per_story, logger)
        enriched_total += len(comments)
        topic = _primary_topic(s["title"])
        date_iso = (
            datetime.fromtimestamp(s["created_at_i"], tz=timezone.utc).isoformat()
            if s["created_at_i"]
            else ""
        )
        articles.append(
            {
                "title": s["title"],
                "link": HN_ITEM_URL.format(id=s["object_id"]),
                "external_url": s["story_url"],
                "snippet": "",
                "date": date_iso,
                "points": s["points"],
                "num_comments": s["num_comments"],
                "primary_topic": topic,
                "topics": [topic],
                "all_topics": [topic],
                "enriched_comments": comments,
            }
        )
        logger.info(
            f"  ✚ [{s['points']:>4} pts / {s['num_comments']:>3} cmts] "
            f"{len(comments)} scraped → '{s['title'][:60]}'"
        )
        time.sleep(0.2)  # be polite to the public API
    logger.info(
        f"HN fetch: {len(articles)} stories, {enriched_total} real comments scraped"
    )
    return articles


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch AI-relevant HN stories + top comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--hours", type=int, default=168, help="Look-back window (default 168 = 7d)")
    parser.add_argument("--min-points", type=int, default=30, help="Minimum story points (default 30)")
    parser.add_argument("--limit", type=int, default=30, help="Max stories to enrich (default 30)")
    parser.add_argument("--comments-per-story", type=int, default=6, help="Top comments per story (default 6)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("fetch-hn")

    cutoff_epoch = int(time.time()) - args.hours * 3600
    articles = build_articles(
        cutoff_epoch, args.min_points, args.limit, args.comments_per_story, logger
    )

    # Output shape mirrors other fetchers: {"sources": [{name, source_id, articles}]}
    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "Hacker News",
                "source_id": "hackernews",
                "priority": True,
                "articles": articles,
            }
        ],
        "total_articles": len(articles),
    }

    output_path = args.output or (Path(tempfile.gettempdir()) / "td-hn.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {len(articles)} HN stories → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
