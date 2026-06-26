#!/usr/bin/env python3
"""
Deterministic industry×role tagging + product disambiguation for the competitor
monitor. Library (imported by weekly-feedback.py and competitor-brief.py), no LLM.

- tag_industry_role(text): keyword-match an 8×8 industry×role skeleton → multi-label.
- match_product(text, profiles): associate text to ProductProfile by name/aliases.

The semantic "which direction / scene is the competitor pursuing" work is left to
the agent (Principle II). This only emits deterministic recall signals; edit the
dictionaries below to extend coverage without touching the main pipeline.

Skeleton defined in: specs/006-domestic-agent-monitor/research.md (R4)
"""

from typing import Dict, List

# ─── Industry × Role keyword skeleton (R4) ────────────────────────────────────

INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "金融": ["金融", "银行", "证券", "保险", "风控", "信贷", "理财", "券商", "基金", "支付"],
    "医疗": ["医疗", "医院", "医生", "问诊", "病历", "医保", "药", "健康", "诊断"],
    "教育": ["教育", "教学", "学校", "学生", "培训", "课程", "备课", "考试", "作业", "高校"],
    "政务": ["政务", "政府", "公文", "审批", "便民", "市民", "政策", "城市治理"],
    "电商": ["电商", "零售", "商品", "店铺", "带货", "选品", "客单", "直播电商", "淘宝", "拼多多"],
    "制造": ["制造", "工厂", "生产", "工业", "供应链", "质检", "设备", "车间", "产线"],
    "法律": ["法律", "律师", "合同", "合规", "诉讼", "法务", "裁判", "条款"],
    "内容媒体": ["自媒体", "内容创作", "文案", "短视频", "营销", "运营文案", "种草", "公众号写作"],
}

ROLE_KEYWORDS: Dict[str, List[str]] = {
    "研发": ["研发", "程序员", "写代码", "编程", "coding", "代码", "bug", "重构", "前端", "后端", "开发者"],
    "运营": ["运营", "增长", "活动", "用户运营", "社群", "私域", "拉新"],
    "销售": ["销售", "获客", "商机", "crm", "外呼", "线索", "成单"],
    "客服": ["客服", "工单", "答疑", "售后", "坐席", "在线客服"],
    "设计": ["设计", "ui", "海报", "作图", "绘图", "出图", "原型", "视觉"],
    "法务": ["法务", "合同审查", "合规审核", "审约"],
    "数据分析": ["数据分析", "报表", "bi", "取数", "看板", "数据可视化", "指标"],
    "行政HR": ["行政", "人事", "hr", "招聘", "考勤", "报销", "薪酬", "面试"],
}


def _match_dict(text_lower: str, dictionary: Dict[str, List[str]]) -> List[str]:
    hits: List[str] = []
    for label, kws in dictionary.items():
        for kw in kws:
            if kw.lower() in text_lower:
                hits.append(label)
                break
    return hits


def tag_industry_role(text: str) -> Dict[str, List[str]]:
    """Return {'industry_tags': [...], 'role_scene_tags': [...]} via deterministic
    multi-label keyword match. No match → empty lists (agent may add free tags)."""
    t = (text or "").lower()
    if not t.strip():
        return {"industry_tags": [], "role_scene_tags": []}
    return {
        "industry_tags": _match_dict(t, INDUSTRY_KEYWORDS),
        "role_scene_tags": _match_dict(t, ROLE_KEYWORDS),
    }


# ─── Product disambiguation (T021) ────────────────────────────────────────────

def match_product(text: str, profiles: List[Dict]) -> List[str]:
    """Return names of profiles whose name/aliases appear in text (multi-match).

    Aliases are the disambiguation keys (FR-001 / Edge: 泛词). Matching is
    case-insensitive substring; a product needs at least one alias hit."""
    if not text:
        return []
    t = text.lower()
    matched: List[str] = []
    for p in profiles:
        name = p.get("name", "")
        candidates = [name] + list(p.get("aliases") or [])
        for c in candidates:
            if c and c.lower() in t:
                matched.append(name)
                break
    return matched


def tag_kol_content(content: Dict, profiles: List[Dict]) -> Dict:
    """Normalize a raw KOL item into a KOLContent dict with product + tags.

    Expects content to carry at least title/url/author/date/platform and a
    text-ish field (title + summary). Mutates and returns the dict."""
    text = " ".join(str(content.get(k, "")) for k in ("title", "summary", "content", "desc"))
    tags = tag_industry_role(text)
    products = match_product(text, profiles)
    content["industry_tags"] = tags["industry_tags"]
    content["role_scene_tags"] = tags["role_scene_tags"]
    content.setdefault("agent_extra_tags", [])
    content["matched_products"] = products
    return content
