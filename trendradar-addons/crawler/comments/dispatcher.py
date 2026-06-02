# coding=utf-8
"""评论抓取分发器：按平台 ID 路由到对应抓取器，并控制 QPS"""

import random
import time
from typing import Dict, List, Tuple, Type

from trendradar.crawler.comments.base import Comment, CommentFetcher
from trendradar.crawler.comments.bilibili import BilibiliCommentFetcher
from trendradar.crawler.comments.zhihu import ZhihuCommentFetcher


# 平台 ID → 抓取器类
PLATFORM_REGISTRY: Dict[str, Type[CommentFetcher]] = {
    "zhihu": ZhihuCommentFetcher,
    "bilibili-hot-search": BilibiliCommentFetcher,
}


class CommentDispatcher:
    """根据配置为热榜条目抓取评论。

    返回结构：{(platform_id, title): [Comment, ...]}
    """

    def __init__(
        self,
        enabled_platforms: List[str],
        max_per_title: int = 3,
        top_n_titles: int = 5,
        request_interval_ms: int = 500,
        proxy_url: str = "",
        timeout: int = 8,
    ):
        self.max_per_title = max_per_title
        self.top_n_titles = top_n_titles
        self.request_interval_ms = request_interval_ms

        # 仅实例化白名单内且已注册的平台
        self.fetchers: Dict[str, CommentFetcher] = {}
        for pid in enabled_platforms:
            cls = PLATFORM_REGISTRY.get(pid)
            if cls is None:
                print(f"[评论] 平台 '{pid}' 未实现抓取器，跳过")
                continue
            self.fetchers[pid] = cls(proxy_url=proxy_url, timeout=timeout)

    @property
    def supported_platforms(self) -> List[str]:
        return list(self.fetchers.keys())

    def crawl(self, results: Dict[str, Dict]) -> Dict[Tuple[str, str], List[Comment]]:
        """
        为热榜结果中支持的平台抓取评论。

        Args:
            results: DataFetcher.crawl_websites 返回的结果字典
                     {platform_id: {title: {ranks, url, mobileUrl}}}

        Returns:
            {(platform_id, title): [Comment, ...]}
        """
        comments_map: Dict[Tuple[str, str], List[Comment]] = {}
        if not self.fetchers:
            return comments_map

        for platform_id, fetcher in self.fetchers.items():
            titles_data = results.get(platform_id)
            if not titles_data:
                continue

            # 按当前最小 rank 升序，取 Top N
            sorted_titles = sorted(
                titles_data.items(),
                key=lambda kv: min(kv[1].get("ranks") or [9999]),
            )[: self.top_n_titles]

            fetched_count = 0
            for title, data in sorted_titles:
                comments = fetcher.fetch(
                    title=title,
                    url=data.get("url", ""),
                    mobile_url=data.get("mobileUrl", ""),
                    max_count=self.max_per_title,
                )
                if comments:
                    comments_map[(platform_id, title)] = comments
                    fetched_count += 1

                # 请求间隔
                interval = self.request_interval_ms + random.randint(-50, 100)
                time.sleep(max(50, interval) / 1000)

            print(f"[评论] {platform_id} 抓到 {fetched_count}/{len(sorted_titles)} 条热榜的评论")

        return comments_map
