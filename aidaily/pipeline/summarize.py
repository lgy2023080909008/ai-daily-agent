"""摘要生成：给入选的每条内容写「中文一句话摘要」+「为什么值得看」。

为什么和精选分开调用：
精选要通读几十条候选（输入长、只要编号），摘要只针对入选的 5 条（输入短、输出长）。
拆开之后成本可控，也方便单独调 prompt。
"""

from __future__ import annotations

import logging

from ..llm import LLMClient
from ..models import Doc, SummaryResult

log = logging.getLogger(__name__)

SUMMARY_SYSTEM = """你是一名 AI 技术资讯编辑，读者是准备面试/关注前沿的工程师。
请基于给出的标题和摘要，输出一个 JSON 对象，不要输出任何解释文字：
{"summary_zh": "50字以内中文摘要，说清楚做了什么、有什么新意", "why": "30字以内，说明为什么值得今天花时间看"}
要求：不要照抄英文原文，不要出现"本文""该论文"这类空话，直接给结论。
"""


def summarize_doc(client: LLMClient, doc: Doc, reason: str = "") -> SummaryResult:
    user = (
        f"标题：{doc.title}\n"
        f"来源：{doc.source}\n"
        f"原文摘要：{(doc.summary_raw or '（无）')[:800]}\n"
        + (f"编辑选它的理由：{reason}" if reason else "")
    )
    try:
        return client.json(SUMMARY_SYSTEM, user, SummaryResult)
    except Exception as exc:  # noqa: BLE001
        log.warning("摘要失败（%s）：%s，用标题兜底", doc.title[:30], exc)
        return SummaryResult(summary_zh=doc.title[:50], why="摘要生成失败，已降级为标题")
