#!/usr/bin/env python3
"""
Comment enrichment helper for follow-news weekly digest.

For Tier 1 announcements' related reactions, fetch top community comments from
HN and V2EX (both zero-auth JSON APIs) so the weekly report can quote real
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
    # Generic English words that surface from title-token fallback and match
    # unrelated high-points HN stories (the source of mis-attributed comments).
    "says", "say", "said", "former", "official", "officially", "companies",
    "company", "have", "has", "had", "try", "tries", "together", "application",
    "applications", "expanding", "expand", "designed", "design", "takes", "take",
    "use", "uses", "using", "get", "gets", "make", "makes", "want", "wants",
    "help", "helps", "build", "builds", "building", "built", "over", "past",
    "here", "there", "more", "most", "very", "much", "just", "like", "also",
    "been", "being", "them", "they", "their", "our", "its", "first", "data",
    "about", "after", "before", "will", "would", "should", "could", "can",
    "not", "but", "all", "any", "out", "off", "via", "per", "than", "then",
}


def _significant_tokens(text: str) -> set:
    """Lowercased content tokens (len>=3, not noise, not version-shaped).

    Used for title↔title overlap relevance checks: a brand-search / title-fuzzy
    HN hit is only accepted if its title shares enough significant tokens with
    the source article, so a generic keyword can't drag in an unrelated thread.
    """
    toks: set = set()
    raw = re.sub(r"[^\w\s\-]", " ", text or "")
    for t in raw.split():
        t = t.strip(".-").lower()
        if len(t) < 3 or t in _BRAND_NOISE_WORDS:
            continue
        if re.match(r"^v?\d+([\.\-]\d+)*[\w\-]*$", t):
            continue
        toks.add(t)
    return toks


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
    brand: str, since_epoch: int, min_points: int = 3,
    source_title: Optional[str] = None, min_overlap: int = 2,
) -> Optional[str]:
    """Search HN Algolia for stories matching `brand` since `since_epoch` (unix).

    Returns the highest-points story_id from hits with >= min_points, or None.
    Used by enrich's brand-search fallback when an announcement has no direct
    HN link and `_extract_brand_terms` identified a distinctive project token.

    Relevance guard (mirrors `find_v2ex_topic_by_brand`): when `source_title` is
    given, a hit is only accepted if its title shares >= `min_overlap` significant
    tokens with the source article. Without this, a generic keyword like "former"
    matches the single highest-points story containing that word (e.g. an unrelated
    Greenspan thread) and drags in mis-attributed comments. Requiring brand + at
    least one more shared token keeps precision high (better no comments than wrong
    comments).
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
    if source_title:
        src_tokens = _significant_tokens(source_title)
        for h in hits:
            title = h.get("title") or h.get("story_title") or ""
            if len(_significant_tokens(title) & src_tokens) >= min_overlap:
                return str(h["objectID"])
        return None
    return str(hits[0]["objectID"])


