#!/usr/bin/env python3
"""
Weekly feedback aggregator for follow-news.

Pools the last N days of archived daily merged JSON into a single weekly digest
that pairs AI tech announcements with downstream community reactions
(HN / Reddit / Twitter / Web search / TrendRadar 中文社区).

Usage:
    python3 weekly-feedback.py \\
      --archive-dir <workspace>/archive/follow-news \\
      --days 7 \\
      --output /tmp/td-weekly-merged.json \\
      --markdown /tmp/td-weekly.md

Output JSON shape matches scripts/merge-sources.py output so summarize-merged.py
can render it. Each article in topics[*].articles may additionally carry a
"reactions" list of related downstream articles.

Reuses merge_article_sources() and normalize_title() from merge-sources.py
for cross-day deduplication and multi-source detection.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).parent


def setup_logging(verbose: bool) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def _load_merge_module():
    """Load merge-sources.py as a module so we can reuse its dedup/multi-source logic."""
    return SourceFileLoader("merge_sources", str(SCRIPTS_DIR / "merge-sources.py")).load_module()


DATE_FILE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def collect_daily_files(archive_dir: Path, days: int) -> List[Path]:
    """Find archived daily-json files within the last N days, sorted oldest→newest."""
    daily_dir = archive_dir / "daily-json"
    if not daily_dir.is_dir():
        return []
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    files = []
    for p in daily_dir.iterdir():
        if not p.is_file():
            continue
        m = DATE_FILE_PATTERN.match(p.name)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= cutoff_date:
            files.append((d, p))
    files.sort()
    return [p for _, p in files]


def flatten_daily_json(daily_files: List[Path], logger: logging.Logger) -> List[Dict[str, Any]]:
    """Read each daily merged JSON and flatten topics[*].articles into a single list."""
    articles: List[Dict[str, Any]] = []
    for path in daily_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Skipping unreadable archive {path.name}: {e}")
            continue

        topics = data.get("topics", {})
        if isinstance(topics, dict):
            for topic_id, topic_data in topics.items():
                for a in topic_data.get("articles", []) or []:
                    # Ensure primary_topic is set (some early articles may not have it)
                    a.setdefault("primary_topic", topic_id)
                    articles.append(a)
        elif isinstance(topics, list):
            for topic_data in topics:
                for a in topic_data.get("articles", []) or []:
                    articles.append(a)

    logger.info(f"Pooled {len(articles)} articles from {len(daily_files)} day(s) of archives")
    return articles


def _flatten_merged_json(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten one merged JSON's topics into a flat article list."""
    articles: List[Dict[str, Any]] = []
    for topic_id, topic_data in (data.get("topics") or {}).items():
        for a in topic_data.get("articles", []) or []:
            a.setdefault("primary_topic", topic_id)
            articles.append(a)
    return articles


