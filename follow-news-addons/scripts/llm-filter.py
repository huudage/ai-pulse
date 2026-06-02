#!/usr/bin/env python3
"""
[DEPRECATED in default flow] LLM filter — semantic dedup + announcement verification.

⚠️  默认 weekly-feedback.py 流程不再调用本脚本。**LLM 工作交给 OpenClaw agent
   在阅读 weekly merged JSON 时按 references/prompts/competitor-monitor.md 的
   "4 阶段" 规则做（语义去重 → 发布验证 → 三维度分类 → 写报告）**。

本脚本保留作为**离线/高级用户选项**：
- 没有 OpenClaw 环境、需要独立产出过滤后的 JSON
- 或者 LLM 上下文窗口不足以一次处理所有 articles 时，可作为预处理减负

需要设置：
  LLM_FILTER_API_KEY: any LLM provider's API key (OpenAI / Anthropic / DeepSeek / Qwen via litellm)
  LLM_FILTER_MODEL:    litellm model id, e.g. "deepseek/deepseek-chat"
  LLM_FILTER_BASE_URL: optional base_url override

如果 LLM_FILTER_API_KEY 未设置，此脚本是 no-op（仅复制输入→输出 + 标记 _llm_filtered:false）。

用法：
    python3 llm-filter.py --input /tmp/td-merged.json --output /tmp/td-merged-filtered.json

注意：此脚本**不会**被 weekly-feedback.py 自动调用，需要你手动跑。
要让 weekly-feedback.py 调用它，传 `--llm-filter`（保留向后兼容）。
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def setup_logging(verbose: bool) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def _get_llm_settings() -> Optional[Dict[str, str]]:
    """Read LLM config from env. Return None if not configured."""
    api_key = os.environ.get("LLM_FILTER_API_KEY", "").strip()
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "model": os.environ.get("LLM_FILTER_MODEL", "deepseek/deepseek-chat").strip(),
        "base_url": os.environ.get("LLM_FILTER_BASE_URL", "").strip() or None,
    }


def _flatten_articles(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull all articles out of topics[*].articles into a flat list."""
    out = []
    topics = data.get("topics", {})
    if isinstance(topics, dict):
        for topic_id, topic_data in topics.items():
            for a in topic_data.get("articles", []) or []:
                a.setdefault("primary_topic", topic_id)
                out.append(a)
    return out


def _regroup_by_topic(articles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    topics: Dict[str, Dict[str, Any]] = {}
    for a in articles:
        pt = a.get("primary_topic") or "uncategorized"
        topics.setdefault(pt, {"count": 0, "articles": []})
        topics[pt]["articles"].append(a)
        topics[pt]["count"] += 1
    return topics


def _short_id(article: Dict[str, Any]) -> str:
    """Stable short id for LLM to refer back to articles."""
    seed = (article.get("link") or article.get("reddit_url") or article.get("title") or "")
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]


# ─── LLM calls ───────────────────────────────────────────────────────────────

CLUSTER_SYSTEM_PROMPT = """你是一个新闻去重助手。给你一批 AI 圈相关文章的标题+来源信息，你需要把"明显是同一事件不同来源报道的"分到同一组。

输出严格 JSON，结构：
{
  "clusters": [
    {"event": "事件名（精炼短描述）", "members": ["id1", "id2", ...]},
    ...
  ]
}

注意：
- 同一事件可以来自不同源、不同标题写法，但描述的是同一件事
- 不同 release 版本（如 v3.0 vs v3.1）属于不同事件
- 不同公司同时间的类似动作（如 OpenAI 和 Anthropic 都发模型）属于不同事件
- 只把高置信度的同事件分组在一起；不确定的就让它单独成组
"""

