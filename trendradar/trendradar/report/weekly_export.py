# coding=utf-8
"""
TrendRadar 7 天 weekly RSS 导出器

跟现有的 rss_export.py（每跑覆盖一份当前快照）不同，本脚本：
- 从 output/news/<date>.db 读最近 N 天的所有 news_items
- 应用关键词过滤（AI 圈聚焦）
- 合并去重
- 输出一份 weekly Atom XML 到 output/rss/weekly-<basename>.xml

供 follow-news 按需触发 weekly 聚合时通过 file:// 协议读取。

用法：
    python -m trendradar.report.weekly_export --days 7
    python -m trendradar.report.weekly_export --days 7 --frequency-file ai_focus.txt
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom


ATOM_NS = "http://www.w3.org/2005/Atom"


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _find_daily_dbs(news_dir: Path, days: int) -> List[Path]:
    """找 news_dir 下最近 N 天的 .db 文件，按日期降序。"""
    if not news_dir.is_dir():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).date()
    files: List[Tuple[datetime, Path]] = []
    for p in news_dir.glob("*.db"):
        try:
            d = datetime.strptime(p.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= cutoff:
            files.append((d, p))
    files.sort(reverse=True)
    return [p for _, p in files]


def _load_news_from_db(
    db_path: Path,
    platform_filter: Optional[List[str]] = None,
) -> List[Dict]:
    """从单个 .db 文件读取所有 news_items。"""
    items: List[Dict] = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 拉 platform 名字映射
        c.execute("SELECT id, name FROM platforms")
        id_to_name = {r["id"]: r["name"] for r in c.fetchall()}

        # 拉 news_items
        sql = "SELECT title, platform_id, rank, url, mobile_url, first_crawl_time, last_crawl_time, crawl_count FROM news_items"
        if platform_filter:
            placeholders = ",".join("?" * len(platform_filter))
            sql += f" WHERE platform_id IN ({placeholders})"
            c.execute(sql, platform_filter)
        else:
            c.execute(sql)

        for r in c.fetchall():
            items.append({
                "title": r["title"],
                "platform_id": r["platform_id"],
                "platform_name": id_to_name.get(r["platform_id"], r["platform_id"]),
                "rank": r["rank"],
                "url": r["url"] or "",
                "mobile_url": r["mobile_url"] or "",
                "first_crawl_time": r["first_crawl_time"],
                "last_crawl_time": r["last_crawl_time"],
                "crawl_count": r["crawl_count"],
                "_db_date": db_path.stem,  # YYYY-MM-DD
            })
        conn.close()
    except sqlite3.Error as e:
        print(f"[Weekly RSS] 读 {db_path.name} 失败: {e}")
    return items


def _load_keyword_filter(frequency_file: Optional[str]) -> Optional[callable]:
    """读关键词文件，返回一个 match(title) -> bool 的过滤函数。None 表示不过滤。"""
    if not frequency_file:
        return None

    candidates = [
        Path(frequency_file),
        Path("config/custom/keyword") / frequency_file,
        Path("config") / frequency_file,
    ]
    file_path = next((c for c in candidates if c.is_file()), None)
    if not file_path:
        print(f"[Weekly RSS] 关键词文件未找到: {frequency_file}（跳过过滤）")
        return None

    try:
        # 这里复用 TrendRadar 的关键词解析（轻量调用，不引入完整 pipeline）
        from trendradar.core.frequency import (
            load_frequency_words,
            matches_word_groups,
        )
        word_groups, filter_words, global_filters = load_frequency_words(str(file_path))
    except Exception as e:
        print(f"[Weekly RSS] 关键词加载失败: {e}（跳过过滤）")
        return None

    def _match(title: str) -> bool:
        try:
            return matches_word_groups(title, word_groups, filter_words, global_filters)
        except Exception:
            return False

    return _match


def _deduplicate(items: List[Dict]) -> List[Dict]:
    """按 (platform_id, title) 去重，保留最早 first_crawl_time、最新 last_crawl_time、最小 rank。"""
    by_key: Dict[Tuple[str, str], Dict] = {}
    for it in items:
        key = (it["platform_id"], it["title"].strip())
        if key not in by_key:
            by_key[key] = it.copy()
        else:
            existing = by_key[key]
            # 取更早的 first_crawl_time
            if it.get("first_crawl_time", "") < existing.get("first_crawl_time", "9999"):
                existing["first_crawl_time"] = it["first_crawl_time"]
            # 取更晚的 last_crawl_time
            if it.get("last_crawl_time", "") > existing.get("last_crawl_time", ""):
                existing["last_crawl_time"] = it["last_crawl_time"]
                existing["_db_date"] = it["_db_date"]
            # 取更小的 rank（更靠前）
            if it.get("rank", 9999) < existing.get("rank", 9999):
                existing["rank"] = it["rank"]
            existing["crawl_count"] = existing.get("crawl_count", 0) + it.get("crawl_count", 0)
    return list(by_key.values())


def _build_atom(
    items: List[Dict],
    feed_title: str,
    feed_id: str,
    feed_link: str,
    days: int,
    generated_at: datetime,
) -> ET.Element:
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    feed.set("xmlns", ATOM_NS)
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = f"{feed_title}（近 {days} 天）"
    ET.SubElement(feed, f"{{{ATOM_NS}}}id").text = feed_id
    link = ET.SubElement(feed, f"{{{ATOM_NS}}}link")
    link.set("href", feed_link)
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = _iso(generated_at)

    for it in items:
        title = it["title"]
        platform_name = it["platform_name"]
        url = it.get("mobile_url") or it.get("url") or ""
        entry_id = f"trendradar:weekly:{it['platform_id']}:{title}"

        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}title").text = f"[{platform_name}] {title}"
        ET.SubElement(entry, f"{{{ATOM_NS}}}id").text = entry_id
        if url:
            entry_link = ET.SubElement(entry, f"{{{ATOM_NS}}}link")
            entry_link.set("href", url)

        # 用 first_crawl_time 作为 published（首次出现）
        first_time = it.get("first_crawl_time", "")
        try:
            # first_crawl_time 在 TrendRadar 里是字符串如 "YYYY-MM-DD HH:MM" 或 ISO
            if first_time and "T" not in first_time and " " in first_time:
                dt = datetime.strptime(first_time, "%Y-%m-%d %H:%M")
                dt = dt.replace(tzinfo=timezone.utc)
            elif first_time:
                dt = datetime.fromisoformat(first_time.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = generated_at
        except Exception:
            dt = generated_at
        ET.SubElement(entry, f"{{{ATOM_NS}}}published").text = _iso(dt)
        ET.SubElement(entry, f"{{{ATOM_NS}}}updated").text = _iso(generated_at)

        # categories: 平台名 + 抓取日期范围
        cat_source = ET.SubElement(entry, f"{{{ATOM_NS}}}category")
        cat_source.set("term", platform_name)

        # summary
        summary_parts = [f"平台: {platform_name}", f"最小排名: {it.get('rank', '?')}"]
        if it.get("crawl_count"):
            summary_parts.append(f"被抓取 {it['crawl_count']} 次")
        summary_parts.append(f"最早出现: {first_time}")
        summary_parts.append(f"最后出现: {it.get('last_crawl_time', '?')}")
        ET.SubElement(entry, f"{{{ATOM_NS}}}summary").text = "\n".join(summary_parts)

    return feed


def export_weekly(
    days: int = 7,
    frequency_file: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    output_dir: Optional[Path] = None,
    news_dir: Optional[Path] = None,
    feed_title: str = "TrendRadar 中文 AI 热榜",
    feed_link: str = "https://github.com/sansan0/TrendRadar",
) -> Optional[str]:
    """从 SQLite 读最近 N 天，应用关键词过滤，输出 weekly Atom XML。"""
    try:
        if news_dir is None:
            news_dir = Path("output") / "news"
        if output_dir is None:
            output_dir = Path("output") / "rss"
        output_dir.mkdir(parents=True, exist_ok=True)

        dbs = _find_daily_dbs(news_dir, days)
        if not dbs:
            print(f"[Weekly RSS] 未找到 {news_dir} 下最近 {days} 天的 .db 文件")
            return None

        print(f"[Weekly RSS] 读取 {len(dbs)} 个 daily DB: {[p.name for p in dbs]}")

        all_items: List[Dict] = []
        for db in dbs:
            all_items.extend(_load_news_from_db(db, platform_filter=platforms))
        print(f"[Weekly RSS] 累计 {len(all_items)} 条 raw items")

        # 关键词过滤
        match_fn = _load_keyword_filter(frequency_file)
        if match_fn:
            filtered = [it for it in all_items if match_fn(it["title"])]
            print(f"[Weekly RSS] 关键词过滤后剩余 {len(filtered)}/{len(all_items)} 条")
            all_items = filtered

        # 去重
        deduped = _deduplicate(all_items)
        print(f"[Weekly RSS] 跨日去重后 {len(deduped)} 条")
        # 按 last_crawl_time 降序，新的在前
        deduped.sort(key=lambda x: x.get("last_crawl_time", ""), reverse=True)

        # 输出
        basename = Path(frequency_file).stem if frequency_file else "default"
        output_path = output_dir / f"weekly-{basename}.xml"
        now = datetime.now(timezone.utc)
        feed_id = f"trendradar:weekly:{basename}:{now.strftime('%Y%m%d%H%M%S')}"
        feed = _build_atom(deduped, feed_title, feed_id, feed_link, days, now)
        raw = ET.tostring(feed, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="utf-8")
        output_path.write_bytes(pretty)
        print(f"[Weekly RSS] 写入 {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"[Weekly RSS] 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description="TrendRadar 7 天 weekly RSS 导出")
    parser.add_argument("--days", type=int, default=7, help="回溯天数（默认 7）")
    parser.add_argument("--frequency-file", type=str, default="ai_focus.txt", help="关键词文件名（默认 ai_focus.txt）")
    parser.add_argument("--platforms", type=str, default=None, help="平台 ID 逗号分隔（默认全部）")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录（默认 output/rss）")
    parser.add_argument("--news-dir", type=Path, default=None, help="SQLite 目录（默认 output/news）")
    args = parser.parse_args()

    platforms = args.platforms.split(",") if args.platforms else None
    result = export_weekly(
        days=args.days,
        frequency_file=args.frequency_file,
        platforms=platforms,
        output_dir=args.output_dir,
        news_dir=args.news_dir,
    )
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
