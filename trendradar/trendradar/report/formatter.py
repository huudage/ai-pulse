# coding=utf-8
"""
平台标题格式化模块

提供多平台标题格式化功能
"""

from typing import Dict, List

from trendradar.report.helpers import clean_title, html_escape, format_rank_display


def _format_likes(n: int) -> str:
    """点赞数压缩展示：1234 → 1.2k, 23456 → 2.3w"""
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


def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True, show_keyword: bool = False
) -> str:
    """统一的标题格式化方法

    为不同平台生成对应格式的标题字符串。

    Args:
        platform: 目标平台，支持:
            - "feishu": 飞书
            - "dingtalk": 钉钉
            - "wework": 企业微信
            - "bark": Bark
            - "telegram": Telegram
            - "ntfy": ntfy
            - "slack": Slack
            - "html": HTML 报告
        title_data: 标题数据字典，包含以下字段:
            - title: 标题文本
            - source_name: 来源名称
            - time_display: 时间显示
            - count: 出现次数
            - ranks: 排名列表
            - rank_threshold: 高亮阈值
            - url: PC端链接
            - mobile_url: 移动端链接（优先使用）
            - is_new: 是否为新增标题（可选）
            - matched_keyword: 匹配的关键词（可选，platform 模式使用）
            - comments: 热门评论列表（可选），每项为 dict 含 content/author/likes
        show_source: 是否显示来源名称（keyword 模式使用）
        show_keyword: 是否显示关键词标签（platform 模式使用）

    Returns:
        格式化后的标题字符串
    """
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )

    link_url = title_data["mobile_url"] or title_data["url"]
    cleaned_title = clean_title(title_data["title"])
    if not cleaned_title:
        cleaned_title = link_url or title_data["url"] or ""

    # 获取关键词标签（platform 模式使用）
    keyword = title_data.get("matched_keyword", "") if show_keyword else ""

    # 评论块（按平台格式生成；无评论时为空串）
    comments_block = _render_comments_block(platform, title_data.get("comments") or [])

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"<font color='blue'>[{keyword}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']}次)</font>"

        return result + comments_block

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result + comments_block

    elif platform in ("wework", "bark"):
        # WeWork 和 Bark 使用 markdown 格式
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result + comments_block

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"<b>[{html_escape(keyword)}]</b> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}次)</code>"

        return result + comments_block

    elif platform == "ntfy":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result + comments_block

    elif platform == "slack":
        # Slack 使用 mrkdwn 格式
        if link_url:
            # Slack 链接格式: <url|text>
            formatted_title = f"<{link_url}|{cleaned_title}>"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"*[{keyword}]* {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        # 排名（使用 * 加粗）
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "slack"
        )
        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result + comments_block

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        # 构建前缀（来源或关键词）
        if show_source:
            prefix = f'<span class="source-tag">[{escaped_source_name}]</span> '
        elif show_keyword and keyword:
            escaped_keyword = html_escape(keyword)
            prefix = f'<span class="keyword-tag">[{escaped_keyword}]</span> '
        else:
            prefix = ""

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'{prefix}<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = f'{prefix}<span class="no-link">{escaped_title}</span>'

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}次)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title + comments_block

    else:
        return cleaned_title