def fetch_now(args: argparse.Namespace, logger: logging.Logger, merge_mod) -> List[Dict[str, Any]]:
    """On-demand fresh 7-day fetch.

    Orchestrates:
      1) run-pipeline.py --hours (days*24) → /tmp/td-merged-weekly.json
      2) TrendRadar weekly_export.py if --trendradar-dir set → produces weekly RSS
         (TrendRadar RSS is already a registered source in workspace config, so run-pipeline picks it up)
      3) Optional llm-filter.py if --llm-filter set

    Returns flat articles list.
    """
    import subprocess
    import tempfile

    # Force Python UTF-8 mode in all subprocesses (fixes Windows GBK encoding issues
    # in upstream fetch-rss.py / fetch-web.py / fetch-github.py / etc. which use
    # open() without explicit encoding=).
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"

    hours = args.days * 24

    # ── 1. Trigger TrendRadar weekly export (if path provided / auto-detected) ──
    trendradar_dir = args.trendradar_dir
    if trendradar_dir is None:
        # Auto-detect: ../TrendRadar relative to follow-news repo root
        repo_root = SCRIPTS_DIR.parent
        candidate = repo_root.parent / "TrendRadar"
        if candidate.is_dir():
            trendradar_dir = candidate
            logger.info(f"Auto-detected TrendRadar at {trendradar_dir}")

    if trendradar_dir and trendradar_dir.is_dir():
        logger.info(f"Running TrendRadar weekly_export.py --days {args.days}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "trendradar.report.weekly_export",
                 "--days", str(args.days), "--frequency-file", "ai_focus.txt"],
                cwd=str(trendradar_dir),
                check=False,
                timeout=120,
                env=child_env,
            )
        except Exception as e:
            logger.warning(f"TrendRadar weekly export failed: {e} (continuing without it)")
    else:
        logger.info("Skipping TrendRadar weekly export (no --trendradar-dir provided or auto-detected)")

    # ── 2. Run follow-news run-pipeline.py --hours N ──
    merged_tmp = Path(tempfile.gettempdir()) / "td-fetch-now-merged.json"
    logger.info(f"Running follow-news run-pipeline.py --hours {hours} (this may take 3-8 min)...")
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "run-pipeline.py"),
        "--hours", str(hours),
        "--output", str(merged_tmp),
        "--no-archive-json",  # no need to pollute archive in fetch-now mode
    ]
    if args.verbose:
        cmd.append("--verbose")

    # Pass --config if there's a sibling workspace
    workspace_config = SCRIPTS_DIR.parent / "workspace" / "config"
    if workspace_config.is_dir():
        cmd += ["--config", str(workspace_config)]

    try:
        result = subprocess.run(cmd, check=False, timeout=900, env=child_env)
        if result.returncode != 0:
            logger.error(f"run-pipeline.py exited with code {result.returncode}")
            return []
    except subprocess.TimeoutExpired:
        logger.error("run-pipeline.py timed out (>15 min)")
        return []
    except Exception as e:
        logger.error(f"run-pipeline.py failed: {e}")
        return []

    # ── 3. Optional LLM filter pass ──
    final_merged = merged_tmp
    if args.llm_filter:
        filtered_tmp = Path(tempfile.gettempdir()) / "td-fetch-now-filtered.json"
        logger.info("Running llm-filter.py (semantic dedup + announcement verification)...")
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "llm-filter.py"),
                 "--input", str(merged_tmp),
                 "--output", str(filtered_tmp)] + (["--verbose"] if args.verbose else []),
                check=False, timeout=600,
                env=child_env,
            )
            if filtered_tmp.exists():
                final_merged = filtered_tmp
        except Exception as e:
            logger.warning(f"LLM filter failed, using unfiltered data: {e}")

    # ── 4. Load and flatten ──
    if not final_merged.exists():
        logger.error(f"Merged file not found: {final_merged}")
        return []

    with open(final_merged, "r", encoding="utf-8") as f:
        merged_data = json.load(f)

    articles = _flatten_merged_json(merged_data)
    logger.info(f"Fresh fetch produced {len(articles)} articles")
    return articles


# Heuristic patterns for announcement detection.
ANNOUNCE_TITLE_PATTERN = re.compile(
    r"\b(release[ds]?|launch(?:ed|ing)?|announc(?:e|es|ed|ing)|introduc(?:e|es|ed|ing)|"
    r"unveil(?:s|ed|ing)?|ships?|shipped|open[- ]?sourc(?:e|es|ed|ing)|"
    r"v\d+(?:\.\d+)+|version \d+|\d+\.\d+ released)\b|"
    r"(发布|开源|上线|推出|首发|首次|放出|开放|更新)",
    re.IGNORECASE,
)

REACTION_SOURCE_TYPES = {"reddit", "twitter", "web"}
REACTION_RSS_ID_PATTERN = re.compile(r"hn|hacker[- ]?news|lobsters|trendradar", re.IGNORECASE)

# Tier 1 vendor patterns — matched against title + source_name.
# Keep these aligned with references/prompts/competitor-monitor.md.
TIER1_VENDOR_PATTERNS = [
    # Foundation model frontier labs
    r"\bOpenAI\b", r"\bChatGPT\b", r"\bGPT-?\d", r"\bo[1-9](?:-(?:mini|pro|preview))?\b",
    r"\bAnthropic\b", r"\bClaude\b",
    r"\bGoogle\s?DeepMind\b", r"\bGemini\b",
    r"\bxAI\b", r"\bGrok\b",
    # Open-source heavyweights
    r"\bMeta\b.{0,20}\bAI\b", r"\bLlama\b", r"\bLLaMA\b",
    r"\bMistral\b", r"\bMixtral\b",
    # China model labs
    r"\bDeepSeek\b", r"深度求索", r"幻方",
    r"\bQwen\b", r"通义",
    r"\bKimi\b", r"月之暗面", r"\bMoonshot\b",
    r"\bGLM\b", r"\bChatGLM\b", r"智谱",
    r"\bMiniMax\b",
    r"\bStep[- ]?\d", r"阶跃星辰",
    # Agent products
    r"\bCursor\b.*(?:agent|release|launch|update|\bv?\d)",
    r"\bDevin\b",
    r"\bClaude Code\b",
    r"\bGitHub Copilot\b",
    r"\bWindsurf\b",
    # Infra (only if release/launch)
    r"\bNVIDIA\b.{0,30}(?:Blackwell|Hopper|H[12]\d\d|B[12]\d\d|GB\d+)",
    r"\bAMD\b.{0,30}(?:MI\d{3,}|Instinct)",
    r"昇腾.{0,30}(?:发布|新一代|系列)",
]
TIER1_VENDOR_RE = re.compile("|".join(TIER1_VENDOR_PATTERNS), re.IGNORECASE)

