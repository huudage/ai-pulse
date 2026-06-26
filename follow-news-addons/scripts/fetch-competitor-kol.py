#!/usr/bin/env python3
"""
Multi-platform KOL content search for the domestic-agent monitor (006 US2).

Why this exists:
    The weekly "国产 Agent 竞品动态" section and the on-demand competitor brief both
    need KOL (视频/文章) coverage showing *which industries/roles* are applying each
    tracked product. This addon searches several Chinese content platforms by product
    name + aliases, normalizes hits to KOLContent records, and tags each with the
    deterministic industry×role dictionary (competitor_tagging). No LLM here — scene
    synthesis is left to the agent.

Platforms & credentials (per-platform soft-fail, Principle VI):
    bilibili  无需凭证。WBI 签名匿名搜索。可选 BILIBILI_COOKIE 提升限额。
    zhihu     需 ZHIHU_COOKIE（浏览器整段 cookie，至少含 d_c0/z_c0）。缺失→跳过。
    jike      需 JIKE_ACCESS_TOKEN（即刻 x-jike-access-token）。缺失→跳过。
    weixin    需 WEIXIN_SEARCH_URL（第三方公众号搜索 JSON 接口，{kw} 占位）
              + 可选 WEIXIN_API_KEY。无公开官方接口，故走用户自备端点。缺失→跳过。

Add-only addon (does not modify upstream). Invoked by weekly-feedback.py and
competitor-brief.py. Run via shell with PYTHONUTF8=1.

Usage:
    python fetch-competitor-kol.py --profiles competitor-profiles.json \
        [--window-days 7] [--out /tmp/competitor-kol.json] [--only-product NAME] \
        [--platforms bilibili,zhihu,jike,weixin] [--max-per-product 10] [--verbose]

Contract: specs/006-domestic-agent-monitor/contracts/ (KOLContent in data-model.md)
"""

import argparse
import hashlib
import html
import json
import logging
import os
import random
import re
import ssl
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from http.cookiejar import CookieJar, Cookie
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPCookieProcessor

# Reuse profile loading + tagging from sibling addons (importlib for hyphenated module).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import competitor_tagging as tagging  # noqa: E402

_SSL_CTX = ssl.create_default_context()
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 ai-pulse-competitor/1.0"
)
TIMEOUT = 20
ALL_PLATFORMS = ["bilibili", "zhihu", "jike", "weixin"]
_TAG_RE = re.compile(r"<[^>]+>")


# ─── shared HTTP / text helpers ───────────────────────────────────────────────

def _strip(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _truncate(text: str, limit: int = 280) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _opener(cookie: Optional[str] = None, referer: Optional[str] = None):
    op = build_opener(HTTPCookieProcessor(CookieJar()))
    headers = [("User-Agent", USER_AGENT)]
    if referer:
        headers.append(("Referer", referer))
    if cookie:
        headers.append(("Cookie", cookie))
    op.addheaders = headers
    return op


def _get(op, url: str, extra_headers: Optional[Dict[str, str]] = None,
         data: Optional[bytes] = None) -> Optional[bytes]:
    req = Request(url, data=data)
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    try:
        with op.open(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except (HTTPError, URLError, TimeoutError, ssl.SSLError) as e:
        logging.debug(f"HTTP failed {url}: {e}")
        return None


def _get_json(op, url, extra_headers=None, data=None) -> Optional[Any]:
    raw = _get(op, url, extra_headers, data)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, json.JSONDecodeError) as e:
        logging.debug(f"JSON decode failed {url}: {e}")
        return None


def _within(epoch: Optional[float], window_days: int) -> bool:
    if not epoch:
        return True  # undated → keep, agent notes ambiguity
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, window_days))
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc) >= cutoff
    except (ValueError, OSError, OverflowError):
        return True


def _iso(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _mk_kol(title, url, author, date_iso, platform, summary) -> Dict[str, Any]:
    return {
        "title": _strip(title) or "(无标题)",
        "url": url or "",
        "author": author or "",
        "date": date_iso,
        "platform": platform,
        "summary": _truncate(_strip(summary or "")),
    }


# ─── Bilibili (WBI-signed search, no credentials required) ─────────────────────

# Fixed mixin-key permutation table (public, stable). Used to derive the WBI salt.
_WBI_MIXIN = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
    20, 34, 44, 52,
]


