#!/usr/bin/env python3
"""
Comment enrichment helper for follow-news weekly digest.

For Tier 1 announcements' related reactions, fetch top community comments from
HN and Reddit (both zero-auth JSON APIs) so the weekly report can quote real
community discussion text instead of just headlines.

This is a *library*, not a standalone script — imported by weekly-feedback.py.
Safe to call: all network errors are caught and downgrade to empty lists.
"""

import html
import json
import logging
import re
import ssl
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

USER_AGENT = "FollowNews/3.0 (weekly-feedback bot)"
TIMEOUT = 10
_SSL_CTX = ssl.create_default_context()


def _truncate(text: str, limit: int = 200) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _http_get_json(url: str) -> Optional[Dict]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (URLError, HTTPError, json.JSONDecodeError, TimeoutError) as e:
        logging.debug(f"HTTP fetch failed for {url}: {e}")
        return None


# ─── Hacker News ─────────────────────────────────────────────────────────────

HN_ITEM_PATTERN = re.compile(r"news\.ycombinator\.com/item\?id=(\d+)")
HN_API = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


def _extract_hn_id(url: str) -> Optional[str]:
    m = HN_ITEM_PATTERN.search(url or "")
    return m.group(1) if m else None


def fetch_hn_top_comments(url: str, max_count: int = 5) -> List[Dict]:
    """Fetch top-level comments from a Hacker News story.

    Returns up to max_count comments sorted by HN's own thread ordering
    (which roughly correlates with karma). Empty list on any failure.
    """
    story_id = _extract_hn_id(url)
    if not story_id:
        return []
    return _fetch_hn_story_comments(story_id, max_count)


def _fetch_hn_story_comments(story_id: str, max_count: int) -> List[Dict]:
    """Inner helper: fetch comments given a known HN story id."""
    story = _http_get_json(HN_API.format(id=story_id))
    if not story or "kids" not in story:
        return []

    comments: List[Dict] = []
    for kid_id in story["kids"][: max_count * 2]:  # over-fetch in case some are deleted
        if len(comments) >= max_count:
            break
        comment_data = _http_get_json(HN_API.format(id=kid_id))
        if not comment_data or comment_data.get("deleted") or comment_data.get("dead"):
            continue
        text = comment_data.get("text") or ""
        # Strip basic HTML tags and unescape entities (HN comments are HTML)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        if not text.strip():
            continue
        comments.append({
            "platform": "hn",
            "content": _truncate(text, 200),
            "author": comment_data.get("by", "anonymous"),
            "likes": 0,  # HN doesn't expose comment karma via API
            "url": f"https://news.ycombinator.com/item?id={kid_id}",
        })
        time.sleep(0.1)  # gentle throttling

    return comments


# ─── HN Algolia title search (fallback when article link isn't HN) ───

HN_ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=5&query={query}"
HN_ALGOLIA_BRAND_SEARCH = (
    "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=10"
    "&query={query}&numericFilters=created_at_i>{since}"
)

# Common noise words that should NOT be used as brand search terms.
_BRAND_NOISE_WORDS = {
    "release", "releases", "released", "version", "the", "and", "or", "with",
    "from", "for", "into", "onto", "blog", "post", "now", "new", "introducing",
    "launches", "launched", "announcing", "announces", "this", "that", "open",
    "source", "github", "codes", "code", "model", "models", "agent", "agents",
    "ai", "llm", "tool", "tools", "framework", "library", "based",
    "free", "weekly", "daily", "today", "tomorrow", "yesterday",
    "how", "why", "what", "where", "when", "who", "your", "you", "are",
}


def _strip_title_for_search(title: str) -> str:
    """Make a title query Algolia-friendly: drop release prefixes / emojis / version tags."""
    t = (title or "").strip()
    # Drop common prefixes like "[Tier 1]", "🔥", "[bilibili 热搜]" etc
    t = re.sub(r"^[\[\(【].*?[\]\)】]\s*", "", t)
    t = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", t)  # emojis & misc symbols
    # Drop trailing version tags like "v2026.5.31-beta.4"
    t = re.sub(r"\s+v?\d+(\.\d+)+[\w.\-]*$", "", t)
    return t.strip()[:120]