# SDK / client-library release noise: GitHub auto-releases of language bindings
# (openai-python, anthropic-sdk-python, langchain-anthropic, mem0 ts-v..., etc.)
# match the Tier 1 vendor regex via brand name but are not product announcements
# — no one discusses "openai-python v2.40.0" on HN/Reddit. Demote to tier3 so the
# weekly feedback report stops wasting Tier-1 slots on package bumps.
SDK_RELEASE_PATTERN = re.compile(
    r"(?ix)"
    r"(?:"
    # Language/binding suffixes: -python, -js, -ts, -sdk, -cli, -core, -api, -client, -lib, -node
    r"\b\S*-(?:python|js|ts|node|sdk|cli|core|api|client|lib|go|rust|java|dotnet|ruby)\b"
    # OR PyPI release notation
    r"|=="
    # OR typescript-style "ts-v..." version prefix
    r"|\bts-v\d"
    # OR explicit "SDK" / "client library" mention in title
    r"|\b(?:SDK|client\s+library|官方\s*SDK)\b"
    r")"
)


CLICKBAIT_PATTERN = re.compile(
    r"震惊|刚刚！|太可怕|未来已来|颠覆了一切|碾压|爆款|逆天",
    re.IGNORECASE,
)


def classify_article(article: Dict[str, Any]) -> str:
    """Return 'announcement' / 'reaction' / 'neutral'."""
    src_type = article.get("source_type", "")
    title = article.get("title", "") or ""
    src_id = article.get("source_id", "") or ""

    # Reactions: discussion-y sources, plus HN-style RSS aggregators
    if src_type in REACTION_SOURCE_TYPES:
        return "reaction"
    if src_type == "rss" and REACTION_RSS_ID_PATTERN.search(src_id):
        return "reaction"

    # Announcements: official releases / GitHub releases / strong RSS sources with launch wording
    if src_type in {"github", "podcast"}:
        return "announcement"
    if src_type == "rss":
        if article.get("priority") and ANNOUNCE_TITLE_PATTERN.search(title):
            return "announcement"
        # Also accept multi-source RSS articles as announcements (covered widely = announcement-like)
        if article.get("multi_source") and article.get("source_count", 0) >= 2:
            return "announcement"

    return "neutral"


def assign_tier(article: Dict[str, Any]) -> str:
    """Heuristic Tier assignment for announcements only.

    Returns "tier1" / "tier2" / "tier3" / "tierX".
    OpenClaw agent reads this as a hint and may revise per competitor-monitor.md.
    """
    title = article.get("title", "") or ""
    source_name = article.get("source_name", "") or ""
    combined = f"{title} {source_name}"

    # Clickbait / blacklist → drop entirely
    if CLICKBAIT_PATTERN.search(combined):
        return "tierX"

    # SDK / client-library release: matched Tier 1 brand by name but is just a
    # package version bump (openai-python, anthropic-sdk-python, langchain-*, etc.)
    # No community discussion → don't waste a Tier 1 slot. Cap at tier3.
    if SDK_RELEASE_PATTERN.search(title):
        return "tier3"

    qs = article.get("quality_score", 0) or 0
    src_count = article.get("source_count", 0) or 0
    multi = article.get("multi_source", False)

    # Tier 1 signals (any one is enough)
    if TIER1_VENDOR_RE.search(combined):
        return "tier1"
    if src_count >= 3:
        return "tier1"
    if qs >= 22:
        return "tier1"

    # Tier 2 signals
    if multi and src_count >= 2:
        return "tier2"
    if qs >= 15:
        return "tier2"

    return "tier3"


