"""通用 RSS / Atom 抓取：一个抓取器吃多个源（机器之心、IT之家……）。

实现上用标准库 `xml.etree` 自己解析，而不是引 feedparser：
- 少一个依赖，clone 下来装包更快；
- 解析逻辑看得见、改得动，测试可以用离线 XML 样本固定住；
- 单个源坏了只 `continue`，不影响其他源出内容。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from ..config import Settings
from ..keywords import looks_ai_related
from ..models import RawDoc
from .base import Fetcher, http_get

log = logging.getLogger(__name__)


def _local(tag: str) -> str:
    """去掉命名空间：'{http://...}title' → 'title'。"""
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, *names: str) -> str:
    for child in element:
        if _local(child.tag) in names:
            return (child.text or "").strip()
    return ""


def _child_attr(element: ET.Element, name: str, attr: str) -> str:
    for child in element:
        if _local(child.tag) == name and child.get(attr):
            return child.get(attr, "").strip()
    return ""


def _to_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)          # RSS: RFC 822
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))  # Atom: ISO 8601
    except ValueError:
        return None


def parse_feed_xml(xml_text: str, source: str, limit: int = 20) -> list[RawDoc]:
    """解析 RSS 2.0 或 Atom，返回过滤掉非 AI 内容的 RawDoc。"""
    root = ET.fromstring(xml_text)
    items = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]

    docs: list[RawDoc] = []
    for item in items[: limit * 3]:  # 先多取一些，关键词过滤后再截断
        title = " ".join(_child_text(item, "title").split())
        # RSS 用 <link>文本</link>，Atom 用 <link href="..."/>
        link = _child_text(item, "link") or _child_attr(item, "link", "href")
        if not title or not link:
            continue
        summary = _child_text(item, "description", "summary", "content")
        summary = " ".join(summary.split())[:1200]
        if not looks_ai_related(title, summary):
            continue
        published = _to_datetime(
            _child_text(item, "pubdate", "published", "updated")
        )
        docs.append(
            RawDoc(
                source=source,
                title=title,
                url=link,
                summary_raw=summary,
                published_at=published,
                tags=[source],
            )
        )
        if len(docs) >= limit:
            break
    return docs


class RssFetcher(Fetcher):
    name = "rss"

    def _fetch(self) -> list[RawDoc]:
        docs: list[RawDoc] = []
        for url in self.settings.rss_url_list:
            source = urlparse(url).netloc or "rss"
            try:
                resp = http_get(url, timeout=self.settings.request_timeout)
                docs.extend(parse_feed_xml(resp.text, source=source))
            except Exception as exc:  # noqa: BLE001 - 单源失败不影响其他源
                log.warning("[rss] %s 抓取/解析失败：%s", url, exc)
        return docs