def _extract_brand_terms(article: Dict, limit: int = 3) -> List[str]:
    """Extract searchable brand/project tokens from article title + link.

    Priority:
      1. GitHub repo name from `link` (most reliable for release announcements)
      2. First few alphanumeric tokens in title (excluding noise words / versions)

    Returns up to `limit` lowercase terms ranked most-specific first.
    """
    terms: List[str] = []
    seen: set = set()

    link = (article.get("link") or "").lower()
    m = re.search(r"github\.com/([\w\.\-]+)/([\w\.\-]+)(?:/|$)", link)
    if m:
        owner, repo = m.group(1), m.group(2)
        # repo name is more distinctive than owner (e.g. "openclaw" > "openclaw-org")
        for tok in (repo, owner):
            tok = tok.strip(".-").lower()
            if tok and tok not in seen and len(tok) >= 3 and tok not in _BRAND_NOISE_WORDS:
                terms.append(tok)
                seen.add(tok)

    title = article.get("title") or ""
    # Strip "owner/repo: " prefix that GitHub trending feeds include
    title = re.sub(r"^[\w\.\-]+/[\w\.\-]+:\s*", "", title)
    # Keep alphanumeric + hyphen, drop everything else
    raw = re.sub(r"[^\w\s\-]", " ", title)
    for tok_raw in raw.split():
        tok = tok_raw.strip(".-").lower()
        if not tok or tok in seen:
            continue
        if tok in _BRAND_NOISE_WORDS:
            continue
        # Skip version-shaped tokens (v1.2.3, 2026, 4.6, etc.)
        if re.match(r"^v?\d+([\.\-]\d+)*[\w\-]*$", tok):
            continue
        if len(tok) < 3:
            continue
        terms.append(tok)
        seen.add(tok)
        if len(terms) >= limit + 2:
            break

    return terms[:limit]


def find_hn_story_by_brand(
    brand: str, since_epoch: int, min_points: int = 3
) -> Optional[str]:
    """Search HN Algolia for stories matching `brand` since `since_epoch` (unix).

    Returns the highest-points story_id from hits with >= min_points, or None.
    Used by enrich's brand-search fallback when an announcement has no direct
    HN link and `_extract_brand_terms` identified a distinctive project token.
    """
    if not brand or len(brand) < 3:
        return None
    from urllib.parse import quote
    url = HN_ALGOLIA_BRAND_SEARCH.format(query=quote(brand), since=since_epoch)
    payload = _http_get_json(url)
    if not payload:
        return None
    hits = [
        h for h in (payload.get("hits") or [])
        if (h.get("points") or 0) >= min_points and h.get("objectID")
    ]
    if not hits:
        return None
    hits.sort(key=lambda h: h.get("points") or 0, reverse=True)
    return str(hits[0]["objectID"])


def find_hn_story_by_title(title: str, min_points: int = 5) -> Optional[str]:
    """Return the HN story id whose title best matches `title`.

    Algolia's `tags=story` returns stories sorted by relevance. We pick the
    top hit whose points >= min_points (filters out joke/dead stories).
    """
    q = _strip_title_for_search(title)
    if len(q) < 6:
        return None
    from urllib.parse import quote
    payload = _http_get_json(HN_ALGOLIA_SEARCH.format(query=quote(q)))
    if not payload:
        return None
    hits = payload.get("hits") or []
    # Sort by points desc among the first few hits
    hits = [h for h in hits if (h.get("points") or 0) >= min_points and h.get("objectID")]
    if not hits:
        return None
    hits.sort(key=lambda h: h.get("points") or 0, reverse=True)
    return str(hits[0]["objectID"])


# ─── Reddit ──────────────────────────────────────────────────────────────────

REDDIT_HOST_PATTERN = re.compile(r"(?:www\.|old\.|new\.)?reddit\.com")


def _build_reddit_json_url(url: str) -> Optional[str]:
    """Convert any Reddit comment URL to its .json API form."""
    if not url:
        return None
    parsed = urlparse(url)
    if not REDDIT_HOST_PATTERN.search(parsed.netloc):
        return None
    path = parsed.path.rstrip("/")
    if not path:
        return None
    return f"https://www.reddit.com{path}.json"