def _project_key(article: Dict[str, Any]) -> Optional[str]:
    """Return a stable key identifying the underlying project for same-project
    dedup. Returns None when no reliable key can be derived (article participates
    as itself, no collapsing).

    Strategy:
    - GitHub releases: use `repo_full_name`, falling back to parsing the link
      path (`/owner/repo/releases/tag/...` → `owner/repo`).
    - Other sources: None (don't try to fuzzy-collapse non-GitHub announcements
      — too easy to wrongly merge sibling launches from the same vendor).
    """
    if article.get("source_type") != "github":
        return None
    repo = article.get("repo_full_name") or ""
    if repo:
        return f"gh:{repo.lower()}"
    link = article.get("link") or ""
    m = re.search(r"github\.com/([^/]+/[^/]+)/", link)
    if m:
        return f"gh:{m.group(1).lower()}"
    return None


def dedup_same_project(
    announcements: List[Dict[str, Any]],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Collapse multiple announcements from the same project into one canonical.

    The pre-existing cross-day dedup operates on title/URL hash, so distinct
    release versions of the same repo (openclaw v2026.5.28 / v2026.5.31-beta.4
    / v2026.6.1) all survive as separate articles — and each grabs a Tier 1
    slot, crowding out actually diverse events. Here we group by project key
    and keep only the most recent release per project, merging signals (max
    source_count, max quality_score, union of reactions) from collapsed
    siblings.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    standalone: List[Dict[str, Any]] = []
    for a in announcements:
        key = _project_key(a)
        if key is None:
            standalone.append(a)
        else:
            groups.setdefault(key, []).append(a)

    collapsed: List[Dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) == 1:
            collapsed.append(items[0])
            continue
        # Pick canonical: most recent published_at, ties broken by quality_score
        def _sort_key(a: Dict[str, Any]):
            d = _parse_date(a.get("published_at") or a.get("date"))
            return (d or datetime.min.replace(tzinfo=timezone.utc), a.get("quality_score", 0) or 0)
        items.sort(key=_sort_key, reverse=True)
        canonical = items[0]
        siblings = items[1:]
        # Merge signals from siblings into canonical
        canonical["quality_score"] = max(
            (it.get("quality_score", 0) or 0) for it in items
        )
        # Bump source_count by the count of collapsed siblings (each was a separate release post)
        canonical["source_count"] = (canonical.get("source_count", 0) or 0) + len(siblings)
        if len(items) >= 2:
            canonical["multi_source"] = True
        # Union reactions (dedup by URL)
        all_reactions = list(canonical.get("reactions", []) or [])
        seen_urls = {(r.get("link") or r.get("url") or "") for r in all_reactions}
        for sib in siblings:
            for r in sib.get("reactions", []) or []:
                u = r.get("link") or r.get("url") or ""
                if u and u not in seen_urls:
                    all_reactions.append(r)
                    seen_urls.add(u)
        if all_reactions:
            canonical["reactions"] = all_reactions
        canonical["_collapsed_siblings"] = [
            {"title": s.get("title", ""), "link": s.get("link", "")} for s in siblings
        ]
        # Mark siblings so they don't show up as orphan announcements in the
        # downstream regrouped JSON. The agent's prompt only acts on entries
        # whose _tier is tier1/2/3, so this keeps the report clean.
        for s in siblings:
            s["_classification"] = "dropped_sibling"
            s["_tier"] = "dropped_sibling"
            s["_collapsed_into"] = canonical.get("link") or canonical.get("title")
        logger.debug(
            f"Same-project dedup: collapsed {len(siblings)} siblings into '{canonical.get('title','')[:60]}' (key={key})"
        )
        collapsed.append(canonical)

    result = standalone + collapsed
    if len(result) < len(announcements):
        logger.info(
            f"Same-project dedup: {len(announcements)} → {len(result)} announcements "
            f"(collapsed {len(announcements) - len(result)} sibling releases)"
        )
    return result


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def pair_reactions(
    announcements: List[Dict[str, Any]],
    reactions: List[Dict[str, Any]],
    normalize_title,
    logger: logging.Logger,
    max_reactions_per_announcement: int = 5,
) -> None:
    """Mutates announcements: attach a 'reactions' list to each based on title overlap + topic match."""
    # Bucket reactions by normalized title for O(1) lookup; also keep flat list for fuzzy matches.
    norm_buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in reactions:
        nt = normalize_title(r.get("title", ""))
        norm_buckets.setdefault(nt, []).append(r)

    for ann in announcements:
        ann_norm = normalize_title(ann.get("title", ""))
        ann_topic = ann.get("primary_topic")
        ann_date = _parse_date(ann.get("date"))

        # 1) Exact normalized-title bucket hits
        candidates = list(norm_buckets.get(ann_norm, []))

        # 2) Token overlap fallback: any reaction sharing 2+ significant tokens
        ann_tokens = set(t for t in ann_norm.split() if len(t) > 2)
        if ann_tokens:
            for r in reactions:
                if r in candidates:
                    continue
                r_tokens = set(t for t in normalize_title(r.get("title", "")).split() if len(t) > 2)
                if len(ann_tokens & r_tokens) >= 2:
                    candidates.append(r)

        # Filter by topic + time-after-announcement
        filtered = []
        for r in candidates:
            if ann_topic and r.get("primary_topic") and r["primary_topic"] != ann_topic:
                continue
            r_date = _parse_date(r.get("date"))
            if ann_date and r_date and r_date < ann_date - timedelta(hours=12):
                continue
            filtered.append(r)

        # Sort by quality_score desc, then engagement
        def _react_key(r):
            metrics = r.get("metrics") or {}
            engagement = (
                metrics.get("like_count", 0)
                + r.get("score", 0)  # reddit upvotes
                + r.get("num_comments", 0)
            )
            return (r.get("quality_score", 0), engagement)

        filtered.sort(key=_react_key, reverse=True)
        if filtered:
            ann["reactions"] = filtered[:max_reactions_per_announcement]
            logger.debug(f"Paired {len(ann['reactions'])} reactions → '{ann.get('title','')[:60]}'")


def regroup_by_topic(articles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Rebuild topics dict in the same shape as merge-sources.py output."""
    topics: Dict[str, Dict[str, Any]] = {}
    for a in articles:
        pt = a.get("primary_topic") or "uncategorized"
        if pt not in topics:
            topics[pt] = {"count": 0, "articles": []}
        topics[pt]["articles"].append(a)
        topics[pt]["count"] += 1
    return topics


def render_markdown(
    annotated_articles: List[Dict[str, Any]],
    topics: Dict[str, Dict[str, Any]],
    days_used: int,
    days_requested: int,
    fetch_now: bool = False,
) -> str:
    """Build a human-readable weekly digest markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if fetch_now:
        header_window = f"生成时间: {now} UTC  |  覆盖窗口: 最近 {days_requested} 天（fetch-now 现抓）"
    else:
        header_window = (
            f"生成时间: {now} UTC  |  覆盖窗口: 最近 {days_used} 天"
            + (
                f" (请求 {days_requested} 天，archive 实际可用 {days_used})"
                if days_used < days_requested
                else ""
            )
        )
    lines: List[str] = [
        f"# 本周 AI 新技术 + 各社区反馈周报",
        f"",
        header_window,
        f"",
    ]

    if not fetch_now and days_used < 3:
        lines.append(
            f"> ⚠️ 当前 archive 仅 {days_used} 天数据，周报偏稀。"
            f" 持续每日跑 run-pipeline.py，下周开始数据更完整。"
        )
        lines.append("")

    has_anything = False
    for topic_id in sorted(topics.keys()):
        topic_articles = topics[topic_id]["articles"]
        anns = [a for a in topic_articles if a.get("_classification") == "announcement"]
        if not anns:
            continue
        has_anything = True

        # Sort by tier (tier1 first) then by quality_score
        tier_rank = {"tier1": 0, "tier2": 1, "tier3": 2, "tierX": 9}
        anns.sort(key=lambda x: (tier_rank.get(x.get("_tier", "tier3"), 5), -(x.get("quality_score", 0) or 0)))

        lines.append(f"## {topic_id}")
        lines.append("")
        for ann in anns:
            if ann.get("_tier") == "tierX":
                continue
            title = ann.get("title", "").strip()
            link = ann.get("link") or ann.get("external_url") or ann.get("reddit_url") or ""
            source = ann.get("source_name", "")
            date_str = (ann.get("date") or "")[:10]
            score = ann.get("quality_score", 0)
            tier = ann.get("_tier", "tier3")
            tier_label = {"tier1": "🔥 TIER 1", "tier2": "📌 Tier 2", "tier3": "Tier 3"}.get(tier, tier)
            lines.append(f"### [{tier_label}] [{title}]({link})")
            lines.append(f"- 来源: **{source}**  |  日期: {date_str}  |  质量分: {score}")
            if ann.get("all_sources"):
                lines.append(f"- 多源覆盖: {', '.join(ann['all_sources'])}")
            snippet = (ann.get("snippet") or ann.get("summary") or "").strip()
            if snippet:
                lines.append(f"- 摘要: {snippet[:200]}")

            reactions = ann.get("reactions") or []
            if reactions:
                lines.append(f"")
                lines.append(f"**社区反馈** ({len(reactions)})：")
                for r in reactions:
                    r_title = r.get("title", "").strip()
                    r_link = r.get("link") or r.get("reddit_url") or r.get("external_url") or ""
                    r_source = r.get("source_name", "")
                    metrics = r.get("metrics") or {}
                    engagement_parts = []
                    if r.get("score"):
                        engagement_parts.append(f"👍 {r['score']}")
                    if r.get("num_comments"):
                        engagement_parts.append(f"💬 {r['num_comments']}")
                    if metrics.get("like_count"):
                        engagement_parts.append(f"❤ {metrics['like_count']}")
                    engagement = "  ".join(engagement_parts)
                    lines.append(f"- [{r_source}] [{r_title}]({r_link})  {engagement}".rstrip())

            enriched = ann.get("enriched_comments") or []
            if enriched:
                lines.append("")
                lines.append(f"**社区评论原文** (Tier 1 二次抓取，{len(enriched)} 条)：")
                for c in enriched:
                    platform = c.get("platform", "")
                    author = c.get("author", "")
                    likes = c.get("likes", 0)
                    content = c.get("content", "")
                    likes_str = f" 👍 {likes}" if likes else ""
                    lines.append(f"  - **[{platform}] {author}**{likes_str}: {content}")

            if not reactions and not enriched:
                lines.append(f"")
                lines.append(f"_（本周暂无对应社区反馈）_")
            lines.append("")

    if not has_anything:
        lines.append("_本周未识别出 AI 新技术发布类条目，可能 archive 还在累积中。_")
        lines.append("")

    # ── 中文舆论侧（TrendRadar 等未配对到 announcement 的中文 reactions）──
    # 按 platform 二次分桶：标题前缀 `[今日头条]` / `[微博]` / `[知乎]` 等就是平台名
    cn_pat = re.compile(r"trendradar", re.IGNORECASE)
    platform_prefix_pat = re.compile(r"^\[([^\]]+)\]\s*")
    paired_links = set()
    for topic_id, topic_data in topics.items():
        for art in topic_data.get("articles", []):
            for r in (art.get("reactions") or []):
                paired_links.add(r.get("link") or r.get("external_url") or "")

    cn_unpaired_by_platform: Dict[str, List[Dict[str, Any]]] = {}
    for topic_id in sorted(topics.keys()):
        for art in topics[topic_id].get("articles", []):
            if art.get("_classification") != "reaction":
                continue
            sid = art.get("source_id", "") or ""
            if not cn_pat.search(sid):
                continue
            link = art.get("link") or art.get("external_url") or ""
            if link in paired_links:
                continue
            title = (art.get("title") or "").strip()
            m = platform_prefix_pat.match(title)
            platform = m.group(1).strip() if m else "其他"
            cn_unpaired_by_platform.setdefault(platform, []).append(art)

    if cn_unpaired_by_platform:
        lines.append("---")
        lines.append("")
        total_cn = sum(len(v) for v in cn_unpaired_by_platform.values())
        lines.append(f"## 🇨🇳 中文舆论侧（TrendRadar 中文热榜，未配对到具体发布，共 {total_cn} 条）")
        lines.append("")
        # 按平台条数从多到少排
        for platform in sorted(cn_unpaired_by_platform.keys(),
                               key=lambda p: (-len(cn_unpaired_by_platform[p]), p)):
            items = cn_unpaired_by_platform[platform]
            lines.append(f"### {platform} ({len(items)})")
            lines.append("")
            for r in items[:15]:
                # 标题已经带 [平台] 前缀，渲染时去掉避免重复
                r_title = platform_prefix_pat.sub("", (r.get("title") or "").strip())
                r_link = r.get("link") or r.get("external_url") or ""
                date_str = (r.get("date") or "")[:10]
                lines.append(f"- [{r_title}]({r_link})  _{date_str}_")
            if len(items) > 15:
                lines.append(f"- … 还有 {len(items)-15} 条")
            lines.append("")

    # ── 英文舆论侧（未配对的 HN / Reddit / Twitter / Web 反应）──
    # 按平台（source_type）分桶，便于扫描
    en_unpaired_by_platform: Dict[str, List[Dict[str, Any]]] = {}
    for topic_id in sorted(topics.keys()):
        for art in topics[topic_id].get("articles", []):
            if art.get("_classification") != "reaction":
                continue
            sid = art.get("source_id", "") or ""
            if cn_pat.search(sid):
                continue  # 已在中文段渲染
            link = art.get("link") or art.get("external_url") or ""
            if link in paired_links:
                continue
            # 平台名优先取 source_type，否则从 source_id 推断
            stype = (art.get("source_type") or "").lower()
            if stype == "reddit":
                bucket = "Reddit"
            elif stype == "twitter":
                bucket = "Twitter"
            elif stype == "web":
                bucket = "Web 搜索"
            elif "hn" in sid.lower() or "hacker" in sid.lower():
                bucket = "Hacker News"
            elif "lobsters" in sid.lower():
                bucket = "Lobsters"
            else:
                bucket = "其他"
            en_unpaired_by_platform.setdefault(bucket, []).append(art)

    if en_unpaired_by_platform:
        lines.append("---")
        lines.append("")
        total_en = sum(len(v) for v in en_unpaired_by_platform.values())
        lines.append(f"## 🌐 其他社区舆论（HN / Reddit / Twitter / Web，未配对，共 {total_en} 条）")
        lines.append("")
        for bucket in sorted(en_unpaired_by_platform.keys(),
                             key=lambda p: (-len(en_unpaired_by_platform[p]), p)):
            items = en_unpaired_by_platform[bucket]
            # 按 metrics 排序（score / num_comments / engagement）
            def _score(a: Dict[str, Any]) -> int:
                m = a.get("metrics") or {}
                return int(m.get("score") or m.get("favorites") or m.get("num_comments") or 0)
            items.sort(key=_score, reverse=True)
            lines.append(f"### {bucket} ({len(items)})")
            lines.append("")
            for r in items[:15]:
                r_title = (r.get("title") or "").strip()
                r_link = r.get("link") or r.get("external_url") or ""
                r_source = r.get("source_name", "")
                date_str = (r.get("date") or "")[:10]
                m = r.get("metrics") or {}
                sc = m.get("score") or m.get("favorites") or m.get("num_comments") or 0
                badge = f" · ⭐{sc}" if sc else ""
                lines.append(f"- [{r_source}] [{r_title}]({r_link})  _{date_str}_{badge}")
            if len(items) > 15:
                lines.append(f"- … 还有 {len(items)-15} 条")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly AI tech announcement + community feedback digest from follow-news archive")
    parser.add_argument("--archive-dir", type=Path, required=False, help="Workspace archive dir (parent of daily-json/) — used when --fetch-now is NOT set")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--output", type=Path, default=Path("/tmp/td-weekly-merged.json"), help="Output JSON path (same schema as merge-sources)")
    parser.add_argument("--markdown", type=Path, default=None, help="Optional markdown digest output path")
    parser.add_argument("--max-reactions", type=int, default=5, help="Max reactions per announcement (default: 5)")
    parser.add_argument(
        "--enrich-tier1",
        action="store_true",
        help="For Tier 1 announcements, fetch top community comments from HN/Reddit via zero-auth JSON APIs and attach as enriched_comments[]",
    )
    parser.add_argument(
        "--fetch-now",
        action="store_true",
        help="Trigger fresh on-demand 7-day fetch (RSS/GitHub/Web/Twitter via run-pipeline.py --hours 168, "
             "TrendRadar via weekly_export.py). Skips archive-dir/daily-json. Recommended for ad-hoc weekly reports.",
    )
    parser.add_argument(
        "--trendradar-dir",
        type=Path,
        default=None,
        help="TrendRadar repo path (for --fetch-now to invoke weekly_export.py). Default: auto-detect ../TrendRadar relative to follow-news",
    )
    parser.add_argument(
        "--llm-filter",
        action="store_true",
        help="[Opt-in legacy] Run llm-filter.py for semantic dedup + announcement verification. "
             "Requires LLM_FILTER_API_KEY env var. Default flow does NOT use this — LLM work "
             "is delegated to OpenClaw agent at report-writing time (no separate API key needed).",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    merge_mod = _load_merge_module()

    # ── Source data path: either --fetch-now (fresh) or --archive-dir (accumulated) ──
    daily_files: List[Path] = []
    if args.fetch_now:
        articles = fetch_now(args, logger, merge_mod)
        if not articles:
            logger.error("Fresh fetch returned no articles")
            return 1
    else:
        if not args.archive_dir:
            logger.error("Either --fetch-now or --archive-dir must be provided")
            return 1
        daily_files = collect_daily_files(args.archive_dir, args.days)
        if not daily_files:
            logger.error(
                f"No daily archives found under {args.archive_dir}/daily-json/. "
                "Either pass --fetch-now (recommended) or run run-pipeline.py first to seed the archive."
            )
            return 1
        logger.info(f"Found {len(daily_files)} daily archives: {[p.name for p in daily_files]}")
        articles = flatten_daily_json(daily_files, logger)
        if not articles:
            logger.error("No articles found in archived files")
            return 1

    # Cross-day dedup + multi-source detection (reuse follow-news's own logic)
    deduped = merge_mod.deduplicate_articles(articles)
    merged = merge_mod.merge_article_sources(deduped)
    logger.info(f"After dedup+merge: {len(merged)} articles")

    # Classify
    announcements: List[Dict[str, Any]] = []
    reactions: List[Dict[str, Any]] = []
    for a in merged:
        cls = classify_article(a)
        a["_classification"] = cls
        if cls == "announcement":
            announcements.append(a)
        elif cls == "reaction":
            reactions.append(a)
    # Collapse same-project sibling releases BEFORE tier assignment so a single
    # project can't claim multiple Tier 1 slots with consecutive version bumps.
    announcements = dedup_same_project(announcements, logger)
    # Now assign tiers on the deduped set
    for a in announcements:
        a["_tier"] = assign_tier(a)
    tier_counts: Dict[str, int] = {}
    for ann in announcements:
        tier_counts[ann["_tier"]] = tier_counts.get(ann["_tier"], 0) + 1
    logger.info(
        f"Classified: {len(announcements)} announcements ({tier_counts}), {len(reactions)} reactions"
    )

    # Pair reactions under announcements
    pair_reactions(announcements, reactions, merge_mod.normalize_title, logger, args.max_reactions)

    # Optionally enrich Tier 1 with real HN/Reddit comment text
    if args.enrich_tier1:
        from importlib.machinery import SourceFileLoader
        enricher = SourceFileLoader("enrich_comments", str(SCRIPTS_DIR / "enrich_comments.py")).load_module()
        tier1_anns = [a for a in announcements if a.get("_tier") == "tier1"]
        logger.info(f"Enriching {len(tier1_anns)} Tier 1 announcements with HN/Reddit comments…")
        enriched_count = 0
        # Shared set tracks HN story IDs claimed by the title-search fallback so
        # different titles can't all collapse onto the same fuzzy-matched thread.
        used_story_ids: set = set()
        for ann in tier1_anns:
            got = enricher.enrich_article_with_comments(
                ann, max_per_source=5, used_story_ids=used_story_ids
            )
            if got:
                enriched_count += 1
                logger.debug(
                    f"  ✚ {len(got)} comments → '{ann.get('title','')[:60]}'"
                )
        logger.info(f"Enrichment: attached comments to {enriched_count}/{len(tier1_anns)} Tier 1 articles")

    # Regroup into topics (same schema as merge-sources output)
    topics_grouped = regroup_by_topic(merged)

    # Build output JSON
    output_data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "weekly_window_days": args.days,
        "weekly_days_used": len(daily_files),
        "input_archive_files": [p.name for p in daily_files],
        "output_stats": {
            "total_articles": len(merged),
            "announcements_count": len(announcements),
            "reactions_count": len(reactions),
            "tier_distribution": tier_counts,
            "tier1_with_enriched_comments": sum(
                1 for a in announcements if a.get("_tier") == "tier1" and a.get("enriched_comments")
            ),
            "topics_count": len(topics_grouped),
            "topic_distribution": {tid: data["count"] for tid, data in topics_grouped.items()},
        },
        "topics": topics_grouped,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"📄 Weekly JSON → {args.output}")

    # Optionally render markdown
    if args.markdown:
        md = render_markdown(merged, topics_grouped, len(daily_files), args.days, fetch_now=args.fetch_now)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md, encoding="utf-8")
        logger.info(f"📝 Weekly markdown → {args.markdown}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
