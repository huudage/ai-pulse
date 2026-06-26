# coding=utf-8
"""评论抓取器基类与数据结构"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class Comment:
    content: str
    author: str
    likes: int

    def to_dict(self) -> Dict:
        return asdict(self)


class CommentFetcher(ABC):
    """评论抓取器基类。所有实现必须捕获内部异常，失败返回空列表。"""

    DEFAULT_TIMEOUT = 8

    def __init__(self, proxy_url: str = "", timeout: int = DEFAULT_TIMEOUT):
        self.proxy_url = proxy_url
        self.timeout = timeout

    @property
    def proxies(self):
        if self.proxy_url:
            return {"http": self.proxy_url, "https": self.proxy_url}
        return None

    @abstractmethod
    def fetch(self, title: str, url: str, mobile_url: str, max_count: int) -> List[Comment]:
        ...

    @staticmethod
    def _truncate(text: str, limit: int = 80) -> str:
        text = (text or "").replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[:limit] + "…"

    @staticmethod
    def _format_likes(n: int) -> str:
        if n >= 10000:
            return f"{n / 10000:.1f}w"
        if n >= 1000:
            return f"{n / 1000:.1f}k"
        return str(n)
