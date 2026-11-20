"""精选：让模型直接从候选里挑出「最值得看的 N 条」并排序。

为什么不用「逐条打 1-5 分再按分数排」：
实测同一个候选集，模型做绝对评分时倾向于给每条都打 4 分（慷慨但没用），
做相对排序时判断明显更准。加上人气数字（star / 点赞）作为客观旁证，
一次调用就能定出 Top N，也不用再维护阈值。

鲁棒性：
- 模型返回的 index 越界 / 重复 / 数量不足 → 用启发式排序补齐；
- 整个调用失败 → 直接退回启发式排序（按热度 + 新鲜度），保证日报还能出。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import Settings
from ..llm import LLMClient
from ..models import Doc, DigestItem, RankResult

log = logging.getLogger(__name__)

SELECT_SYSTEM = """你是一名 AI 技术资讯编辑。读者是准备 AI 方向技术面试的本科生 / 初级工程师，
每天只有 10 分钟，只想知道「今天最值得知道的几条」。

任务：从候选列表里挑出最值得看的 {n} 条，并按值得程度从高到低排序。

挑选标准（按优先级）：
1. 与 AI 技术前沿的相关程度：新模型 / 开源权重 / 算力与芯片 / 有 benchmark 数字的进展 / 可借鉴的工程实践；
2. 热度：候选里给了各源的榜内热度（GitHub star、Hacker News 分数、HF 点赞）。
   注意：**不同来源的数字不可直接比较**，请按「本榜第几热」理解，
   不要因为 star 数字大就优先——arXiv 和资讯源本身没有热度数据；
3. 信息量：有具体方法、数据、结论的优先；只有宣传没有内容的不要。

多样性要求：不要 5 条全是同一个来源，**同一来源最多 2 条**；
某个源今天确实没有值得看的，可以不选它。

直接排除：硬件参数堆砌、融资与人事变动、课程与招聘广告、纯转载的旧闻、促销软文。

只输出一个 JSON 对象，不要任何解释文字：
{"picks": [{"index": 3, "reason": "开源权重发布 + benchmark 提升，热度 1200★"}, ...]}

要求：
- 正好 {n} 条，按推荐顺序排列；
- index 必须是候选列表里的编号，不要编造；
- reason 用中文，说清「为什么是它」，30 字以内。
"""

CANDIDATE_TMPL = """[{index}] 来源：{source} ｜ 热度：{heat}
标题：{title}
摘要：{summary}
"""


def _heat_text(doc: Doc) -> str:
    """给模型看的热度描述：把原始数字换成「本榜第几」，避免跨源比大小。"""
    if doc.heat and doc.heat_rank:
        label = doc.heat_label or str(doc.heat)
        return f"{label}（本榜第 {doc.heat_rank} 热）"
    return doc.heat_label or "无热度数据"


def build_candidates_prompt(docs: list[Doc]) -> str:
    blocks = []
    for index, doc in enumerate(docs, start=1):
        blocks.append(
            CANDIDATE_TMPL.format(
                index=index,
                source=doc.source,
                heat=_heat_text(doc),
                title=doc.title,
                summary=(doc.summary_raw or "（无摘要）")[:350],
            )
        )
    return "\n".join(blocks)


def heuristic_order(docs: list[Doc]) -> list[Doc]:
    """纯规则排序：热度为主，其次新鲜度。模型不可用时的兜底。"""
    now = datetime.now(timezone.utc)

    def key(doc: Doc) -> tuple[float, float]:
        heat = min(doc.heat, 5000) / 1000.0
        freshness = 0.0
        if doc.published_at:
            published = doc.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            hours = (now - published).total_seconds() / 3600
            freshness = max(0.0, 2.0 - hours / 24.0)
        return (heat, freshness)

    return sorted(docs, key=key, reverse=True)


def select_top(
    client: LLMClient,
    docs: list[Doc],
    settings: Settings,
    n: int | None = None,
) -> tuple[list[DigestItem], bool]:
    """返回 (按推荐顺序排好的条目, 是否退回了规则兜底)。"""
    if not docs:
        return [], False
    limit = min(n or settings.top_n, len(docs))

    picks = []
    model_failed = False
    try:
        result = client.json(
            SELECT_SYSTEM.replace("{n}", str(limit)),
            build_candidates_prompt(docs),
            RankResult,
        )
        picks = result.picks
    except Exception as exc:  # noqa: BLE001 - 选不出来也要出报
        log.warning("模型精选失败（%s），改用热度启发式排序", exc)
        model_failed = True

    # 校验并去重：index 从 1 开始，越界直接丢弃
    chosen: list[tuple[Doc, str]] = []
    seen: set[int] = set()
    for pick in picks:
        idx = pick.index - 1
        if idx < 0 or idx >= len(docs) or idx in seen:
            continue
        seen.add(idx)
        chosen.append((docs[idx], pick.reason))

    if not chosen:
        model_failed = True

    # 数量不足就用启发式补齐（不重复）
    if len(chosen) < limit:
        have_ids = {doc.id for doc, _ in chosen}
        for doc in heuristic_order(docs):
            if len(chosen) >= limit:
                break
            if doc.id in have_ids:
                continue
            chosen.append((doc, "按热度与新鲜度补位"))

    items = [
        DigestItem(doc=doc, rank=rank, reason=reason)
        for rank, (doc, reason) in enumerate(chosen[:limit], start=1)
    ]
    log.info("精选 %d 条：%s", len(items), " / ".join(i.doc.title[:18] for i in items))
    return items, model_failed
