#!/usr/bin/env python3
"""
Official competitor-update direct crawler for the domestic-agent monitor.

Why this exists:
    The weekly "国产 Agent 竞品动态" section needs each tracked product's official
    updates (releases / changelog entries / new docs / app-store notes / RSS) as a
    deterministic, KOL-independent foundation. This addon reads a per-product profile
    config and pulls whatever official sources are configured, normalizing everything
    to CompetitorUpdate records. No LLM — direction/scene synthesis is left to the agent.

Add-only addon (does not modify upstream). Invoked by weekly-feedback.py after
run-pipeline, same orchestration slot as fetch-hn.py. Run via shell with PYTHONUTF8=1.

Usage:
    python fetch-competitor-official.py --profiles competitor-profiles.json \
        [--window-days 7] [--out /tmp/competitor-official.json] [--only-product NAME] [--verbose]

Environment:
    GITHUB_TOKEN (optional): used for github_repo sources, reused from existing env.
    Missing token → github path skips. All other sources are anonymous.

Contract: specs/006-domestic-agent-monitor/contracts/official-fetcher-cli.md
"""

import argparse
import html
import json
import logging
import os
import re
import ssl
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

_SSL_CTX = ssl.create_default_context()
# Browser-ish UA: several CN sites gate on default urllib UA (Principle V / R7).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 ai-pulse-competitor/1.0"
)
TIMEOUT = 20

VALID_CATEGORIES = {"coding", "general_agent", "office", "rpa"}
_TAG_RE = re.compile(r"<[^>]+>")


# ─── HTTP helpers (T004) ──────────────────────────────────────────────────────

def _request(url: str, accept: str, extra_headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            return resp.read()
    except (HTTPError, URLError, TimeoutError, ssl.SSLError) as e:
        logging.debug(f"HTTP fetch failed for {url}: {e}")
        return None


def http_get_json(url: str, token: Optional[str] = None) -> Optional[Any]:
    extra = {"Authorization": f"Bearer {token}"} if token else None
    raw = _request(url, "application/json", extra)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, json.JSONDecodeError) as e:
        logging.debug(f"JSON decode failed for {url}: {e}")
        return None


def http_get_text(url: str) -> Optional[str]:
    raw = _request(url, "text/html,application/xhtml+xml,application/xml")
    if raw is None:
        return None
    return raw.decode("utf-8", "replace")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = text.replace("<br>", "\n").replace("</p>", "\n")
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _truncate(text: str, limit: int = 280) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


# ─── Date / window utils (T005) ───────────────────────────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y年%m月%d日",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
]


def parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Best-effort multi-format date parse → aware UTC datetime, or None.

    Parsing failure returns None (caller keeps the record but with empty date, R1).
    """
    if not raw:
        return None
    s = raw.strip()
    # Normalize trailing Z for fromisoformat-style strings already covered above.
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    # Last resort: pull a YYYY-MM-DD substring.
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def within_window(dt: Optional[datetime], window_days: int, now: Optional[datetime] = None) -> bool:
    """True if dt falls within the last window_days. Unknown date (None) → kept (True)."""
    if dt is None:
        return True  # keep undated items; agent/coverage will note the ambiguity
    now = now or datetime.now(timezone.utc)
    return dt >= now - timedelta(days=max(1, window_days))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ─── Profile loading + validation (T003) ──────────────────────────────────────

def load_profiles(path: str) -> List[Dict[str, Any]]:
    """Load + validate competitor profiles. Invalid items skipped+logged; a
    broken file yields [] (caller still exits 0). See contracts/competitor-profile.md."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logging.error(f"profiles file unreadable, competitor section degrades to empty: {e}")
        return []

    raw_profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(raw_profiles, list):
        logging.error("profiles file missing 'profiles' array; degrade to empty")
        return []

    valid: List[Dict[str, Any]] = []
    for i, p in enumerate(raw_profiles):
        if not isinstance(p, dict):
            logging.warning(f"profile[{i}] not an object, skipped")
            continue
        name = p.get("name")
        aliases = p.get("aliases")
        category = p.get("category")
        if not isinstance(name, str) or not name.strip():
            logging.warning(f"profile[{i}] missing name, skipped")
            continue
        if not isinstance(aliases, list) or not aliases:
            logging.warning(f"profile '{name}' missing aliases array, skipped")
            continue
        if category not in VALID_CATEGORIES:
            logging.warning(f"profile '{name}' invalid category '{category}', skipped")
            continue
        sources = p.get("official_sources")
        if not isinstance(sources, dict):
            sources = {}
        valid.append({
            "name": name.strip(),
            "aliases": [a for a in aliases if isinstance(a, str) and a.strip()],
            "category": category,
            "enabled": bool(p.get("enabled", True)),
            "official_sources": sources,
        })
    logging.info(f"loaded {len(valid)} valid profiles from {path}")
    return valid


