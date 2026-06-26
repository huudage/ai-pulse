"""006 US2: multi-platform KOL fetcher — normalization, tagging, dedup, degrade.

All network is mocked; no live calls. Asserts each platform soft-fails to a
coverage annotation (Principle VI) and that hits are normalized + industry/role
tagged via competitor_tagging (Principle II — deterministic, no LLM)."""

import os


SAMPLE_PROFILES = [
    {"name": "通义灵码", "aliases": ["通义灵码", "Lingma"], "category": "coding",
     "enabled": True, "official_sources": {}},
    {"name": "Kimi", "aliases": ["Kimi"], "category": "general_agent",
     "enabled": True, "official_sources": {}},
]


# ─── normalization ────────────────────────────────────────────────────────────

def test_mk_kol_strips_html_and_truncates(kol):
    item = kol._mk_kol(
        title="<b>金融</b>风控实战", url="https://x/v", author="UP主",
        date_iso="2026-06-20T00:00:00+00:00", platform="bilibili",
        summary="<p>" + "长" * 400 + "</p>",
    )
    assert item["title"] == "金融风控实战"          # tags stripped
    assert item["platform"] == "bilibili"
    assert len(item["summary"]) <= 281               # truncated + ellipsis
    assert item["summary"].endswith("…")


def test_mk_kol_blank_title_fallback(kol):
    item = kol._mk_kol("", "https://x", "", None, "zhihu", "")
    assert item["title"] == "(无标题)"


def test_within_window_filters_old(kol):
    import time
    now = time.time()
    assert kol._within(now, 7) is True
    assert kol._within(now - 30 * 86400, 7) is False
    assert kol._within(None, 7) is True              # undated → keep


# ─── per-platform graceful degradation (Principle VI) ──────────────────────────

def test_zhihu_skips_without_cookie(kol, monkeypatch):
    monkeypatch.delenv("ZHIHU_COOKIE", raising=False)
    try:
        kol.fetch_zhihu("通义灵码", 7, 5)
        assert False, "expected _SkipUnconfigured"
    except kol._SkipUnconfigured:
        pass


def test_jike_skips_without_token(kol, monkeypatch):
    monkeypatch.delenv("JIKE_ACCESS_TOKEN", raising=False)
    try:
        kol.fetch_jike("通义灵码", 7, 5)
        assert False, "expected _SkipUnconfigured"
    except kol._SkipUnconfigured:
        pass


def test_weixin_skips_without_endpoint(kol, monkeypatch):
    monkeypatch.delenv("WEIXIN_SEARCH_URL", raising=False)
    try:
        kol.fetch_weixin("通义灵码", 7, 5)
        assert False, "expected _SkipUnconfigured"
    except kol._SkipUnconfigured:
        pass


def test_search_product_unconfigured_all_skip(kol, monkeypatch):
    # No creds + bilibili stubbed to raise its risk-gate skip.
    monkeypatch.delenv("ZHIHU_COOKIE", raising=False)
    monkeypatch.delenv("JIKE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WEIXIN_SEARCH_URL", raising=False)

    def bili_gated(*a, **k):
        raise kol._SkipUnconfigured("bilibili 风控拦截")
    monkeypatch.setitem(kol._FETCHERS, "bilibili", bili_gated)

    contents, coverage = kol.search_product(
        SAMPLE_PROFILES[0], kol.ALL_PLATFORMS, 7, 5, SAMPLE_PROFILES)
    assert contents == []
    assert coverage["product"] == "通义灵码"
    for p in kol.ALL_PLATFORMS:
        assert coverage[p].startswith("skip")
    assert coverage["note"] == "无可用平台凭证"


