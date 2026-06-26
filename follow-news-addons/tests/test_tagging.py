"""T018 [US2]: industry×role keyword tagging, multi-label + empty on no-match."""


def test_finance_customer_service_tagging(tagging):
    res = tagging.tag_industry_role("某竞品用于金融行业的智能客服坐席辅助")
    assert "金融" in res["industry_tags"]
    assert "客服" in res["role_scene_tags"]


def test_multi_label(tagging):
    res = tagging.tag_industry_role("教育行业的备课与作业批改，同时辅助老师做数据分析报表")
    assert "教育" in res["industry_tags"]
    assert "数据分析" in res["role_scene_tags"]


def test_no_match_returns_empty(tagging):
    res = tagging.tag_industry_role("今天天气不错适合散步")
    assert res["industry_tags"] == []
    assert res["role_scene_tags"] == []


def test_empty_text(tagging):
    res = tagging.tag_industry_role("")
    assert res == {"industry_tags": [], "role_scene_tags": []}


def test_coding_role(tagging):
    res = tagging.tag_industry_role("帮程序员写代码、修 bug、做重构的编程助手")
    assert "研发" in res["role_scene_tags"]
