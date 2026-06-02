# coding=utf-8
"""
评论抓取模块 - 为热榜条目抓取热门评论

仅 demo 阶段支持知乎和 B 站热搜。
失败不阻塞主流程，外部调用方拿到空字典即可继续推送。
"""

from trendradar.crawler.comments.base import Comment, CommentFetcher
from trendradar.crawler.comments.dispatcher import CommentDispatcher

__all__ = ["Comment", "CommentFetcher", "CommentDispatcher"]
