#!/usr/bin/env python3
"""
On-demand competitor research brief (US3). Triggered for the full competitor set
(default), a single product, or an industry; aggregates official updates + KOL
scenes + cross-competitor peers into JSON (for the agent) and markdown (for
humans). Modeled on topic-feedback.py (concurrent + 10-min cache + dual output).
No LLM — horizontal comparison writing is the agent's job via
references/prompts/competitor-brief.md (Principle II).

Usage:
    python competitor-brief.py [--all]            [--window-days 30]  # default = all 28
    python competitor-brief.py --product "通义灵码" [--window-days 30]
    python competitor-brief.py --industry "教育"   [--window-days 30]

Contract: specs/006-domestic-agent-monitor/contracts/competitor-brief-cli.md
"""

import argparse
import hashlib
import importlib.util
import json
import logging
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import competitor_tagging as tagging

CACHE_DIR = Path(tempfile.gettempdir()) / "competitor-brief-cache"
CACHE_TTL_SECONDS = 600
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILES = SCRIPTS_DIR.parent / "workspace-config" / "competitor-profiles.json"


def _load_official_module():
    """Import the hyphenated fetch-competitor-official.py as a module (R6 reuse)."""
    path = SCRIPTS_DIR / "fetch-competitor-official.py"
    spec = importlib.util.spec_from_file_location("fetch_competitor_official", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.json"


def _cache_get(key: str) -> Optional[Dict]:
    p = _cache_path(key)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _cache_put(key: str, value: Dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _cache_path(key).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logging.debug(f"cache write failed: {e}")


def collect_official(official, profiles, window_days, token, product_names) -> List[Dict]:
    """Run official crawl concurrently across the target product(s)."""
    targets = [p for p in profiles if p["name"] in product_names]
    updates: List[Dict] = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(targets)))) as ex:
        futures = [ex.submit(official.crawl_product, p, window_days, token) for p in targets]
        for fut in futures:
            try:
                ups, _cov = fut.result()
                updates.extend(ups)
            except Exception as e:  # noqa: BLE001 — soft per Principle VI
                logging.warning(f"official crawl worker failed: {e}")
    return updates