# ─── Source fetchers (T009–T013) ──────────────────────────────────────────────

def _mk_update(product, type_, title, url, dt, summary, source_kind) -> Dict[str, Any]:
    return {
        "product": product,
        "type": type_,
        "title": title or "(无标题)",
        "url": url or "",
        "date": _iso(dt),
        "summary": _truncate(summary or ""),
        "source_kind": source_kind,
    }


def fetch_github(product: str, repo: str, window_days: int, token: Optional[str]) -> List[Dict[str, Any]]:
    """GitHub releases for an open-source product (R1). type=release."""
    if not repo:
        return []
    url = f"https://api.github.com/repos/{repo}/releases?per_page=20"
    payload = http_get_json(url, token=token)
    if not isinstance(payload, list):
        return []
    out: List[Dict[str, Any]] = []
    for rel in payload:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        dt = parse_date(rel.get("published_at") or rel.get("created_at"))
        if not within_window(dt, window_days):
            continue
        out.append(_mk_update(
            product, "release",
            rel.get("name") or rel.get("tag_name") or "release",
            rel.get("html_url"), dt, rel.get("body") or "", "github",
        ))
    return out


def fetch_changelog(product: str, url: str, css_selector: Optional[str], window_days: int) -> List[Dict[str, Any]]:
    """Official changelog HTML scrape via per-product CSS selector (R1, FR-002a).

    Selector grammar supported (deterministic, no heavy dep): tag, .class, #id,
    and 'tag.class'. No match / unreachable → [] (degrade, caller annotates)."""
    if not url or not css_selector:
        return []
    htmltext = http_get_text(url)
    if not htmltext:
        return []
    blocks = _select_blocks(htmltext, css_selector)
    out: List[Dict[str, Any]] = []
    for block in blocks[:50]:
        title = _strip_html(block)
        if not title:
            continue
        href = _first_href(block)
        dt = parse_date(_first_date_str(block))
        if not within_window(dt, window_days):
            continue
        out.append(_mk_update(
            product, "feature", _truncate(title, 160),
            href or url, dt, title, "changelog",
        ))
    return out


def _select_blocks(htmltext: str, selector: str) -> List[str]:
    """Return raw HTML fragments matching a simple CSS selector.

    Supports: '.class', '#id', 'tag', 'tag.class'. We locate each matching
    *opening* tag and slice to its next same-tag close — dependency-free and
    robust against an outer container (html/body) swallowing inner items.
    Unknown selector → []."""
    sel = selector.strip()
    tag = None
    attr_pat = None
    m = re.match(r"^([a-zA-Z0-9]+)?(?:\.([\w\-]+))?$", sel)
    if m and (m.group(1) or m.group(2)):
        tag = m.group(1)
        cls = m.group(2)
        if cls:
            attr_pat = re.compile(r'class\s*=\s*["\'][^"\']*\b' + re.escape(cls) + r'\b', re.I)
    elif sel.startswith("#"):
        ident = sel[1:]
        attr_pat = re.compile(r'id\s*=\s*["\']' + re.escape(ident) + r'["\']', re.I)
    else:
        return []

    tagpat = tag or r"[a-zA-Z0-9]+"
    open_re = re.compile(r"<(" + tagpat + r")\b([^>]*)>", re.I)
    results: List[str] = []
    for mt in open_re.finditer(htmltext):
        opentag = mt.group(0)
        if attr_pat and not attr_pat.search(opentag):
            continue
        close_re = re.compile(r"</" + re.escape(mt.group(1)) + r"\s*>", re.I)
        close = close_re.search(htmltext, mt.end())
        block = htmltext[mt.end():close.start()] if close else htmltext[mt.end():]
        results.append(block)
    return results


