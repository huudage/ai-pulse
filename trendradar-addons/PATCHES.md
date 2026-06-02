# TrendRadar Patch 参考

本文档说明 `patches/trendradar/upstream.patch` **修改了上游哪些文件、修改了什么**。用途：

- 升级上游 TrendRadar SHA 时知道要 rebase 哪些点
- 手动 debug 时定位 patch 触碰到的 hook 位置

**普通用户不需要看本文档** —— `install.sh` 已自动应用所有改动。

patch 共修改 TrendRadar 上游的 **4 个文件**。

---

## 1. `trendradar/core/loader.py`

**在 `_load_display_config` 函数前** 加入新函数：

```python
def _load_comments_config(config_data: Dict) -> Dict:
    """加载评论抓取配置（实验性，默认关闭）"""
    comments = config_data.get("comments", {})

    def _int(value, default):
        try:
            v = int(value)
            return v if v >= 0 else default
        except (TypeError, ValueError):
            return default

    platforms = comments.get("platforms", []) or []
    if not isinstance(platforms, list):
        platforms = []

    return {
        "ENABLED": bool(comments.get("enabled", False)),
        "MAX_PER_TITLE": _int(comments.get("max_per_title", 3), 3),
        "TOP_N_TITLES": _int(comments.get("top_n_titles", 5), 5),
        "REQUEST_INTERVAL": _int(comments.get("request_interval", 500), 500),
        "TIMEOUT": _int(comments.get("timeout", 8), 8),
        "PLATFORMS": [str(p) for p in platforms if p],
    }
```

**在主 load_config 流程里** （`config["RSS"] = _load_rss_config(...)` 行之后）加：

```python
    # 评论抓取配置（实验性）
    config["COMMENTS"] = _load_comments_config(config_data)
```

---

## 2. `trendradar/report/__init__.py`

**新增 import 与导出**：

```python
from trendradar.report.rss_export import export_rss
```

把 `export_rss` 加进 `__all__` 列表。

---

## 3. `trendradar/report/formatter.py`

**新增辅助函数**（放在文件顶部 import 之后）：

```python
def _format_likes(n: int) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 10000:
        return f"{n / 10000:.1f}w"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _render_comments_block(platform: str, comments: List[Dict]) -> str:
    """按平台格式拼接评论块。无评论返回空串。"""
    if not comments:
        return ""

    if platform == "telegram":
        items = []
        for c in comments:
            content = html_escape((c.get("content") or "").strip())
            author = html_escape(c.get("author") or "匿名")
            likes = _format_likes(c.get("likes") or 0)
            items.append(f"   • {content} — <i>{author}</i> 👍 {likes}")
        return "\n💬 热评:\n" + "\n".join(items)

    if platform == "html":
        items = []
        for c in comments:
            content = html_escape((c.get("content") or "").strip())
            author = html_escape(c.get("author") or "匿名")
            likes = _format_likes(c.get("likes") or 0)
            items.append(
                f'<li>{content} — <span class="comment-author">{author}</span>'
                f' <span class="comment-likes">👍 {likes}</span></li>'
            )
        return '<div class="comments-block">💬 热评：<ul>' + "".join(items) + "</ul></div>"

    if platform == "slack":
        items = []
        for c in comments:
            content = (c.get("content") or "").strip()
            author = c.get("author") or "匿名"
            likes = _format_likes(c.get("likes") or 0)
            items.append(f"   • {content} — _{author}_ 👍 {likes}")
        return "\n💬 热评:\n" + "\n".join(items)

    # 通用 markdown 路径：feishu / dingtalk / wework / bark / ntfy
    items = []
    for c in comments:
        content = (c.get("content") or "").strip()
        author = c.get("author") or "匿名"
        likes = _format_likes(c.get("likes") or 0)
        items.append(f"   • {content} — *{author}* 👍 {likes}")
    return "\n💬 热评:\n" + "\n".join(items)
```

**在 `format_title_for_platform` 函数顶部**（计算完 keyword 之后）加：

```python
    # 评论块（按平台格式生成；无评论时为空串）
    comments_block = _render_comments_block(platform, title_data.get("comments") or [])
```

**在每个平台分支的 `return result` 前** 改成 `return result + comments_block`；HTML 分支的 `return formatted_title` 改成 `return formatted_title + comments_block`。

完整修改后的版本参见 [TrendRadar 仓库的实际文件](https://github.com/sansan0/TrendRadar/blob/main/trendradar/report/formatter.py)（已应用所有改动）。

---

## 4. `trendradar/__main__.py`

**导入加一行**：

```python
from trendradar.crawler.comments import CommentDispatcher
```

**`NewsAnalyzer.__init__` 末尾** 添加：

```python
        # 评论抓取（实验性）- 默认空字典，run() 中若启用会填充
        self.comments_map: Dict[Tuple[str, str], List[Dict]] = {}
```

**新增方法** `_crawl_comments`（紧接 `_crawl_data` 之后）：

```python
    def _crawl_comments(self, results: Dict) -> Dict[Tuple[str, str], List[Dict]]:
        """为白名单平台的 Top N 热榜抓取热门评论（实验性）"""
        comments_cfg = self.ctx.config.get("COMMENTS", {})
        if not comments_cfg.get("ENABLED", False):
            return {}
        platforms = comments_cfg.get("PLATFORMS", []) or []
        if not platforms:
            return {}
        try:
            dispatcher = CommentDispatcher(
                enabled_platforms=platforms,
                max_per_title=comments_cfg.get("MAX_PER_TITLE", 3),
                top_n_titles=comments_cfg.get("TOP_N_TITLES", 5),
                request_interval_ms=comments_cfg.get("REQUEST_INTERVAL", 500),
                proxy_url=self.proxy_url or "",
                timeout=comments_cfg.get("TIMEOUT", 8),
            )
            if not dispatcher.supported_platforms:
                return {}
            print(f"[评论] 抓取启动，目标平台: {dispatcher.supported_platforms}")
            comments_map = dispatcher.crawl(results)
            return {key: [c.to_dict() for c in comments] for key, comments in comments_map.items()}
        except Exception as e:
            print(f"[评论] 抓取过程出错（跳过，不影响主流程）: {e}")
            return {}
```

**新增方法** `_inject_comments_into_report` 和 `_export_rss_sidecar`（接在 `_crawl_comments` 后面，完整源码见 ai-pulse 仓库的现有实现，或对照本目录 `_PATCH_REFERENCE_main.py`）。

**`run()` 方法里** 在 `_crawl_data()` 之后追加：

```python
            # 抓取评论数据（实验性，仅白名单平台 Top N 条热榜）
            self.comments_map = self._crawl_comments(results)
```

**`_send_notification_if_needed` 里** 在 `report_data = self.ctx.prepare_report(...)` 之后加：

```python
            # 注入评论数据到 report_data（实验性）
            self._inject_comments_into_report(report_data, id_to_name)
```

**`_execute_mode_strategy` 里** 在 HTML 报告生成完之后、`# 发送通知` 之前加：

```python
        # RSS 旁路导出（供 follow-news 等聚合器消费）
        self._export_rss_sidecar(stats)
```

---

## 一键应用建议

由于改动跨多个文件，建议直接 fork TrendRadar 到自己仓库，然后把 ai-pulse 的 `trendradar-addons/` 文件复制到对应位置，并按上述说明手动加上 4 处修改。改动总计约 100 行。