def test_search_product_worker_exception_is_soft(kol, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated network blowup")
    monkeypatch.setitem(kol._FETCHERS, "bilibili", boom)
    contents, coverage = kol.search_product(
        SAMPLE_PROFILES[0], ["bilibili"], 7, 5, SAMPLE_PROFILES)
    assert contents == []
    assert coverage["bilibili"].startswith("error")   # annotated, not raised


# ─── tagging + dedup on real hits ──────────────────────────────────────────────

def test_search_product_tags_and_dedups(kol, monkeypatch):
    hit = {
        "title": "通义灵码在金融风控的研发实践", "url": "https://www.bilibili.com/video/BV1",
        "author": "UP", "date": "2026-06-20T00:00:00+00:00", "platform": "bilibili",
        "summary": "面向研发团队的编码场景演示",
    }
    # Same url returned twice → must dedup to one.
    monkeypatch.setitem(kol._FETCHERS, "bilibili", lambda q, w, l: [dict(hit), dict(hit)])

    contents, coverage = kol.search_product(
        SAMPLE_PROFILES[0], ["bilibili"], 7, 5, SAMPLE_PROFILES)
    assert coverage["bilibili"].startswith("ok(")
    assert len(contents) == 1                          # deduped by url
    item = contents[0]
    # Tagged by competitor_tagging.
    assert "通义灵码" in item["matched_products"]
    assert "金融" in item.get("industry_tags", [])
    assert any("研发" in t or "编码" in t for t in item.get("role_scene_tags", []))


def test_search_product_forces_searched_product_into_matches(kol, monkeypatch):
    # Title lacks any alias → tagging won't match, but searched product is added.
    hit = {"title": "一个无关标题", "url": "https://x/p/2", "author": "a",
           "date": None, "platform": "zhihu", "summary": "无关内容"}
    monkeypatch.setitem(kol._FETCHERS, "zhihu", lambda q, w, l: [dict(hit)])
    contents, _ = kol.search_product(
        SAMPLE_PROFILES[0], ["zhihu"], 7, 5, SAMPLE_PROFILES)
    assert len(contents) == 1
    assert "通义灵码" in contents[0]["matched_products"]


# ─── keyword mode (profiles-free, topic-feedback) ──────────────────────────────

def test_search_keyword_dedups_by_url(kol, monkeypatch):
    hit = {"title": "Claude Code 后台任务实测", "url": "https://www.bilibili.com/video/BV9",
           "author": "UP", "date": "2026-06-20T00:00:00+00:00", "platform": "bilibili",
           "summary": "编码场景演示"}
    monkeypatch.setitem(kol._FETCHERS, "bilibili", lambda q, w, l: [dict(hit), dict(hit)])
    contents, coverage = kol.search_keyword("Claude Code", ["bilibili"], 7, 5)
    assert coverage["query"] == "Claude Code"
    assert coverage["bilibili"].startswith("ok(")
    assert len(contents) == 1                          # deduped by url


def test_search_keyword_empty_profiles_still_tags_scene(kol, monkeypatch):
    # No profiles, but industry/role tags (keyword-dict driven) must still apply.
    hit = {"title": "金融风控研发场景下的 agent 实践", "url": "https://x/kw/1",
           "author": "a", "date": None, "platform": "bilibili", "summary": "面向研发团队"}
    monkeypatch.setitem(kol._FETCHERS, "bilibili", lambda q, w, l: [dict(hit)])
    contents, _ = kol.search_keyword("agent", ["bilibili"], 7, 5)
    assert len(contents) == 1
    item = contents[0]
    assert item["matched_products"] == []              # no profiles → no product match
    assert "金融" in item.get("industry_tags", [])
    assert any("研发" in t for t in item.get("role_scene_tags", []))


def test_search_keyword_skip_and_error_coverage(kol, monkeypatch):
    def bili_skip(*a, **k):
        raise kol._SkipUnconfigured("风控拦截")
    def zhihu_boom(*a, **k):
        raise RuntimeError("network blowup")
    monkeypatch.setitem(kol._FETCHERS, "bilibili", bili_skip)
    monkeypatch.setitem(kol._FETCHERS, "zhihu", zhihu_boom)
    contents, coverage = kol.search_keyword("x", ["bilibili", "zhihu"], 7, 5)
    assert contents == []
    assert coverage["bilibili"].startswith("skip")
    assert coverage["zhihu"].startswith("error")


def test_search_keyword_unknown_platform(kol):
    contents, coverage = kol.search_keyword("x", ["nope"], 7, 5)
    assert contents == []
    assert coverage["nope"].startswith("skip(unknown-platform)")