def _first_href(fragment: str) -> Optional[str]:
    m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', fragment, re.I)
    return m.group(1) if m else None


def _first_date_str(fragment: str) -> Optional[str]:
    m = re.search(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}", fragment)
    return m.group(0) if m else None


def fetch_sitemap(product: str, url: str, window_days: int) -> List[Dict[str, Any]]:
    """Docs-site sitemap.xml recently-modified pages = new-feature signal (R1). type=direction."""
    if not url:
        return []
    xmltext = http_get_text(url)
    if not xmltext:
        return []
    try:
        root = ET.fromstring(xmltext)
    except ET.ParseError as e:
        logging.debug(f"sitemap parse failed for {url}: {e}")
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out: List[Dict[str, Any]] = []
    urls = root.findall(".//sm:url", ns) or root.findall(".//url")
    for u in urls:
        loc_el = u.find("sm:loc", ns)
        if loc_el is None:
            loc_el = u.find("loc")
        lastmod_el = u.find("sm:lastmod", ns)
        if lastmod_el is None:
            lastmod_el = u.find("lastmod")
        loc = loc_el.text.strip() if loc_el is not None and loc_el.text else None
        if not loc:
            continue
        dt = parse_date(lastmod_el.text if lastmod_el is not None else None)
        if not within_window(dt, window_days) or dt is None:
            continue  # sitemap entries without dates are noise here
        title = loc.rstrip("/").rsplit("/", 1)[-1] or loc
        out.append(_mk_update(product, "direction", title, loc, dt, loc, "sitemap"))
    return out


def fetch_appstore(product: str, app_id: str, window_days: int) -> List[Dict[str, Any]]:
    """Apple App Store release notes via anonymous iTunes lookup (R1). type=release."""
    if not app_id:
        return []
    url = f"https://itunes.apple.com/lookup?id={quote(str(app_id))}&country=cn&entity=software"
    payload = http_get_json(url)
    if not isinstance(payload, dict):
        return []
    results = payload.get("results") or []
    out: List[Dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        dt = parse_date(r.get("currentVersionReleaseDate"))
        if not within_window(dt, window_days):
            continue
        ver = r.get("version") or ""
        out.append(_mk_update(
            product, "release",
            f"{r.get('trackName', product)} {ver}".strip(),
            r.get("trackViewUrl"), dt, r.get("releaseNotes") or "", "appstore",
        ))
    return out


def fetch_rss(product: str, url: str, window_days: int) -> List[Dict[str, Any]]:
    """RSS/Atom feed items in window (R1). type=feature."""
    if not url:
        return []
    xmltext = http_get_text(url)
    if not xmltext:
        return []
    try:
        root = ET.fromstring(xmltext)
    except ET.ParseError as e:
        logging.debug(f"rss parse failed for {url}: {e}")
        return []
    out: List[Dict[str, Any]] = []
    # RSS <item> and Atom <entry>
    items = root.findall(".//item")
    if items:
        for it in items:
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            dt = parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))
            desc = it.findtext("description") or ""
            if not within_window(dt, window_days):
                continue
            out.append(_mk_update(product, "feature", title, link, dt, _strip_html(desc), "rss"))
        return out
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for it in root.findall(f".//{atom_ns}entry"):
        title = (it.findtext(f"{atom_ns}title") or "").strip()
        link_el = it.find(f"{atom_ns}link")
        link = link_el.get("href") if link_el is not None else ""
        dt = parse_date(it.findtext(f"{atom_ns}updated") or it.findtext(f"{atom_ns}published"))
        summary = it.findtext(f"{atom_ns}summary") or it.findtext(f"{atom_ns}content") or ""
        if not within_window(dt, window_days):
            continue
        out.append(_mk_update(product, "feature", title, link, dt, _strip_html(summary), "rss"))
    return out


