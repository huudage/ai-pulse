# coding=utf-8
"""
RSS / Atom 旁路导出

把当次抓取的 stats 输出成标准 Atom XML，写到 output/rss/<basename>.xml。
为 follow-news 等聚合器提供消费入口（file:// 协议）。

不接入主通知流程，失败只打日志，不抛。
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom


ATOM_NS = "http://www.w3.org/2005/Atom"


def _iso(dt: datetime) -> str:
    """Atom 要求 RFC3339 带时区的 ISO 字符串"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _format_summary(title_data: Dict) -> str:
    """构造 entry summary：包含来源/排名，再附加已抓取的评论（如有）"""
    parts: List[str] = []
    source = title_data.get("source_name", "")
    ranks = title_data.get("ranks") or []
    if ranks:
        parts.append(f"[{source}] 当前排名: {min(ranks)}")
    elif source:
        parts.append(f"[{source}]")

    comments = title_data.get("comments") or []
    if comments:
        parts.append("热门评论:")
        for c in comments[:5]:
            content = (c.get("content") or "").strip()
            author = c.get("author") or "匿名"
            likes = c.get("likes") or 0
            if content:
                parts.append(f"• {content} — {author} (👍 {likes})")

    return "\n".join(parts)


def _build_atom(
    stats: List[Dict],
    feed_title: str,
    feed_id: str,
    feed_link: str,
    generated_at: datetime,
) -> ET.Element:
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    feed.set("xmlns", ATOM_NS)

    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = feed_title
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = feed_id
    link = ET.SubElement(feed, f"{{{ATOM_NS}}}link")
    link.set("href", feed_link)
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = _iso(generated_at)

    seen_ids = set()
    for stat in stats or []:
        word = stat.get("word", "")
        for title_data in stat.get("titles", []) or []:
            title = (title_data.get("title") or "").strip()
            if not title:
                continue

            source_name = title_data.get("source_name", "")
            url = title_data.get("mobile_url") or title_data.get("url") or ""
            entry_id = f"trendradar:{source_name}:{title}"
            if entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)

            entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
            entry_title = f"[{source_name}] {title}" if source_name else title
            ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = entry_title
            ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = entry_id

            if url:
                entry_link = ET.SubElement(entry, f"{{{ATOM_NS}}}link")
                entry_link.set("href", url)

            ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = _iso(generated_at)
            ET.SubElement(entry, f"{{{ATOM_NS}}}published").text = _iso(generated_at)

            if source_name:
                cat_source = ET.SubElement(entry, f"{{{ATOM_NS}}}category")
                cat_source.set("term", source_name)
            if word:
                cat_word = ET.SubElement(entry, f"{{{ATOM_NS}}}category")
                cat_word.set("term", word)

            summary_text = _format_summary(title_data)
            if summary_text:
                ET.SubElement(entry, f"{{{ATOM_NS}}}summary").text = summary_text

    return feed


def export_rss(
    stats: List[Dict],
    frequency_file: Optional[str] = None,
    output_dir: Optional[Path] = None,
    feed_title: str = "TrendRadar 热榜 RSS",
    feed_link: str = "https://github.com/sansan0/TrendRadar",
    generated_at: Optional[datetime] = None,
) -> Optional[str]:
    """把 stats 写成 Atom XML。

    Args:
        stats: prepare_report 输出的 stats（每项有 word/titles）
        frequency_file: 当前使用的关键词文件名，用来给 XML 命名；None 则用 default
        output_dir: 输出根目录，默认 ./output/rss
        feed_title / feed_link: feed 顶层元数据
        generated_at: 时间戳；None 则使用当前 UTC 时间

    Returns:
        生成的文件路径字符串；失败返回 None。
    """
    try:
        if not stats:
            print("[RSS 导出] stats 为空，跳过")
            return None

        if output_dir is None:
            output_dir = Path("output") / "rss"
        output_dir.mkdir(parents=True, exist_ok=True)

        basename = "default"
        if frequency_file:
            basename = Path(frequency_file).stem or "default"
        output_path = output_dir / f"{basename}.xml"

        now = generated_at or datetime.now(timezone.utc)
        feed_id = f"trendradar:{basename}:{now.strftime('%Y%m%d%H%M%S')}"

        feed = _build_atom(stats, feed_title, feed_id, feed_link, now)
        raw_xml = ET.tostring(feed, encoding="utf-8")
        pretty = minidom.parseString(raw_xml).toprettyxml(indent="  ", encoding="utf-8")

        output_path.write_bytes(pretty)
        entry_count = sum(len(s.get("titles", []) or []) for s in stats)
        print(f"[RSS 导出] 写入 {output_path}（约 {entry_count} 条 entry）")
        return str(output_path)

    except Exception as e:
        print(f"[RSS 导出] 失败（跳过，不影响主流程）: {e}")
        return None
