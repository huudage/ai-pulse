"""T025 [US3]: brief CLI validation + empty-data 'no data' message."""
import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_brief():
    spec = importlib.util.spec_from_file_location("competitor_brief", SCRIPTS_DIR / "competitor-brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


brief_mod = _load_brief()


class _FakeOfficial:
    def load_profiles(self, path):
        return [{"name": "通义灵码", "aliases": ["Lingma"], "category": "coding",
                 "enabled": True, "official_sources": {}}]

    def crawl_product(self, profile, window_days, token):
        return [], {"product": profile["name"]}


def _args(**kw):
    base = dict(product=None, industry=None, window_days=7, profiles="x",
                out_json=None, out_md=None, verbose=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_empty_data_markdown_says_no_data():
    brief = {"subject": "X", "subject_type": "product", "window_days": 7,
             "updates": [], "kol_contents": [], "scene_distribution": {"industry": {}, "role_scene": {}},
             "peers": []}
    md = brief_mod.render_markdown(brief)
    assert "暂无足够数据" in md


def test_unknown_product_raises(monkeypatch):
    monkeypatch.setattr(brief_mod, "_load_official_module", lambda: _FakeOfficial())
    with pytest.raises(SystemExit):
        brief_mod.build_brief(_args(product="不存在的产品"))


def test_unknown_industry_raises(monkeypatch):
    monkeypatch.setattr(brief_mod, "_load_official_module", lambda: _FakeOfficial())
    with pytest.raises(SystemExit):
        brief_mod.build_brief(_args(industry="不存在行业"))


def test_known_product_builds(monkeypatch):
    monkeypatch.setattr(brief_mod, "_load_official_module", lambda: _FakeOfficial())
    out = brief_mod.build_brief(_args(product="通义灵码"))
    assert out["subject"] == "通义灵码"
    assert out["subject_type"] == "product"
    assert "peers" in out


def test_markdown_renders_updates():
    brief = {"subject": "通义灵码", "subject_type": "product", "window_days": 7,
             "updates": [{"date": "2026-06-20T00:00:00Z", "source_kind": "github",
                          "type": "release", "title": "v3.0", "url": "https://x", "summary": "新功能"}],
             "kol_contents": [], "scene_distribution": {"industry": {}, "role_scene": {}},
             "peers": ["Kimi"]}
    md = brief_mod.render_markdown(brief)
    assert "v3.0" in md and "时间线" in md


def test_all_mode_default_builds(monkeypatch):
    monkeypatch.setattr(brief_mod, "_load_official_module", lambda: _FakeOfficial())
    monkeypatch.setattr(brief_mod, "_collect_kol_best_effort", lambda *a, **k: [])
    out = brief_mod.build_brief(_args())  # no product / no industry → all
    assert out["subject_type"] == "all"
    assert out["subject"] == "全部竞品"
    assert out["peers"] == ["通义灵码"]


def test_all_mode_markdown_groups_by_product():
    brief = {"subject": "全部竞品", "subject_type": "all", "window_days": 30,
             "updates": [
                 {"product": "通义灵码", "date": "2026-06-20T00:00:00Z", "source_kind": "github",
                  "type": "release", "title": "Lingma v3.0", "url": "https://a", "summary": ""},
                 {"product": "Trae", "date": "2026-06-19T00:00:00Z", "source_kind": "appstore",
                  "type": "release", "title": "Trae 1.2", "url": "https://b", "summary": ""},
             ],
             "kol_contents": [], "scene_distribution": {"industry": {}, "role_scene": {}},
             "peers": ["通义灵码", "Trae"]}
    md = brief_mod.render_markdown(brief)
    assert "### 通义灵码（1）" in md
    assert "### Trae（1）" in md


def test_default_window_is_30():
    args = brief_mod.build_parser().parse_args([])
    assert args.window_days == 30
    assert not args.all and args.product is None and args.industry is None


def test_flags_mutually_exclusive():
    parser = brief_mod.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--all", "--product", "通义灵码"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--product", "X", "--industry", "金融"])