# ─── Orchestration / CLI (T014) ───────────────────────────────────────────────

_SOURCE_LABELS = ["github", "changelog", "sitemap", "appstore", "rss"]


def crawl_product(profile: Dict[str, Any], window_days: int, token: Optional[str]) -> tuple:
    """Run every configured source for one product, each isolated. Returns
    (updates, coverage_row). Any source error degrades to skip + annotation (VI)."""
    name = profile["name"]
    src = profile.get("official_sources") or {}
    updates: List[Dict[str, Any]] = []
    coverage: Dict[str, str] = {"product": name}

    def run(label, fn, *args):
        if not args[0]:  # the source's config value is empty
            coverage[label] = "skip(unconfigured)"
            return
        try:
            got = fn(name, *args)
            coverage[label] = f"ok({len(got)})" if got else "ok(0)"
            updates.extend(got)
        except Exception as e:  # noqa: BLE001 — any source failure must be soft (VI)
            logging.warning(f"[{name}] {label} failed: {e}")
            coverage[label] = f"error({type(e).__name__})"

    run("github", fetch_github, src.get("github_repo"), window_days, token)
    # changelog needs both url+selector; pass url as the "configured?" gate
    if src.get("changelog_url"):
        try:
            got = fetch_changelog(name, src.get("changelog_url"), src.get("css_selector"), window_days)
            coverage["changelog"] = f"ok({len(got)})" if got else (
                "degrade(no-selector)" if not src.get("css_selector") else "ok(0)")
            updates.extend(got)
        except Exception as e:  # noqa: BLE001
            logging.warning(f"[{name}] changelog failed: {e}")
            coverage["changelog"] = f"error({type(e).__name__})"
    else:
        coverage["changelog"] = "skip(unconfigured)"
    run("sitemap", fetch_sitemap, src.get("docs_sitemap_url"), window_days)
    run("appstore", fetch_appstore, src.get("app_store_id"), window_days)
    run("rss", fetch_rss, src.get("rss_url"), window_days)

    if not updates and all(
        coverage.get(k, "").startswith("skip") for k in _SOURCE_LABELS
    ):
        coverage["note"] = "无配置官方源"
    elif not updates:
        coverage["note"] = "本周无更新"
    return updates, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl competitor official updates")
    parser.add_argument("--profiles", required=True, help="competitor-profiles.json path")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--out", "-o", default=None, help="output JSON path (default /tmp/competitor-official.json)")
    parser.add_argument("--only-product", default=None, help="restrict to one product name (for on-demand brief)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not Path(args.profiles).exists():
        logging.error(f"--profiles path does not exist: {args.profiles}")
        return 2  # parameter error is the only non-zero exit (contract)

    profiles = load_profiles(args.profiles)
    token = os.environ.get("GITHUB_TOKEN")

    if args.only_product:
        profiles = [p for p in profiles if p["name"] == args.only_product
                    or args.only_product in p.get("aliases", [])]

    all_updates: List[Dict[str, Any]] = []
    coverage_rows: List[Dict[str, str]] = []
    for p in profiles:
        if not p.get("enabled", True):
            continue
        ups, cov = crawl_product(p, args.window_days, token)
        all_updates.extend(ups)
        coverage_rows.append(cov)
        logging.info(f"  {p['name']}: {len(ups)} updates")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": args.window_days,
        "updates": all_updates,
        "coverage": coverage_rows,
    }
    out_path = args.out or str(Path(tempfile.gettempdir()) / "competitor-official.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logging.info(f"Wrote {len(all_updates)} updates across {len(coverage_rows)} products → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
