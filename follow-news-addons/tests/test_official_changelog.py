"""T006 [US1]: changelog HTML + CSS selector parsing."""

SAMPLE_HTML = """
<html><body>
<div class="changelog-item">
  <a href="/posts/v3">通义灵码 3.0 发布</a>
  <span class="date">2026-06-20</span>
  <p>新增多文件编辑能力。</p>
</div>
<div class="changelog-item">
  <a href="/posts/v2">2.9 更新</a>
  <span class="date">2020-01-01</span>
  <p>历史版本，超出窗口。</p>
</div>
<div class="sidebar">无关内容</div>
</body></html>
"""


def test_changelog_parses_items_with_selector(official, monkeypatch):
    monkeypatch.setattr(official, "http_get_text", lambda url: SAMPLE_HTML)
    updates = official.fetch_changelog("通义灵码", "https://x/cl", ".changelog-item", window_days=3650)
    titles = [u["title"] for u in updates]
    assert any("3.0" in t for t in titles)
    for u in updates:
        assert u["source_kind"] == "changelog"
        assert u["type"] == "feature"
        assert u["product"] == "通义灵码"


def test_changelog_window_filters_old(official, monkeypatch):
    monkeypatch.setattr(official, "http_get_text", lambda url: SAMPLE_HTML)
    updates = official.fetch_changelog("通义灵码", "https://x/cl", ".changelog-item", window_days=7)
    # The 2020 entry must be filtered out by the 7-day window.
    assert all("2.9" not in u["title"] for u in updates)


def test_changelog_no_selector_match_returns_empty(official, monkeypatch):
    monkeypatch.setattr(official, "http_get_text", lambda url: SAMPLE_HTML)
    updates = official.fetch_changelog("通义灵码", "https://x/cl", ".does-not-exist", window_days=3650)
    assert updates == []


def test_changelog_missing_selector_returns_empty(official, monkeypatch):
    monkeypatch.setattr(official, "http_get_text", lambda url: SAMPLE_HTML)
    assert official.fetch_changelog("p", "https://x/cl", None, window_days=7) == []
