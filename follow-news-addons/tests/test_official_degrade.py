"""T008 [US1]: every source soft-fails to [] + coverage annotation, no exception."""


def test_sources_return_empty_on_network_failure(official, monkeypatch):
    monkeypatch.setattr(official, "http_get_json", lambda url, token=None: None)
    monkeypatch.setattr(official, "http_get_text", lambda url: None)
    assert official.fetch_github("p", "o/r", 7, None) == []
    assert official.fetch_appstore("p", "1", 7) == []
    assert official.fetch_rss("p", "https://x", 7) == []
    assert official.fetch_sitemap("p", "https://x", 7) == []
    assert official.fetch_changelog("p", "https://x", ".item", 7) == []


def test_crawl_product_unconfigured_sources_annotated(official):
    profile = {"name": "WorkBuddy", "aliases": ["WorkBuddy"], "category": "office",
               "enabled": True, "official_sources": {}}
    updates, coverage = official.crawl_product(profile, window_days=7, token=None)
    assert updates == []
    assert coverage["product"] == "WorkBuddy"
    assert coverage.get("note") == "无配置官方源"
    for k in ("github", "changelog", "sitemap", "appstore", "rss"):
        assert coverage[k].startswith("skip")


def test_crawl_product_source_exception_is_soft(official, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated")
    monkeypatch.setattr(official, "fetch_github", boom)
    profile = {"name": "X", "aliases": ["X"], "category": "coding", "enabled": True,
               "official_sources": {"github_repo": "o/r"}}
    updates, coverage = official.crawl_product(profile, window_days=7, token=None)
    assert updates == []
    assert coverage["github"].startswith("error")  # annotated, not raised


def test_load_profiles_broken_file_returns_empty(official, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert official.load_profiles(str(bad)) == []


def test_load_profiles_skips_invalid_items(official, tmp_path):
    cfg = tmp_path / "p.json"
    cfg.write_text(
        '{"profiles":['
        '{"name":"Good","aliases":["g"],"category":"coding"},'
        '{"name":"","aliases":["x"],"category":"coding"},'
        '{"name":"BadCat","aliases":["b"],"category":"nope"},'
        '{"name":"NoAlias","aliases":[],"category":"rpa"}'
        ']}', encoding="utf-8")
    profiles = official.load_profiles(str(cfg))
    assert [p["name"] for p in profiles] == ["Good"]