def fetch_reddit_top_comments(url: str, max_count: int = 5) -> List[Dict]:
    """Fetch top comments from a Reddit submission, sorted by score.

    Returns up to max_count top-level comments with content/author/score.
    Empty list on any failure (deleted post, network error, rate limit, etc.).
    """
    api_url = _build_reddit_json_url(url)
    if not api_url:
        return []

    data = _http_get_json(api_url)
    if not isinstance(data, list) or len(data) < 2:
        return []

    listing = data[1].get("data", {}).get("children", [])
    comments: List[Dict] = []
    for child in listing:
        if len(comments) >= max_count:
            break
        if child.get("kind") != "t1":
            continue
        c = child.get("data", {})
        body = c.get("body") or ""
        if not body.strip() or body in ("[removed]", "[deleted]"):
            continue
        body = html.unescape(body)
        comments.append({
            "platform": "reddit",
            "content": _truncate(body, 200),
            "author": c.get("author", "[deleted]"),
            "likes": int(c.get("score") or 0),
            "url": "https://www.reddit.com" + (c.get("permalink") or ""),
        })

    # Reddit returns comments in their default sort (usually "confidence"); resort by score
    comments.sort(key=lambda x: x["likes"], reverse=True)
    return comments[:max_count]


# ─── Dispatch ────────────────────────────────────────────────────────────────

def enrich_article_with_comments(
    article: Dict,
    max_per_source: int = 5,
    used_story_ids: Optional[set] = None,
    days_window: int = 7,
) -> List[Dict]:
    """Inspect an article's url and reactions, fetch comments where possible.

    Returns a list of enriched comment dicts; also stores under article["enriched_comments"].

    `used_story_ids`: optional set of HN story IDs already claimed by previous
    enrichment calls in this run. The brand-search and title-search fallbacks
    skip stories whose ID is already in the set, preventing N article variants
    (e.g. multiple release versions of the same project) from all collapsing
    onto the same fuzzy-matched HN thread. The set is mutated in place.

    `days_window`: how far back (in days) to look for HN stories during the
    brand-search fallback. Defaults to 7 to align with the weekly report window.
    """
    enriched: List[Dict] = []

    # Try the article's own link first (if it itself is an HN/Reddit thread)
    primary_url = article.get("link") or article.get("reddit_url") or ""
    for fetcher in (fetch_hn_top_comments, fetch_reddit_top_comments):
        if len(enriched) >= max_per_source:
            break
        got = fetcher(primary_url, max_count=max_per_source - len(enriched))
        enriched.extend(got)

    # Then walk reactions
    for reaction in article.get("reactions", []) or []:
        if len(enriched) >= max_per_source * 2:  # cap total
            break
        r_url = reaction.get("link") or reaction.get("reddit_url") or ""
        for fetcher in (fetch_hn_top_comments, fetch_reddit_top_comments):
            got = fetcher(r_url, max_count=max(2, max_per_source - len(enriched)))
            enriched.extend(got)

    # ── Fallbacks: brand-keyword HN search, then title fuzzy match ──
    # When the announcement has no direct HN/Reddit link, proactively look for
    # any HN thread about the same brand/project within the report window.
    # This is what unlocks community voice for company-blog announcements
    # (Anthropic, OpenAI, Google) that don't seed HN links themselves.
    if not enriched:
        since_epoch = int(time.time()) - max(1, days_window) * 86400
        story_id: Optional[str] = None
        matched_via = None

        for brand in _extract_brand_terms(article):
            candidate = find_hn_story_by_brand(brand, since_epoch)
            if not candidate:
                continue
            if used_story_ids is not None and candidate in used_story_ids:
                logging.debug(
                    f"enrich brand-search skipped: HN story {candidate} already claimed "
                    f"(brand='{brand}', title='{(article.get('title','') or '')[:60]}')"
                )
                continue
            story_id = candidate
            matched_via = f"brand={brand}"
            break

        if not story_id:
            # Last resort: title fuzzy match (kept for cases brand extraction fails)
            candidate = find_hn_story_by_title(article.get("title", "") or "")
            if candidate and (used_story_ids is None or candidate not in used_story_ids):
                story_id = candidate
                matched_via = "title-fuzzy"

        if story_id:
            got = _fetch_hn_story_comments(story_id, max_per_source)
            if got:
                logging.debug(
                    f"enrich {matched_via} hit: HN story {story_id} for "
                    f"'{(article.get('title','') or '')[:60]}'"
                )
                enriched.extend(got)
                if used_story_ids is not None:
                    used_story_ids.add(story_id)

    if enriched:
        article["enriched_comments"] = enriched
    return enriched