def _bili_mixin_key(img_sub: str) -> str:
    return "".join(img_sub[i] for i in _WBI_MIXIN)[:32]


def _bili_get_wbi_key(op) -> Optional[str]:
    nav = _get_json(op, "https://api.bilibili.com/x/web-interface/nav")
    if not isinstance(nav, dict):
        return None
    wbi = (nav.get("data") or {}).get("wbi_img") or {}
    img, sub = wbi.get("img_url", ""), wbi.get("sub_url", "")
    if not img or not sub:
        return None
    img_k = img.rsplit("/", 1)[-1].split(".")[0]
    sub_k = sub.rsplit("/", 1)[-1].split(".")[0]
    return _bili_mixin_key(img_k + sub_k)


def _bili_sign(params: Dict[str, Any], mixin_key: str) -> str:
    params = dict(params)
    params["wts"] = int(time.time())
    ordered = {k: params[k] for k in sorted(params)}
    query = urlencode(ordered)
    ordered["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return urlencode(ordered)


def _bili_set_cookie(jar: CookieJar, name: str, value: str) -> None:
    jar.set_cookie(Cookie(
        0, name, value, None, False, ".bilibili.com", True, False,
        "/", True, False, None, True, None, None, {}))


def _bili_seed(jar: CookieJar, op) -> None:
    """Seed a browser-like fingerprint so anonymous search clears the risk gate:
    homepage (buvid3/b_nut) → spi endpoint (buvid3/buvid4) → synthetic _uuid/b_lsid.
    Bilibili returns data.v_voucher (a risk challenge) instead of results when the
    fingerprint is too thin; this raises the success rate without a logged-in cookie."""
    _get(op, "https://www.bilibili.com")
    spi = _get_json(op, "https://api.bilibili.com/x/frontend/finger/spi")
    data = spi.get("data") if isinstance(spi, dict) else None
    if isinstance(data, dict):
        if data.get("b_3"):
            _bili_set_cookie(jar, "buvid3", data["b_3"])
        if data.get("b_4"):
            _bili_set_cookie(jar, "buvid4", data["b_4"])
    rnd = lambda n: "".join(random.choice("0123456789ABCDEF") for _ in range(n))
    ms = int(time.time() * 1000)
    _bili_set_cookie(jar, "_uuid",
                     f"{rnd(8)}-{rnd(4)}-{rnd(4)}-{rnd(4)}-{rnd(12)}{str(ms)[-5:]}infoc")
    _bili_set_cookie(jar, "b_lsid", f"{rnd(8)}_{format(ms, 'X')}")


def fetch_bilibili(query: str, window_days: int, limit: int) -> List[Dict[str, Any]]:
    """WBI-signed video search. Anonymous by default (fingerprint seeded via spi);
    set BILIBILI_COOKIE (logged-in SESSDATA) to reliably clear Bilibili's risk gate."""
    cookie = os.environ.get("BILIBILI_COOKIE")
    jar = CookieJar()
    op = build_opener(HTTPCookieProcessor(jar))
    headers = [("User-Agent", USER_AGENT), ("Referer", "https://www.bilibili.com/")]
    if cookie:
        headers.append(("Cookie", cookie))
    op.addheaders = headers
    if not cookie:
        _bili_seed(jar, op)
    mixin = _bili_get_wbi_key(op)
    if not mixin:
        return []
    qs = _bili_sign({"search_type": "video", "keyword": query, "page": 1}, mixin)
    payload = _get_json(op, "https://api.bilibili.com/x/web-interface/wbi/search/type?" + qs)
    if not isinstance(payload, dict) or payload.get("code") != 0:
        return []
    data = payload.get("data") or {}
    # Risk-control gate: code 0 + v_voucher but no result → needs a logged-in cookie.
    if "v_voucher" in data and not data.get("result"):
        if not cookie:
            raise _SkipUnconfigured("bilibili 风控拦截，需设置 BILIBILI_COOKIE（登录态 SESSDATA）")
        return []
    results = data.get("result") or []
    out: List[Dict[str, Any]] = []
    for it in results[:limit]:
        if not isinstance(it, dict):
            continue
        pub = it.get("pubdate") or it.get("senddate")
        if not _within(pub, window_days):
            continue
        bvid = it.get("bvid") or ""
        url = f"https://www.bilibili.com/video/{bvid}" if bvid else (it.get("arcurl") or "")
        out.append(_mk_kol(
            it.get("title", ""), url, it.get("author", ""),
            _iso(pub), "bilibili", it.get("description", ""),
        ))
    return out


# ─── 知乎 (cookie-driven, best-effort) ─────────────────────────────────────────

def fetch_zhihu(query: str, window_days: int, limit: int) -> List[Dict[str, Any]]:
    cookie = os.environ.get("ZHIHU_COOKIE")
    if not cookie:
        raise _SkipUnconfigured("ZHIHU_COOKIE 未设置")
    op = _opener(cookie=cookie, referer="https://www.zhihu.com/")
    url = ("https://www.zhihu.com/api/v4/search_v3?t=general&q=" + quote(query)
           + "&correction=1&offset=0&limit=" + str(min(limit, 20)))
    payload = _get_json(op, url, extra_headers={"x-requested-with": "fetch"})
    if not isinstance(payload, dict):
        return []
    out: List[Dict[str, Any]] = []
    for row in (payload.get("data") or [])[:limit]:
        obj = row.get("object") if isinstance(row, dict) else None
        if not isinstance(obj, dict):
            continue
        otype = obj.get("type", "")
        title = obj.get("title") or (obj.get("question") or {}).get("name") or ""
        excerpt = obj.get("excerpt") or obj.get("content") or ""
        author = ((obj.get("author") or {}).get("name")) or ""
        oid = obj.get("id") or ""
        if otype == "answer":
            url = f"https://www.zhihu.com/answer/{oid}"
        elif otype == "article":
            url = f"https://zhuanlan.zhihu.com/p/{oid}"
        elif otype == "zvideo":
            url = f"https://www.zhihu.com/zvideo/{oid}"
        else:
            url = obj.get("url") or ""
        ct = obj.get("created_time") or obj.get("updated_time")
        if not _within(ct, window_days):
            continue
        out.append(_mk_kol(title, url, author, _iso(ct), "zhihu", excerpt))
    return out


# ─── 即刻 Jike (token-driven, best-effort) ─────────────────────────────────────

def fetch_jike(query: str, window_days: int, limit: int) -> List[Dict[str, Any]]:
    token = os.environ.get("JIKE_ACCESS_TOKEN")
    if not token:
        raise _SkipUnconfigured("JIKE_ACCESS_TOKEN 未设置")
    op = _opener(referer="https://web.okjike.com/")
    body = json.dumps({"keywords": query, "loadMoreKey": None}).encode("utf-8")
    payload = _get_json(
        op, "https://api.ruguoapp.com/1.0/search/integrate",
        extra_headers={"x-jike-access-token": token, "Content-Type": "application/json",
                       "App-Version": "7.0.0", "platform": "web"},
        data=body,
    )
    if not isinstance(payload, dict):
        return []
    out: List[Dict[str, Any]] = []
    for row in (payload.get("data") or [])[:limit]:
        if not isinstance(row, dict):
            continue
        content = row.get("content") or row.get("text") or ""
        user = (row.get("user") or {}).get("screenName") or ""
        pid = row.get("id") or ""
        url = f"https://web.okjike.com/originalPost/{pid}" if pid else ""
        ts = row.get("createdAt") or ""
        # Jike createdAt is ISO; convert to epoch best-effort.
        epoch = None
        try:
            epoch = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            pass
        if not _within(epoch, window_days):
            continue
        out.append(_mk_kol(content[:60], url, user, _iso(epoch) or (ts or None), "jike", content))
    return out


# ─── 公众号 WeChat (user-supplied third-party endpoint, best-effort) ───────────

def fetch_weixin(query: str, window_days: int, limit: int) -> List[Dict[str, Any]]:
    """No official public API. Driven by a user-configured JSON endpoint:
        WEIXIN_SEARCH_URL  e.g. https://your-vendor/api/search?word={kw}&key=...
        WEIXIN_API_KEY     optional, sent as Authorization: Bearer <key>
    Expected JSON shape (lenient): {articles|data|list:[{title,url,author|nickname,
        digest|summary,date|pubtime}]}. Anything else → []."""
    endpoint = os.environ.get("WEIXIN_SEARCH_URL")
    if not endpoint:
        raise _SkipUnconfigured("WEIXIN_SEARCH_URL 未设置（公众号无官方接口，需自备）")
    url = endpoint.replace("{kw}", quote(query))
    headers = {}
    key = os.environ.get("WEIXIN_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    op = _opener()
    payload = _get_json(op, url, extra_headers=headers or None)
    if not isinstance(payload, dict):
        return []
    rows = payload.get("articles") or payload.get("data") or payload.get("list") or []
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        title = row.get("title") or ""
        link = row.get("url") or row.get("link") or ""
        author = row.get("author") or row.get("nickname") or row.get("account") or ""
        summary = row.get("digest") or row.get("summary") or row.get("desc") or ""
        # date may be epoch or ISO; pass through if can't parse epoch.
        raw_date = row.get("date") or row.get("pubtime") or row.get("publish_time")
        date_iso = None
        if isinstance(raw_date, (int, float)):
            date_iso = _iso(raw_date)
        elif isinstance(raw_date, str):
            date_iso = raw_date
        out.append(_mk_kol(title, link, author, date_iso, "weixin", summary))
    return out


class _SkipUnconfigured(Exception):
    """Raised by a platform fetcher when its credential is absent → coverage skip."""


_FETCHERS = {
    "bilibili": fetch_bilibili,
    "zhihu": fetch_zhihu,
    "jike": fetch_jike,
    "weixin": fetch_weixin,
}


# ─── Orchestration ─────────────────────────────────────────────────────────────

def search_product(profile: Dict[str, Any], platforms: List[str], window_days: int,
                   max_per_product: int, all_profiles: List[Dict[str, Any]]) -> tuple:
    """Search every enabled platform for one product's name+aliases, tag hits.
    Returns (kol_contents, coverage_row). Each platform isolated (Principle VI)."""
    name = profile["name"]
    queries = [name] + [a for a in profile.get("aliases", []) if a]
    coverage: Dict[str, str] = {"product": name}
    seen_urls = set()
    contents: List[Dict[str, Any]] = []

    for plat in platforms:
        fn = _FETCHERS.get(plat)
        if fn is None:
            coverage[plat] = "skip(unknown-platform)"
            continue
        got_plat: List[Dict[str, Any]] = []
        try:
            for q in queries:
                for item in fn(q, window_days, max_per_product):
                    u = item.get("url") or (item.get("title", "") + plat)
                    if u in seen_urls:
                        continue
                    seen_urls.add(u)
                    got_plat.append(item)
                if len(got_plat) >= max_per_product:
                    break
            coverage[plat] = f"ok({len(got_plat)})"
        except _SkipUnconfigured as e:
            coverage[plat] = f"skip({e})"
            continue
        except Exception as e:  # noqa: BLE001 — any platform failure must be soft (VI)
            logging.warning(f"[{name}] {plat} failed: {e}")
            coverage[plat] = f"error({type(e).__name__})"
            continue

        for item in got_plat[:max_per_product]:
            tagged = tagging.tag_kol_content(item, all_profiles)
            item["matched_products"] = tagged.get("matched_products", [])
            item["industry_tags"] = tagged.get("industry_tags", [])
            item["role_scene_tags"] = tagged.get("role_scene_tags", [])
            item["agent_extra_tags"] = tagged.get("agent_extra_tags", [])
            # Ensure the searched product is associated even if title lacks the alias.
            if name not in item["matched_products"]:
                item["matched_products"].append(name)
            contents.append(item)

    if not contents:
        if all(coverage.get(p, "").startswith("skip") for p in platforms):
            coverage["note"] = "无可用平台凭证"
        else:
            coverage["note"] = "本周无 KOL 内容"
    return contents, coverage


def search_keyword(query: str, platforms: List[str], window_days: int,
                   max_results: int) -> tuple:
    """Profiles-free KOL search by an arbitrary free-text query (topic mode).

    Unlike search_product (which iterates a profile's name+aliases and tags hits
    against the tracked competitor set), this calls each platform fetcher with the
    raw user query and tags with an EMPTY profile list — product matching is empty
    but the industry×role scene tags (keyword-dictionary driven, not profile driven)
    still apply, which is exactly what single-topic feedback wants.

    Each platform isolated (Principle VI): _SkipUnconfigured → coverage skip,
    other exceptions → coverage error. Returns (kol_contents, coverage_row)."""
    coverage: Dict[str, str] = {"query": query}
    seen_urls = set()
    contents: List[Dict[str, Any]] = []

    for plat in platforms:
        fn = _FETCHERS.get(plat)
        if fn is None:
            coverage[plat] = "skip(unknown-platform)"
            continue
        got_plat: List[Dict[str, Any]] = []
        try:
            for item in fn(query, window_days, max_results):
                u = item.get("url") or (item.get("title", "") + plat)
                if u in seen_urls:
                    continue
                seen_urls.add(u)
                got_plat.append(item)
            coverage[plat] = f"ok({len(got_plat)})"
        except _SkipUnconfigured as e:
            coverage[plat] = f"skip({e})"
            continue
        except Exception as e:  # noqa: BLE001 — any platform failure must be soft (VI)
            logging.warning(f"[keyword:{query}] {plat} failed: {e}")
            coverage[plat] = f"error({type(e).__name__})"
            continue

        for item in got_plat[:max_results]:
            tagged = tagging.tag_kol_content(item, [])
            item["matched_products"] = tagged.get("matched_products", [])
            item["industry_tags"] = tagged.get("industry_tags", [])
            item["role_scene_tags"] = tagged.get("role_scene_tags", [])
            item["agent_extra_tags"] = tagged.get("agent_extra_tags", [])
            contents.append(item)

    if not contents:
        if all(coverage.get(p, "").startswith("skip") for p in platforms):
            coverage["note"] = "无可用平台凭证"
        else:
            coverage["note"] = "本窗口无 KOL 内容"
    return contents, coverage


def load_profiles_via_official(path: str) -> List[Dict[str, Any]]:
    """Reuse fetch-competitor-official.load_profiles for identical validation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "competitor_official", Path(__file__).resolve().parent / "fetch-competitor-official.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_profiles(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search competitor KOL content across CN platforms")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--profiles", help="competitor-profiles.json: search each product's name+aliases")
    src.add_argument("--query", help="free-text topic keyword (profiles-free, topic-feedback mode)")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--out", "-o", default=None, help="default /tmp/competitor-kol.json")
    parser.add_argument("--only-product", default=None)
    parser.add_argument("--platforms", default=",".join(ALL_PLATFORMS),
                        help=f"comma list of {ALL_PLATFORMS}; default all")
    parser.add_argument("--max-per-product", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    )

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    # ── Keyword (topic-feedback) mode: profiles-free, single free-text query ──
    if args.query:
        kc, cov = search_keyword(args.query, platforms, args.window_days, args.max_per_product)
        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": args.window_days,
            "platforms": platforms,
            "query": args.query,
            "kol_contents": kc,
            "coverage": [cov],
        }
        out_path = args.out or str(Path(tempfile.gettempdir()) / "competitor-kol.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        logging.info(f"Wrote {len(kc)} KOL items for query '{args.query}' → {out_path}")
        return 0

    # ── Profiles mode (weekly / competitor-brief) ──
    if not Path(args.profiles).exists():
        logging.error(f"--profiles path does not exist: {args.profiles}")
        return 2

    profiles = load_profiles_via_official(args.profiles)
    if args.only_product:
        profiles = [p for p in profiles if p["name"] == args.only_product
                    or args.only_product in p.get("aliases", [])]

    all_kol: List[Dict[str, Any]] = []
    coverage_rows: List[Dict[str, str]] = []
    for p in profiles:
        if not p.get("enabled", True):
            continue
        kc, cov = search_product(p, platforms, args.window_days, args.max_per_product, profiles)
        all_kol.extend(kc)
        coverage_rows.append(cov)
        logging.info(f"  {p['name']}: {len(kc)} KOL items")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": args.window_days,
        "platforms": platforms,
        "kol_contents": all_kol,
        "coverage": coverage_rows,
    }
    out_path = args.out or str(Path(tempfile.gettempdir()) / "competitor-kol.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logging.info(f"Wrote {len(all_kol)} KOL items across {len(coverage_rows)} products → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
