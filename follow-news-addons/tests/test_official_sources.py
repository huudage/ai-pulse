"""T007 [US1]: GitHub releases / iTunes lookup / RSS normalization."""
from datetime import datetime, timezone


def _recent_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_github_releases_normalize(official, monkeypatch):
    payload = [
        {"name": "v3.0", "tag_name": "v3.0", "html_url": "https://gh/r/3",
         "published_at": _recent_iso(), "body": "新功能 A", "draft": False},
        {"name": "draft", "tag_name": "d", "html_url": "x", "published_at": _recent_iso(),
         "body": "x", "draft": True},
    ]
    monkeypatch.setattr(official, "http_get_json", lambda url, token=None: payload)
    ups = official.fetch_github("CodeGeeX", "THUDM/CodeGeeX", window_days=7, token=None)
    assert len(ups) == 1
    u = ups[0]
    assert u["type"] == "release" and u["source_kind"] == "github"
    assert u["url"] == "https://gh/r/3"
    assert u["date"] is not None


def test_appstore_lookup_normalize(official, monkeypatch):
    payload = {"results": [{
        "trackName": "豆包", "version": "5.1", "trackViewUrl": "https://apps/x",
        "releaseNotes": "修复若干问题", "currentVersionReleaseDate": _recent_iso(),
    }]}
    monkeypatch.setattr(official, "http_get_json", lambda url, token=None: payload)
    ups = official.fetch_appstore("豆包", "123456", window_days=7)
    assert len(ups) == 1
    assert ups[0]["source_kind"] == "appstore"
    assert "豆包" in ups[0]["title"]
    assert ups[0]["summary"].startswith("修复")


def test_rss_normalize(official, monkeypatch):
    rss = f"""<?xml version="1.0"?><rss><channel>
      <item><title>新版本发布</title><link>https://blog/x</link>
      <pubDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>
      <description>&lt;p&gt;内容&lt;/p&gt;</description></item>
    </channel></rss>"""
    monkeypatch.setattr(official, "http_get_text", lambda url: rss)
    ups = official.fetch_rss("Kimi", "https://blog/rss", window_days=7)
    assert len(ups) == 1
    assert ups[0]["type"] == "feature" and ups[0]["source_kind"] == "rss"
    assert ups[0]["title"] == "新版本发布"


def test_sitemap_normalize(official, monkeypatch):
    sm = f"""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs/x/new-feature</loc><lastmod>{_recent_iso()}</lastmod></url>
      <url><loc>https://docs/x/old</loc><lastmod>2019-01-01</lastmod></url>
    </urlset>"""
    monkeypatch.setattr(official, "http_get_text", lambda url: sm)
    ups = official.fetch_sitemap("通义灵码", "https://docs/sitemap.xml", window_days=7)
    locs = [u["url"] for u in ups]
    assert "https://docs/x/new-feature" in locs
    assert "https://docs/x/old" not in locs
    assert ups[0]["type"] == "direction"


def test_parse_date_formats(official):
    assert official.parse_date("2026-06-20") is not None
    assert official.parse_date("2026年06月20日") is not None
    assert official.parse_date("garbage") is None
    assert official.parse_date(None) is None