VERIFY_SYSTEM_PROMPT = """你是一个 AI 圈竞品监控筛选员。给你一篇文章信息，判断它是不是"新模型发布 / 新技术架构发布 / 新产品发布"。

输出严格 JSON：
{
  "is_announcement": true | false,
  "dimension": "model" | "architecture" | "product" | "none",
  "reason": "≤30 字理由"
}

规则：
- model: 基础模型新版本、新模态模型、推理模型发布
- architecture: 训练/推理框架 major 版本、新协议（MCP/Hermes 等）、新 Agent 框架开源
- product: 旗舰 Agent 产品（Cursor/Devin/Claude Code 等）能力质变（不是小功能升级）
- none: 行业评论、blog 解读、benchmark 综述、研究论文、KOL 推文、产品小升级、招聘信息、营销软文

务必严格：升级算不算"发布"？
- 主力模型主版本号变更（v3 → v4）：是
- 同一模型小版本（v4.0 → v4.1）+ 含新能力描述：是
- 仅改 UI 配色 / 加快捷键：不是
- "增强 X 能力"但没有版本号变更：往往不是，需谨慎判断
"""


def _call_llm_json(model: str, api_key: str, base_url: Optional[str], system: str, user: str, max_tokens: int = 2000) -> Optional[Dict]:
    """Single LLM call returning parsed JSON. Returns None on failure."""
    try:
        import litellm
        kwargs = {
            "model": model,
            "api_key": api_key,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url
        resp = litellm.completion(**kwargs)
        content = resp["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        logging.warning(f"LLM call failed: {e}")
        return None


# ─── Cluster pass ────────────────────────────────────────────────────────────

def cluster_articles(
    articles: List[Dict[str, Any]],
    settings: Dict[str, str],
    logger: logging.Logger,
    batch_size: int = 60,
) -> Dict[str, str]:
    """Returns mapping: article_id → cluster_event_name (or own id if singleton)."""
    if not articles:
        return {}

    cluster_map: Dict[str, str] = {}

    # Process in batches to fit LLM context
    for batch_start in range(0, len(articles), batch_size):
        batch = articles[batch_start: batch_start + batch_size]
        logger.info(f"  Clustering batch {batch_start//batch_size + 1}: {len(batch)} articles")

        # Build the user prompt
        lines = []
        for a in batch:
            aid = a["_id"]
            title = (a.get("title") or "").strip()[:120]
            source = a.get("source_name", "")
            topic = a.get("primary_topic", "")
            lines.append(f"id={aid} | topic={topic} | source={source} | title={title}")
        user_prompt = "下面这批文章里哪些是同一事件？\n\n" + "\n".join(lines)

        result = _call_llm_json(
            settings["model"], settings["api_key"], settings["base_url"],
            CLUSTER_SYSTEM_PROMPT, user_prompt, max_tokens=4000,
        )
        if not result:
            continue

        for cluster in result.get("clusters", []) or []:
            event = cluster.get("event", "")
            members = cluster.get("members", []) or []
            if not members:
                continue
            for m in members:
                cluster_map[m] = event

    return cluster_map


# ─── Verification pass ───────────────────────────────────────────────────────

def verify_announcements(
    candidates: List[Dict[str, Any]],
    settings: Dict[str, str],
    logger: logging.Logger,
) -> None:
    """Mutates candidates: adds _llm_classification (is_announcement bool), _llm_dimension, _llm_reason."""
    logger.info(f"  Verifying {len(candidates)} candidate announcements via LLM")
    for i, a in enumerate(candidates, 1):
        title = (a.get("title") or "").strip()[:200]
        source = a.get("source_name", "")
        snippet = (a.get("snippet") or a.get("summary") or "")[:300]
        user_prompt = (
            f"文章信息：\n"
            f"标题: {title}\n"
            f"来源: {source}\n"
            f"摘要: {snippet}\n"
            f"原始 source_type: {a.get('source_type', '')}\n"
            f"\n请按规则判断是否为新模型/架构/产品发布。"
        )
        result = _call_llm_json(
            settings["model"], settings["api_key"], settings["base_url"],
            VERIFY_SYSTEM_PROMPT, user_prompt, max_tokens=200,
        )
        if not result:
            a["_llm_classification"] = "unknown"
            continue
        is_ann = bool(result.get("is_announcement"))
        a["_llm_classification"] = "announcement" if is_ann else "not-announcement"
        a["_llm_dimension"] = result.get("dimension", "none")
        a["_llm_reason"] = result.get("reason", "")
        if i % 10 == 0:
            logger.info(f"    Verified {i}/{len(candidates)}")


# ─── Main ────────────────────────────────────────────────────────────────────

# Pre-filter: which articles are even worth checking via LLM?
# These are the source_types that *could* be announcements (whitelist).
ANNOUNCEMENT_CANDIDATE_SOURCE_TYPES = {"rss", "github", "podcast"}


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM-based semantic dedup + announcement filter")
    parser.add_argument("--input", type=Path, required=True, help="Input merged JSON (from merge-sources.py)")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON (filtered)")
    parser.add_argument("--max-articles", type=int, default=300, help="Cap total articles processed (default: 300)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)

    if not args.input.exists():
        logger.error(f"Input not found: {args.input}")
        return 1

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = _flatten_articles(data)
    logger.info(f"Loaded {len(articles)} articles from {args.input.name}")

    # Cap if too many (cost control)
    if len(articles) > args.max_articles:
        # Keep highest-quality articles
        articles.sort(key=lambda x: x.get("quality_score", 0) or 0, reverse=True)
        articles = articles[: args.max_articles]
        logger.info(f"Capped to {args.max_articles} highest-quality articles")

    # Assign stable ids
    for a in articles:
        a["_id"] = _short_id(a)

    settings = _get_llm_settings()

    if not settings:
        logger.warning(
            "LLM_FILTER_API_KEY not set — running in pass-through mode "
            "(no semantic dedup, no announcement verification). "
            "Set LLM_FILTER_API_KEY + LLM_FILTER_MODEL to enable."
        )
        for a in articles:
            a["_llm_filtered"] = False
        data["topics"] = _regroup_by_topic(articles)
        data.setdefault("output_stats", {})["llm_filter"] = {"enabled": False, "reason": "no API key"}
    else:
        logger.info(f"LLM filter enabled: model={settings['model']}")

        # Pass 1: cluster (semantic dedup)
        logger.info("Pass 1: semantic clustering for dedup")
        cluster_map = cluster_articles(articles, settings, logger)
        clusters_by_event: Dict[str, List[Dict[str, Any]]] = {}
        for a in articles:
            event = cluster_map.get(a["_id"], a["_id"])
            clusters_by_event.setdefault(event, []).append(a)

        # Keep one canonical per cluster (highest quality_score)
        kept: List[Dict[str, Any]] = []
        merged_count = 0
        for event, group in clusters_by_event.items():
            if len(group) == 1:
                kept.append(group[0])
            else:
                primary = max(group, key=lambda x: x.get("quality_score", 0) or 0)
                primary["_cluster_event"] = event
                primary["_cluster_member_count"] = len(group)
                primary["_cluster_members"] = [
                    {"id": m["_id"], "title": m.get("title", "")[:100], "source": m.get("source_name", "")}
                    for m in group if m["_id"] != primary["_id"]
                ]
                kept.append(primary)
                merged_count += len(group) - 1
        logger.info(f"Clustering: {len(articles)} → {len(kept)} (merged {merged_count} duplicates)")
        articles = kept

        # Pass 2: verify which surviving articles are real announcements
        logger.info("Pass 2: announcement verification")
        candidates = [
            a for a in articles
            if a.get("source_type") in ANNOUNCEMENT_CANDIDATE_SOURCE_TYPES
        ]
        verify_announcements(candidates, settings, logger)

        # Mark all
        for a in articles:
            a["_llm_filtered"] = True

        # Regroup by topic
        data["topics"] = _regroup_by_topic(articles)
        verified_count = sum(1 for a in articles if a.get("_llm_classification") == "announcement")
        data.setdefault("output_stats", {})["llm_filter"] = {
            "enabled": True,
            "model": settings["model"],
            "after_cluster": len(articles),
            "verified_announcements": verified_count,
            "merged_duplicates": merged_count,
        }
        logger.info(f"LLM filter done: {verified_count} verified announcements")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"📄 Wrote filtered JSON → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
