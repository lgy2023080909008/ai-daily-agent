"""抓取器注册表：新增数据源只要加一个类、加一行注册。

哪些源默认开启由 .env 的 SOURCES 控制（默认：arxiv,huggingface,github,rss,hackernews）。
reddit 和 hf_models 在国内直连常不通，需要代理时再手动启用。
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..models import RawDoc
from .arxiv import ArxivFetcher
from .base import Fetcher
from .github import GithubFetcher
from .hackernews import HackerNewsFetcher
from .hf_models import HuggingFaceModelsFetcher
from .huggingface import HuggingFaceFetcher
from .reddit import RedditFetcher
from .rss import RssFetcher

log = logging.getLogger(__name__)

# 名字 → 抓取器类。新增源时只改这里。
REGISTRY: dict[str, type[Fetcher]] = {
    "arxiv": ArxivFetcher,
    "huggingface": HuggingFaceFetcher,
    "hf_models": HuggingFaceModelsFetcher,
    "github": GithubFetcher,
    "rss": RssFetcher,
    "hackernews": HackerNewsFetcher,
    "reddit": RedditFetcher,
}

__all__ = [
    "REGISTRY",
    "Fetcher",
    "build_fetchers",
    "fetch_all",
]


def build_fetchers(settings: Settings) -> list[Fetcher]:
    """按 SOURCES 配置实例化抓取器；未知名字只警告不报错。"""
    fetchers: list[Fetcher] = []
    for name in settings.source_list:
        cls = REGISTRY.get(name)
        if cls is None:
            log.warning("未知数据源：%s（可选：%s）", name, ", ".join(REGISTRY))
            continue
        fetchers.append(cls(settings))
    return fetchers


def fetch_all(settings: Settings) -> list[RawDoc]:
    """抓取全部启用的源。单个抓取器抛异常不影响其他源（内部已重试+缓存兜底）。"""
    docs: list[RawDoc] = []
    for fetcher in build_fetchers(settings):
        try:
            docs.extend(fetcher.fetch())
        except Exception as exc:  # noqa: BLE001 - 兜底，保证日报还能出
            log.error("[%s] 抓取器异常退出：%s", fetcher.name, exc)
    return docs
