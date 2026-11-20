"""领域模型：抓取结果 → 规范化文档 → 日报条目。

数据链路只有三层，字段只增不减，方便排查：
    RawDoc（各源原始字段 + 热度） → Doc（加 id，可入库） → DigestItem（加推荐理由与摘要）
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_doc_id(title: str, url: str) -> str:
    """内容指纹：同一篇文章被多个源转载时，标题相同 → id 相同，天然去重。"""
    key = (title or url).strip().lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


class RawDoc(BaseModel):
    """抓取器返回的原始条目。"""

    source: str
    title: str
    url: str
    summary_raw: str = ""
    published_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    # 热度：源能给出的客观数字（GitHub star / HF 点赞 / HN 分数），没有就 0
    heat: int = 0
    heat_label: str = ""
    # 榜内排名与百分位：跨源比较时用这个，不直接比原始数字（见 prerank.annotate_heat）
    heat_rank: int = 0
    heat_pct: float = 0.0


class Doc(RawDoc):
    """规范化后的文档，可以入库。"""

    id: str = ""
    fetched_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_raw(cls, raw: RawDoc) -> "Doc":
        return cls(**raw.model_dump(), id=make_doc_id(raw.title, raw.url))


class RankPick(BaseModel):
    """模型从候选里挑中的一条。index 对应候选编号，从 1 开始。"""

    index: int = Field(description="候选列表里的编号")
    reason: str = Field(default="", description="为什么选它，30 字以内")


class RankResult(BaseModel):
    """模型返回的精选列表，按推荐顺序排列。"""

    picks: list[RankPick] = Field(default_factory=list)


class SummaryResult(BaseModel):
    """日报用的中文摘要。"""

    summary_zh: str = Field(description="50 字以内的中文摘要")
    why: str = Field(description="为什么值得看，30 字以内")


class DigestItem(BaseModel):
    doc: Doc
    rank: int = 0
    reason: str = ""
    summary_zh: str = ""
    why: str = ""


class Digest(BaseModel):
    date: str
    items: list[DigestItem] = Field(default_factory=list)
    stats: dict[str, int | float | str] = Field(default_factory=dict)
    markdown: str = ""
