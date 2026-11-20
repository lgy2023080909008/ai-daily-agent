"""arXiv 抓取：官方 Atom API，不需要 key，是最稳定的一个源。"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from ..config import Settings
from ..models import RawDoc
from .base import Fetcher, http_get

log = logging.getLogger(__name__)

API = "http://export.arxiv.org/api/query"
# 只取 AI 相关的四个分类，按提交时间倒序
QUERY = "cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.CV"
NS = {"a": "http://www.w3.org/2005/Atom"}


def parse_arxiv(xml_text: str, limit: int = 50) -> list[RawDoc]:
    """把 Atom XML 解析成 RawDoc 列表（单独抽出来，方便用离线样本做单测）。"""
    root = ET.fromstring(xml_text)
    docs: list[RawDoc] = []
    for entry in root.findall("a:entry", NS)[:limit]:
        title = (entry.findtext("a:title", default="", namespaces=NS) or "").strip()
        title = " ".join(title.split())  # arXiv 标题里常有换行
        if not title:
            continue
        summary = (entry.findtext("a:summary", default="", namespaces=NS) or "").strip()
        link = (entry.findtext("a:id", default="", namespaces=NS) or "").strip()
        published_raw = entry.findtext("a:published", default="", namespaces=NS)
        try:
            published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published = None
        tags = [
            c.get("term", "")
            for c in entry.findall("a:category", NS)
            if c.get("term")
        ]
        docs.append(
            RawDoc(
                source="arxiv",
                title=title,
                url=link,
                summary_raw=" ".join(summary.split())[:1200],
                published_at=published,
                tags=tags,
            )
        )
    return docs


class ArxivFetcher(Fetcher):
    name = "arxiv"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.max_results = settings.arxiv_max_results

    def _fetch(self) -> list[RawDoc]:
        resp = http_get(
            API,
            params={
                "search_query": QUERY,
                "start": 0,
                "max_results": self.max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=self.settings.request_timeout,
        )
        return parse_arxiv(resp.text, limit=self.max_results)
