"""topic-feedback.py — V2EX comment parse, KOL subprocess injection, markdown.

All network/subprocess mocked. Asserts the new default-on comment enrichment
(HN/V2EX) and the KOL keyword subprocess wire into the `sources` payload with
the documented shapes, and that render_markdown emits the V2EX + KOL sections."""

import importlib.machinery
import json


# ─── a fake enrich_comments the SourceFileLoader will hand back ─────────────────

class _FakeLoader:
    """Stand-in for importlib.machinery.SourceFileLoader.

    topic-feedback does `SourceFileLoader("enrich_comments", path).load_module()`
    inside the worker; we patch the class so load_module returns our fake."""

    def __init__(self, name, path):
        self._name = name

    def load_module(self):
        return _FAKE_ENRICHER


class _FakeEnricher:
    SOV2EX_SEARCH = "https://sov2ex.test/api/search?q={query}"

    def __init__(self):
        self.hits = []
        self.comments = []

    def _http_get_json(self, url):
        return {"hits": self.hits}

    def fetch_v2ex_comments(self, topic_id, max_count=5):
        return list(self.comments)

    def _fetch_hn_story_comments(self, story_id, max_count):
        return [{"platform": "hn", "content": f"comment on {story_id}",
                 "author": "alice", "likes": 0,
                 "url": f"https://news.ycombinator.com/item?id={story_id}"}]


_FAKE_ENRICHER = _FakeEnricher()


def _disable_cache(topic, monkeypatch):
    monkeypatch.setattr(topic, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(topic, "cache_put", lambda *a, **k: None)


# ─── V2EX search ────────────────────────────────────────────────────────────────

def test_search_v2ex_parses_topics_and_comments(topic, monkeypatch):
    _disable_cache(topic, monkeypatch)
    _FAKE_ENRICHER.hits = [
        {"_source": {"id": "111", "replies": 30, "title": "Claude Code 实测",
                     "content": "claude code 后台任务很顺手", "created": "2026-06-20T10:00:00"}},
        {"_source": {"id": "222", "replies": 1, "title": "无关帖",
                     "content": "claude code", "created": "2026-06-20T10:00:00"}},  # < min_replies → drop
        {"_source": {"id": "333", "replies": 9, "title": "另一个主题",
                     "content": "完全无关内容", "created": "2026-06-20T10:00:00"}},  # term miss → drop
    ]
    _FAKE_ENRICHER.comments = [
        {"platform": "v2ex", "content": "用了一周很稳", "author": "bob",
         "likes": 0, "url": "https://www.v2ex.com/t/111"}
    ]
    monkeypatch.setattr(importlib.machinery, "SourceFileLoader", _FakeLoader)

    out = topic.search_v2ex("claude code", 30)
    assert out["status"] == "ok"
    assert out["count"] == 1                       # only topic 111 qualifies
    r = out["results"][0]
    assert r["topic_id"] == "111"
    assert r["replies"] == 30
    assert r["comments"][0]["author"] == "bob"
    assert r["url"].startswith("https://www.v2ex.com/t/")


def test_search_v2ex_missing_enricher_skips(topic, monkeypatch):
    _disable_cache(topic, monkeypatch)
    monkeypatch.setattr(topic.Path, "exists", lambda self: False)
    out = topic.search_v2ex("x", 30)
    assert out["status"].startswith("skipped")
    assert out["count"] == 0


# ─── HN enrichment default-on path ──────────────────────────────────────────────

def test_search_hn_enrich_populates_top_comments(topic, monkeypatch):
    _disable_cache(topic, monkeypatch)
    _FAKE_ENRICHER.hits = [
        {"objectID": "900", "title": "HN story", "url": "https://ex/a",
         "points": 200, "num_comments": 50, "author": "x", "created_at": "2026-06-20"}
    ]
    monkeypatch.setattr(importlib.machinery, "SourceFileLoader", _FakeLoader)
    out = topic.search_hn("claude", 30, enrich=True)
    assert out["status"] == "ok"
    assert out["results"][0]["top_comments"]       # enrichment ran (default-on caller)
    assert out["results"][0]["top_comments"][0]["platform"] == "hn"


# ─── KOL subprocess worker ──────────────────────────────────────────────────────

def test_search_kol_injects_subprocess_json(topic, monkeypatch, tmp_path):
    _disable_cache(topic, monkeypatch)
    payload = {
        "kol_contents": [
            {"platform": "bilibili", "title": "agent 实践", "url": "https://b/v1",
             "industry_tags": ["金融"], "role_scene_tags": ["研发"], "matched_products": []}
        ],
        "coverage": [{"query": "agent", "bilibili": "ok(1)", "zhihu": "skip(no cookie)"}],
    }

    def fake_run(cmd, *a, **k):
        out_idx = cmd.index("--out")
        with open(cmd[out_idx + 1], "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        class R:  # noqa: D401 - stub completed-process
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(topic.subprocess, "run", fake_run)
    out = topic.search_kol("agent", 30)
    assert out["status"] == "ok"
    assert out["count"] == 1
    assert out["results"][0]["platform"] == "bilibili"
    assert out["coverage"][0]["bilibili"] == "ok(1)"


def test_search_kol_no_output_file_is_soft(topic, monkeypatch):
    _disable_cache(topic, monkeypatch)

    def fake_run(cmd, *a, **k):
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()  # writes nothing

    monkeypatch.setattr(topic.subprocess, "run", fake_run)
    out = topic.search_kol("agent-no-output-distinct", 30)
    assert out["status"].startswith("error")
    assert out["count"] == 0


# ─── markdown rendering includes the new sections ───────────────────────────────

def test_render_markdown_has_v2ex_and_kol_sections(topic):
    payload = {
        "query": "Claude Code",
        "days": 30,
        "generated_at": "2026-06-26T00:00:00+00:00",
        "no_results_hint": None,
        "sources": {
            "hn": {"status": "ok", "count": 0, "results": []},
            "twitter": {"status": "skipped", "count": 0, "results": []},
            "trendradar_cn": {"status": "ok", "count": 0, "results": []},
            "v2ex": {"status": "ok", "count": 1, "results": [
                {"title": "实测帖", "url": "https://www.v2ex.com/t/1", "topic_id": "1",
                 "replies": 20, "comments": [
                     {"platform": "v2ex", "content": "很好用", "author": "bob",
                      "likes": 0, "url": "https://www.v2ex.com/t/1"}]}
            ]},
            "kol": {"status": "ok", "count": 1,
                    "coverage": [{"query": "Claude Code", "bilibili": "ok(1)",
                                  "zhihu": "skip(no cookie)"}],
                    "results": [
                        {"platform": "bilibili", "title": "agent 实践",
                         "url": "https://b/v1", "industry_tags": ["金融"],
                         "role_scene_tags": ["研发"]}]},
        },
    }
    md = topic.render_markdown(payload)
    assert "## V2EX 中文技术社区" in md
    assert "## KOL 行业/岗位场景" in md
    assert "https://www.v2ex.com/t/1" in md
    assert "bilibili" in md
    assert "ok(1)" in md                            # coverage rendered
    assert "金融/研发" in md                          # tags joined
