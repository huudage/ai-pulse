# coding=utf-8
"""知乎热榜评论抓取（实际抓取高赞回答摘录）"""

import re
from typing import List

import requests

from trendradar.crawler.comments.base import Comment, CommentFetcher


QUESTION_ID_PATTERN = re.compile(r"/question/(\d+)")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class ZhihuCommentFetcher(CommentFetcher):
    """从知乎问题页抓取高赞回答前 N 条作为'热门评论'"""

    API_URL = "https://www.zhihu.com/api/v4/questions/{qid}/answers"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.zhihu.com/",
    }

    def fetch(self, title: str, url: str, mobile_url: str, max_count: int) -> List[Comment]:
        qid = self._extract_qid(mobile_url) or self._extract_qid(url)
        if not qid:
            return []

        try:
            params = {
                "include": "data[*].voteup_count,author",
                "limit": max_count,
                "offset": 0,
                "order_by": "default",
            }
            resp = requests.get(
                self.API_URL.format(qid=qid),
                params=params,
                headers=self.HEADERS,
                proxies=self.proxies,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[评论] 知乎抓取失败 qid={qid}: {e}")
            return []

        comments: List[Comment] = []
        for item in (data.get("data") or [])[:max_count]:
            try:
                raw_html = item.get("content") or item.get("excerpt") or ""
                text = HTML_TAG_PATTERN.sub("", raw_html)
                author = (item.get("author") or {}).get("name", "匿名")
                likes = int(item.get("voteup_count") or 0)
                if not text.strip():
                    continue
                comments.append(
                    Comment(
                        content=self._truncate(text, 80),
                        author=author or "匿名",
                        likes=likes,
                    )
                )
            except Exception:
                continue

        return comments

    @staticmethod
    def _extract_qid(url: str) -> str:
        if not url:
            return ""
        m = QUESTION_ID_PATTERN.search(url)
        return m.group(1) if m else ""
