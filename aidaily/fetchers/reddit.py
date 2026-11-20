"""Reddit 抓取：r/LocalLLaMA、r/MachineLearning 是开源模型圈的风向标。

热度信号：score（点赞数）和 num_comments，都是真实用户行为。

注意：reddit.com 在国内直连经常被重置，默认**不开启**（见 .env 的 SOURCES）。
有代理时把它加进去，信息密度很高。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import Settings
from ..models import RawDoc
from .base import Fetcher, http_get

log = logging.getLogger(__name__)

# 关注的子版块；第一个是开源模型圈，第二个是学术圈
SUBREDDITS = ["LocalLLaMA", "MachineLearning"]
API = "https://www.reddit.com/r/{sub}/top.json"


def parse_reddit(payload: dict, subreddit: str, limit: int = 25) -> list[RawDoc]:
    docs: list[RawDoc] = []
    children = (payload.get("data") or {}).get("children") or []
    for child in children:
        data = child.get("data") or {}
        title = " ".join(str(data.get("title") or "").split())
        if not title or data.get("stickied"):
            continue
        permalink = data.get("permalink") or ""
        url = (
            f"https://www.reddit.com{permalink}"
            if permalink
            else data.get("url")
            or f"https://www.reddit.com/r/{subreddit}"
        )
        score = int(data.get("score") or 0)
        comments = int(data.get("num_comments") or 0)
        created = data.get("created_utc")
        published = (
            datetime.fromtimestamp(float(created), tz=timezone.utc) if created else None
        )
        selftext = " ".join(str(data.get("selftext") or "").split())[:600]
        docs.append(
            RawDoc(
                source="reddit",
                title=title,
                url=url,
                summary_raw=f"r/{subreddit} · {score} 赞 · {comments} 评论"
                + (f"\n{selftext}" if selftext else ""),
                published_at=published,
                tags=[subreddit],
                heat=score,
                heat_label=f"▲{score}",
            )
        )
        if len(docs) >= limit:
            break
    return docs


class RedditFetcher(Fetcher):
    name = "reddit"

    def _fetch(self) -> list[RawDoc]:
        docs: list[RawDoc] = []
        for sub in SUBREDDITS:
            try:
                resp = http_get(
                    API.format(sub=sub),
                    params={"t": "day", "limit": 30},
                    headers={"Accept": "application/json"},
                    timeout=self.settings.request_timeout,
                )
                docs.extend(parse_reddit(resp.json(), sub))
            except Exception as exc:  # noqa: BLE001 - 单个子版块失败不影响整体
                log.warning("[reddit] r/%s 抓取失败：%s", sub, exc)
        return docs
