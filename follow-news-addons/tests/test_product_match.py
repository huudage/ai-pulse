"""T019 [US2]: alias disambiguation associates to the right product, no false positives."""


def test_match_by_alias(tagging, sample_profiles):
    assert tagging.match_product("最近用 Lingma 写代码很爽", sample_profiles) == ["通义灵码"]


def test_match_by_name(tagging, sample_profiles):
    assert "Kimi" in tagging.match_product("Kimi 的长文本能力测评", sample_profiles)


def test_multi_product(tagging, sample_profiles):
    matched = tagging.match_product("对比通义灵码和 Kimi", sample_profiles)
    assert set(matched) == {"通义灵码", "Kimi"}


def test_no_false_positive(tagging, sample_profiles):
    assert tagging.match_product("今天聊聊别的产品", sample_profiles) == []


def test_tag_kol_content_full(tagging, sample_profiles):
    item = {"title": "Kimi 在教育行业帮老师备课", "url": "u", "author": "a",
            "date": "2026-06-20", "platform": "bilibili"}
    out = tagging.tag_kol_content(item, sample_profiles)
    assert "Kimi" in out["matched_products"]
    assert "教育" in out["industry_tags"]
    assert out["agent_extra_tags"] == []