def build_brief(args) -> Dict[str, Any]:
    official = _load_official_module()
    profiles = official.load_profiles(str(args.profiles))
    import os
    token = os.environ.get("GITHUB_TOKEN")

    if args.product:
        target = next(
            (p for p in profiles if p["name"] == args.product or args.product in p.get("aliases", [])),
            None,
        )
        if not target:
            available = ", ".join(p["name"] for p in profiles)
            raise SystemExit(f"product '{args.product}' not in profiles. Available: {available}")
        subject_type, subject = "product", target["name"]
        product_names = [target["name"]]
        peers = [p["name"] for p in profiles
                 if p["category"] == target["category"] and p["name"] != target["name"]]
    elif args.industry:
        valid_inds = set(tagging.INDUSTRY_KEYWORDS.keys())
        if args.industry not in valid_inds:
            raise SystemExit(f"industry '{args.industry}' not in skeleton. Available: {', '.join(valid_inds)}")
        subject_type, subject = "industry", args.industry
        product_names = [p["name"] for p in profiles]
        peers = product_names
    else:
        # Default (no flag) or explicit --all: research the full tracked set.
        subject_type, subject = "all", "全部竞品"
        product_names = [p["name"] for p in profiles]
        peers = product_names

    updates = collect_official(official, profiles, args.window_days, token, product_names)

    # KOL: real multi-platform fetch via fetch-competitor-kol.py (006 US2).
    # Degrades to [] on any failure / missing credentials (R5, Principle VI).
    kol_contents: List[Dict] = _collect_kol_best_effort(
        args.profiles, args.window_days,
        only_product=subject if subject_type == "product" else None,
    )
    if subject_type == "industry":
        kol_contents = [k for k in kol_contents if subject in k.get("industry_tags", [])]

    scene = {
        "industry": dict(Counter(t for k in kol_contents for t in k.get("industry_tags", []))),
        "role_scene": dict(Counter(t for k in kol_contents for t in k.get("role_scene_tags", []))),
    }

    return {
        "subject_type": subject_type,
        "subject": subject,
        "window_days": args.window_days,
        "updates": sorted(updates, key=lambda u: u.get("date") or "", reverse=True),
        "kol_contents": kol_contents,
        "scene_distribution": scene,
        "peers": peers,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _collect_kol_best_effort(profiles_path, window_days, only_product=None) -> List[Dict]:
    """Run fetch-competitor-kol.py and return its tagged kol_contents.

    Each item is already tagged (industry_tags / role_scene_tags / matched_products)
    by the fetcher. Bilibili is anonymous (risk-gate permitting); 知乎/即刻/公众号
    need user-supplied credentials and are skipped observably. Any failure → []
    (graceful, R5 / Principle VI)."""
    import os
    import subprocess
    import tempfile

    script = SCRIPTS_DIR / "fetch-competitor-kol.py"
    if not script.exists():
        logging.info("fetch-competitor-kol.py not present; KOL collection degrades to empty")
        return []
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    out_tmp = Path(tempfile.gettempdir()) / "competitor-brief-kol.json"
    cmd = [sys.executable, str(script),
           "--profiles", str(profiles_path),
           "--window-days", str(window_days),
           "--out", str(out_tmp)]
    if only_product:
        cmd += ["--only-product", only_product]
    try:
        subprocess.run(cmd, check=False, timeout=900, env=child_env)
        if not out_tmp.exists():
            return []
        with open(out_tmp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("kol_contents", []) or []
    except Exception as e:  # noqa: BLE001
        logging.info(f"KOL collection unavailable, degrading: {e}")
        return []


def render_markdown(brief: Dict) -> str:
    lines: List[str] = []
    lines.append(f"# 竞品调研：{brief['subject']}（{brief['subject_type']}，近 {brief['window_days']} 天）")
    lines.append("")
    updates = brief["updates"]
    kol = brief["kol_contents"]
    if not updates and not kol:
        lines.append("> **暂无足够数据**：该对象近期未采集到官方动态或 KOL 内容。")
        return "\n".join(lines)

    lines.append("## 官方动态时间线")
    if updates:
        if brief["subject_type"] == "all":
            # Full-set brief: group the timeline per product so the agent gets a
            # long-report skeleton instead of one flat firehose.
            by_product: Dict[str, List[Dict]] = {}
            for u in updates:
                by_product.setdefault(u.get("product", "(未知)"), []).append(u)
            for product in sorted(by_product.keys()):
                items = by_product[product]
                lines.append(f"### {product}（{len(items)}）")
                for u in items:
                    date = u.get("date") or "(日期未知)"
                    lines.append(f"- **{date[:10]}** [{u['source_kind']}/{u['type']}] {u['title']} — [原文]({u['url']})")
                    if u.get("summary"):
                        lines.append(f"  - {u['summary']}")
        else:
            for u in updates:
                date = u.get("date") or "(日期未知)"
                lines.append(f"- **{date[:10]}** [{u['source_kind']}/{u['type']}] {u['title']} — [原文]({u['url']})")
                if u.get("summary"):
                    lines.append(f"  - {u['summary']}")
    else:
        lines.append("- 本窗口无官方动态。")
    lines.append("")

    lines.append("## KOL 行业/岗位场景分布")
    sd = brief["scene_distribution"]
    if kol:
        lines.append(f"- 行业：{sd['industry'] or '（无）'}")
        lines.append(f"- 岗位/场景：{sd['role_scene'] or '（无）'}")
        for k in kol[:20]:
            tags = "/".join(k.get("industry_tags", []) + k.get("role_scene_tags", []))
            lines.append(f"- [{k.get('platform','?')}] {k.get('title','')} ({tags}) — [原文]({k.get('url','')})")
    else:
        lines.append("- 本窗口无 KOL 内容（KOL 源未配置或未采集到）。")
    lines.append("")

    lines.append("## 横向对比骨架（同类竞品）")
    lines.append(f"- 同类产品：{', '.join(brief['peers']) or '（无）'}")
    lines.append("- 横向方向对比由 agent 依据 competitor-brief.md prompt 撰写。")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="On-demand competitor research brief")
    g = parser.add_mutually_exclusive_group(required=False)
    g.add_argument("--all", action="store_true", help="research the full tracked competitor set (default when no flag given)")
    g.add_argument("--product", help="product name or alias")
    g.add_argument("--industry", help="industry from the R4 skeleton")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-md", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S",
    )

    cache_key = f"{args.product or args.industry or 'all'}|{args.window_days}"
    brief = _cache_get(cache_key)
    if brief is None:
        brief = build_brief(args)
        _cache_put(cache_key, brief)
    else:
        logging.info("served from cache")

    subject_slug = (brief["subject"] or "brief").replace("/", "_").replace(" ", "_")
    out_json = Path(args.out_json) if args.out_json else (
        Path(tempfile.gettempdir()) / f"competitor-brief-{subject_slug}.json")
    out_md = Path(args.out_md) if args.out_md else (
        Path(tempfile.gettempdir()) / f"competitor-brief-{subject_slug}.md")

    out_json.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(brief), encoding="utf-8")
    logging.info(f"brief written → {out_json} / {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