def find_hn_story_by_title(title: str, min_points: int = 5, min_overlap: int = 2) -> Optional[str]:
    """Return the HN story id whose title best matches `title`.

    Algolia's `tags=story` returns stories sorted by relevance. We pick the
    top hit whose points >= min_points (filters out joke/dead stories) AND that
    shares >= `min_overlap` significant tokens with `title` (relevance guard so a
    loose fuzzy match can't attach an unrelated thread's comments).
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
    src_tokens = _significant_tokens(title)
    for h in hits:
        hit_title = h.get("title") or h.get("story_title") or ""
        if len(_significant_tokens(hit_title) & src_tokens) >= min_overlap:
            return str(h["objectID"])
    return None


# ─── V2EX (zero-auth Chinese tech community) ─────────────────────────────────
#
# Two zero-auth endpoints, no API key:
#   discovery — sov2ex.com community ES index: /api/search?q=<kw> (V2EX has no
#               first-party keyword search; sov2ex indexes topics + replies)
#   bodies    — v2ex.com/api/topics/show.json?id=<id>  (topic)
#               v2ex.com/api/replies/show.json?topic_id=<id>  (replies)
# This is the ONLY real Chinese *comment-text* source this phase — TrendRadar and
# the competitor-KOL plane fetch metadata only.

SOV2EX_SEARCH = "https://www.sov2ex.com/api/search?q={query}&size=10&sort=sumup"
V2EX_TOPIC_API = "https://www.v2ex.com/api/topics/show.json?id={id}"
V2EX_REPLIES_API = "https://www.v2ex.com/api/replies/show.json?topic_id={id}"


def find_v2ex_topic_by_brand(
    brand: str, max_age_days: int = 90, min_replies: int = 2
) -> Optional[str]:
    """Search the sov2ex ES index for a *recent, relevant* V2EX topic about `brand`.

    Returns the most-replied qualifying topic id (str), or None. Zero-auth.

    sov2ex has no first-party recency/relevance filtering, so a bare keyword
    query happily returns decade-old unrelated threads (e.g. "professor" → a
    2017 PHP-course post). We guard three ways before accepting a hit:
      - recency: `created` within `max_age_days` (Chinese communities lag the
        English news cycle, so this is looser than the 7-day report window)
      - relevance: the brand term must actually appear in the topic title/body
      - discussion: at least `min_replies` replies (a 0-reply thread has no
        community voice to quote anyway)
    """
    if not brand or len(brand) < 3:
        return None
    from urllib.parse import quote
    payload = _http_get_json(SOV2EX_SEARCH.format(query=quote(brand)))
    if not payload:
        return None
    hits = payload.get("hits") or []
    cutoff = time.time() - max(1, max_age_days) * 86400
    brand_lc = brand.lower()
    scored = []
    for h in hits:
        src = h.get("_source") or {}
        tid = src.get("id")
        if not tid:
            continue
        replies = int(src.get("replies") or 0)
        if replies < min_replies:
            continue
        haystack = f"{src.get('title','')} {src.get('content','')}".lower()
        if brand_lc not in haystack:
            continue
        created = src.get("created") or ""
        if created:
            try:
                ts = time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S"))
                if ts < cutoff:
                    continue
            except (ValueError, OverflowError):
                pass  # unparseable timestamp → don't reject on recency alone
        scored.append((replies, str(tid)))
    if not scored:
        return None
    scored.sort(reverse=True)  # most-replied first = hottest discussion
    return scored[0][1]


def fetch_v2ex_comments(topic_id: str, max_count: int = 5) -> List[Dict]:
    """Fetch top replies for a V2EX topic via the zero-auth JSON API.

    V2EX's v1 reply API exposes no per-reply like count, so `likes` is 0.
    Returns up to max_count replies (API returns chronological; we take the
    first max_count). Empty list on any failure.
    """
    if not topic_id:
        return []
    topics = _http_get_json(V2EX_TOPIC_API.format(id=topic_id))
    topic_url = ""
    if isinstance(topics, list) and topics:
        topic_url = topics[0].get("url") or ""
    elif isinstance(topics, dict):
        topic_url = topics.get("url") or ""

    replies = _http_get_json(V2EX_REPLIES_API.format(id=topic_id))
    if not isinstance(replies, list):
        return []

    comments: List[Dict] = []
    for r in replies:
        if len(comments) >= max_count:
            break
        content = (r.get("content") or "").strip()
        if not content:
            continue
        member = r.get("member") or {}
        comments.append({
            "platform": "v2ex",
            "content": _truncate(html.unescape(content), 200),
            "author": member.get("username", "anonymous"),
            "likes": 0,  # V2EX v1 API exposes no per-reply like count
            "url": topic_url or f"https://www.v2ex.com/t/{topic_id}",
        })
    return comments


# ─── 知乎 / B站 (cred-gated stubs) ────────────────────────────────────────────
#
# Both require a logged-in cookie for any comment-text access. Without it they
# soft-degrade to [] (the report annotates coverage as skipped). Wired as
# best-effort: presence of ZHIHU_COOKIE / BILIBILI_COOKIE env vars unlocks them.

def fetch_zhihu_comments(query: str, max_count: int = 5) -> List[Dict]:
    """Cred-gated stub: needs ZHIHU_COOKIE. Returns [] when unconfigured."""
    import os
    if not os.environ.get("ZHIHU_COOKIE"):
        logging.debug("zhihu enrichment skipped: no ZHIHU_COOKIE")
        return []
    # Implementation deferred — cookie plumbing only; keep soft-degrade contract.
    logging.debug("zhihu enrichment: ZHIHU_COOKIE present but fetch not implemented yet")
    return []


def fetch_bilibili_comments(query: str, max_count: int = 5) -> List[Dict]:
    """Cred-gated stub: needs BILIBILI_COOKIE. Returns [] when unconfigured."""
    import os
    if not os.environ.get("BILIBILI_COOKIE"):
        logging.debug("bilibili enrichment skipped: no BILIBILI_COOKIE")
        return []
    logging.debug("bilibili enrichment: BILIBILI_COOKIE present but fetch not implemented yet")
    return []


# ─── Dispatch ────────────────────────────────────────────────────────────────

def enrich_article_with_comments(
    article: Dict,
    max_per_source: int = 5,
    used_story_ids: Optional[set] = None,
    days_window: int = 7,
    used_v2ex_ids: Optional[set] = None,
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

    `used_v2ex_ids`: same dedup contract as `used_story_ids` but for V2EX topic
    ids claimed by the Chinese-voice brand search. Mutated in place.
    """
    enriched: List[Dict] = []

    # Try the article's own link first (if it itself is an HN thread)
    primary_url = article.get("link") or ""
    for fetcher in (fetch_hn_top_comments,):
        if len(enriched) >= max_per_source:
            break
        got = fetcher(primary_url, max_count=max_per_source - len(enriched))
        enriched.extend(got)

    # Then walk reactions
    for reaction in article.get("reactions", []) or []:
        if len(enriched) >= max_per_source * 2:  # cap total
            break
        r_url = reaction.get("link") or ""
        for fetcher in (fetch_hn_top_comments,):
            got = fetcher(r_url, max_count=max(2, max_per_source - len(enriched)))
            enriched.extend(got)

    # ── Fallbacks: brand-keyword HN search, then title fuzzy match ──
    # When the announcement has no direct HN link, proactively look for
    # any HN thread about the same brand/project within the report window.
    # This is what unlocks community voice for company-blog announcements
    # (Anthropic, OpenAI, Google) that don't seed HN links themselves.
    if not enriched:
        since_epoch = int(time.time()) - max(1, days_window) * 86400
        story_id: Optional[str] = None
        matched_via = None
        src_title = article.get("title", "") or ""

        for brand in _extract_brand_terms(article):
            candidate = find_hn_story_by_brand(brand, since_epoch, source_title=src_title)
            if not candidate:
                continue
            if used_story_ids is not None and candidate in used_story_ids:
                logging.debug(
                    f"enrich brand-search skipped: HN story {candidate} already claimed "
                    f"(brand='{brand}', title='{src_title[:60]}')"
                )
                continue
            story_id = candidate
            matched_via = f"brand={brand}"
            break

        if not story_id:
            # Last resort: title fuzzy match (kept for cases brand extraction fails)
            candidate = find_hn_story_by_title(src_title)
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

    # ── Chinese voice: V2EX brand search (additive, zero-auth) ──
    # Always attempt so the report carries Chinese community sentiment, not only
    # English HN. Brand terms (often English product names like "Cursor"
    # / "Claude") are found even in Chinese threads. Deduped via used_v2ex_ids.
    for brand in _extract_brand_terms(article):
        topic_id = find_v2ex_topic_by_brand(brand)
        if not topic_id:
            continue
        if used_v2ex_ids is not None and topic_id in used_v2ex_ids:
            continue
        got = fetch_v2ex_comments(topic_id, max_per_source)
        if got:
            logging.debug(
                f"enrich v2ex brand={brand} hit: topic {topic_id} for "
                f"'{(article.get('title','') or '')[:60]}'"
            )
            enriched.extend(got)
            if used_v2ex_ids is not None:
                used_v2ex_ids.add(topic_id)
            break

    if enriched:
        article["enriched_comments"] = enriched
    return enriched
