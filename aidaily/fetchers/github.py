"""GitHub 近期涨星仓库（AI 方向）。

说明：GitHub 官方没有 trending API，网页版抓 HTML 很容易随改版失效。
这里改用官方 search API：找「最近 N 天创建、star 较多」的仓库，再按关键词过滤 AI 相关，
数据来源稳定、不需要 token（未认证有速率限制，所以我们只请求一次）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import Settings
from ..keywords import looks_ai_related
from ..models import RawDoc
from .base import Fetcher, http_get

API = "https://api.github.com/search/repositories"


def parse_github(payload: dict) -> list[RawDoc]:
    docs: list[RawDoc] = []
    for repo in payload.get("items", []):
        full_name = repo.get("full_name") or ""
        desc = repo.get("description") or ""
        topics = repo.get("topics") or []
        # 关键词粗筛：名字 / 描述 / topics 任一命中 AI 关键词才留下
        if not looks_ai_related(full_name, desc, " ".join(topics)):
            continue
        stars = repo.get("stargazers_count") or 0
        docs.append(
            RawDoc(
                source="github",
                title=f"{full_name}（★{stars}）",
                url=repo.get("html_url") or "",
                summary_raw=f"{desc}\n语言：{repo.get('language') or '未知'}；topics：{', '.join(topics)}"[:1200],
                published_at=None,
                tags=list(topics)[:8],
                heat=int(stars),
                heat_label=f"★{stars}",
            )
        )
    return docs


class GithubFetcher(Fetcher):
    name = "github"

    def _fetch(self) -> list[RawDoc]:
        since = (
            datetime.now(timezone.utc) - timedelta(days=self.settings.github_days)
        ).date().isoformat()
        resp = http_get(
            API,
            params={
                "q": f"created:>={since} stars:>10",
                "sort": "stars",
                "order": "desc",
                "per_page": 30,
            },
            headers={"Accept": "application/vnd.github+json"},
            timeout=self.settings.request_timeout,
        )
        return parse_github(resp.json())
