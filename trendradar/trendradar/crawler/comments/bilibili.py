# coding=utf-8
"""B 站热搜评论抓取（先用关键词搜索取 Top 视频，再抓视频评论）"""

from typing import List, Optional, Tuple

import requests

from trendradar.crawler.comments.base import Comment, CommentFetcher


class BilibiliCommentFetcher(CommentFetcher):
    """B 站热搜词 → 第一条搜索结果视频 → 热门评论"""

    SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
    REPLY_URL = "https://api.bilibili.com/x/v2/reply/main"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bilibili.com/",
    }

    def fetch(self, title: str, url: str, mobile_url: str, max_count: int) -> List[Comment]:
        keyword = title.strip()
        if not keyword:
            return []

        aid = self._search_top_video(keyword)
        if not aid:
            return []

        return self._fetch_replies(aid, max_count)

    def _search_top_video(self, keyword: str) -> Optional[int]:
        try:
            params = {
                "search_type": "video",
                "keyword": keyword,
                "order": "totalrank",
                "page": 1,
            }
            resp = requests.get(
                self.SEARCH_URL,
                params=params,
                headers=self.HEADERS,
                proxies=self.proxies,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                print(f"[评论] B站搜索失败 keyword={keyword}: code={data.get('code')} msg={data.get('message')}")
                return None
            results = (data.get("data") or {}).get("result") or []
            if not results:
                return None
            first = results[0]
            aid = first.get("aid")
            return int(aid) if aid else None
        except Exception as e:
            print(f"[评论] B站搜索异常 keyword={keyword}: {e}")
            return None

    def _fetch_replies(self, aid: int, max_count: int) -> List[Comment]:
        try:
            params = {
                "type": 1,
                "oid": aid,
                "mode": 3,  # 3 = 热门评论
                "ps": max(max_count, 3),
            }
            resp = requests.get(
                self.REPLY_URL,
                params=params,
                headers=self.HEADERS,
                proxies=self.proxies,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                print(f"[评论] B站评论失败 aid={aid}: code={data.get('code')} msg={data.get('message')}")
                return []
        except Exception as e:
            print(f"[评论] B站评论异常 aid={aid}: {e}")
            return []

        replies = (data.get("data") or {}).get("replies") or []
        comments: List[Comment] = []
        for r in replies[:max_count]:
            try:
                content = ((r.get("content") or {}).get("message") or "").strip()
                if not content:
                    continue
                author = (r.get("member") or {}).get("uname", "匿名")
                likes = int(r.get("like") or 0)
                comments.append(
                    Comment(
                        content=self._truncate(content, 80),
                        author=author or "匿名",
                        likes=likes,
                    )
                )
            except Exception:
                continue
        return comments
