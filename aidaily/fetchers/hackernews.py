"""Hacker News 抓取：目前最好的"技术圈热度"信号，官方 API 免费无鉴权。

为什么值得接：HN 每条故事都有分数（points）和评论数（num_comments），
这是**真实的人类投票**，比任何模型打分都客观，正好补上"热度"这一维。

接口：Algolia 提供的 HN 搜索 API，比 Firebase 那套更适合按热度筛选。
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import Settings
from ..keywords import looks_ai_related
from ..models import RawDoc
from .base import Fetcher, http_get

API = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hn(payload: dict, limit: int = 25) -> list[RawDoc]:
    docs: list[RawDoc] = []
    for hit in payload.get("hits", []):
        title = " ".join(str(hit.get("title") or "").split())
        if not title:
            continue
        if not looks_ai_related(title):
            continue
        # 有的故事没有外链（Ask HN / Show HN），用 HN 自己的讨论页
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        points = int(hit.get("points") or 0)
        comments = int(hit.get("num_comments") or 0)
        created = hit.get("created_at_i")
        published = (
            datetime.fromtimestamp(int(created), tz=timezone.utc) if created else None
        )
        docs.append(
            RawDoc(
                source="hackernews",
                title=title,
                url=url,
                summary_raw=f"HN 热度 {points} 分 · {comments} 条讨论"
                + (f"\n{hit.get('story_text', '')[:400]}" if hit.get("story_text") else ""),
                published_at=published,
                tags=["hackernews"],
                heat=points,
                heat_label=f"🔥{points}",
            )
        )
        if len(docs) >= limit:
            break
    return docs


class HackerNewsFetcher(Fetcher):
    name = "hackernews"

    def _fetch(self) -> list[RawDoc]:
        # 只取最近有一定热度的故事（20 分以上），再本地按 AI 关键词过滤
        resp = http_get(
            API,
            params={
                "tags": "story",
                "numericFilters": "points>20",
                "hitsPerPage": 80,
            },
            timeout=self.settings.request_timeout,
        )
        return parse_hn(resp.json())
