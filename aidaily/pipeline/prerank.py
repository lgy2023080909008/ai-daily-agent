"""预筛：用零成本的规则先砍掉大部分，只把最值得看的一小批送进模型。

两个关键设计：

1. **跨源热度不可直接比**（这里踩过坑）：
   GitHub 的 star 动辄几千、HN 分数几百、arXiv/RSS 根本没有热度。
   如果直接按数字大小排，结果会全是 GitHub 仓库。
   所以先把热度换算成「**本榜内百分位**」——只比"在同类源里排第几"，不比绝对值。

2. **候选池按源轮转取**：
   如果只按总分取前 30，大源（arXiv 40 条）会把小源挤没。
   改成按源轮转（round-robin），保证每个源在候选池里都有位置，
   让后面的模型精选看到"全貌"，而不是"GitHub 专场"。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from ..config import Settings
from ..keywords import count_hits
from ..models import Doc

log = logging.getLogger(__name__)

# 来源权重：论文和 HF 日榜的信息密度更高，RSS 里广告/软文比例更高
SOURCE_WEIGHT: dict[str, float] = {
    "huggingface": 1.2,
    "hf_models": 1.2,
    "arxiv": 1.0,
    "github": 0.9,
    "hackernews": 0.9,
    "reddit": 0.8,
    "rss": 0.7,
}


def annotate_heat(docs: list[Doc]) -> list[Doc]:
    """按来源分组，算出「本榜内排名」与百分位（1.0 = 本源最热）。

    这就是解决"全是 GitHub"的关键：star 5764 与 HN 1070 不再直接比大小，
    而是各自换算成"在本源里排第几"。
    """
    groups: dict[str, list[Doc]] = defaultdict(list)
    for doc in docs:
        groups[doc.source].append(doc)

    for items in groups.values():
        ordered = sorted(items, key=lambda d: d.heat, reverse=True)
        count = len(ordered)
        for index, doc in enumerate(ordered):
            doc.heat_rank = index + 1
            # 单条时给 1.0，避免除零
            doc.heat_pct = 1.0 - (index / (count - 1)) if count > 1 else 1.0
    return docs


def heuristic_score(doc: Doc, now: datetime | None = None) -> float:
    """规则打分（越高越优先）。全部是免费信号，不需要调模型。"""
    now = now or datetime.now(timezone.utc)

    # 1. 关键词命中数：AI 味越浓越优先（封顶 10 个，避免长文占便宜）
    score = min(count_hits(doc.title, doc.summary_raw[:300]), 10) * 1.0

    # 2. 来源权重
    score += SOURCE_WEIGHT.get(doc.source, 0.7) * 2.0

    # 3. 热度：用「榜内百分位」而不是原始数字，否则 GitHub 的 star 会压倒一切
    if doc.heat > 0:
        score += 3.0 * doc.heat_pct

    # 4. 新鲜度：24 小时内加 2 分，3 天以上减 1 分
    if doc.published_at:
        published = doc.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_hours = (now - published).total_seconds() / 3600
        if age_hours <= 24:
            score += 2.0
        elif age_hours > 72:
            score -= 1.0

    # 5. 摘要太短的，信息量通常不够
    if len(doc.summary_raw) < 80:
        score -= 1.0

    return round(score, 2)


def _balanced_pick(docs: list[Doc], limit: int) -> list[Doc]:
    """按源轮转取候选：每个源挑自己榜内最好的，轮流放到名额用完。"""
    groups: dict[str, list[Doc]] = defaultdict(list)
    for doc in docs:
        groups[doc.source].append(doc)
    for items in groups.values():
        items.sort(key=lambda d: heuristic_score(d), reverse=True)

    # 大源先起手，保证名额分配更均匀
    order = sorted(groups, key=lambda s: len(groups[s]), reverse=True)
    picked: list[Doc] = []
    cursor = {source: 0 for source in groups}

    while len(picked) < limit:
        progressed = False
        for source in order:
            if len(picked) >= limit:
                break
            idx = cursor[source]
            if idx < len(groups[source]):
                picked.append(groups[source][idx])
                cursor[source] = idx + 1
                progressed = True
        if not progressed:  # 所有源都取完了
            break
    return picked


def prerank(docs: list[Doc], settings: Settings) -> list[Doc]:
    """归一化热度 → 按源轮转取候选 → 按规则分排序。"""
    if not docs:
        return []
    annotate_heat(docs)
    limit = settings.max_candidates

    if limit <= 0 or len(docs) <= limit:
        ranked = sorted(docs, key=lambda d: heuristic_score(d), reverse=True)
        log.info("预筛：%d 条全部送模型（上限 %d）", len(ranked), limit)
        return ranked

    picked = _balanced_pick(docs, limit)
    picked.sort(key=lambda d: heuristic_score(d), reverse=True)

    per_source = defaultdict(int)
    for doc in picked:
        per_source[doc.source] += 1
    log.info(
        "预筛：%d 条 → 送模型 %d 条（%s）",
        len(docs),
        len(picked),
        " / ".join(f"{k}:{v}" for k, v in sorted(per_source.items())),
    )
    return picked
