"""Hugging Face Daily Papers：社区热度最高的 AI 论文，JSON 接口，无 key。"""

from __future__ import annotations

from datetime import datetime

from ..config import Settings
from ..models import RawDoc
from .base import Fetcher, http_get

API = "https://huggingface.co/api/daily_papers"


def parse_hf(payload: list[dict], limit: int = 30) -> list[RawDoc]:
    docs: list[RawDoc] = []
    for item in payload[:limit]:
        paper = item.get("paper") or {}
        title = " ".join(str(paper.get("title") or "").split())
        if not title:
            continue
        paper_id = paper.get("id") or item.get("paperId") or ""
        url = f"https://huggingface.co/papers/{paper_id}" if paper_id else "https://huggingface.co/papers"
        published = None
        raw_date = paper.get("publishedAt") or item.get("publishedAt")
        if raw_date:
            try:
                published = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            except ValueError:
                published = None
        # HF 的点赞数就是最直接的热度信号
        upvotes = int(item.get("upvotes") or paper.get("upvotes") or 0)
        docs.append(
            RawDoc(
                source="huggingface",
                title=title,
                url=url,
                summary_raw=" ".join(str(paper.get("summary") or "").split())[:1200],
                published_at=published,
                tags=["paper"],
                heat=upvotes,
                heat_label=f"{upvotes} 赞" if upvotes else "",
            )
        )
    return docs


class HuggingFaceFetcher(Fetcher):
    name = "huggingface"

    def _fetch(self) -> list[RawDoc]:
        resp = http_get(API, params={"limit": 50}, timeout=self.settings.request_timeout)
        return parse_hf(resp.json())
