"""离线示例数据：没有网络 / 没有 API key 时，用它把整条链路跑通。

用途有两个：写代码时先验证流程（`python -m aidaily --demo`），以及给 pytest 当固定输入。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import RawDoc

_NOW = datetime.now(timezone.utc)


def sample_raw_docs() -> list[RawDoc]:
    return [
        RawDoc(
            source="arxiv",
            title="AgentBench-X: Evaluating Long-Horizon Tool Use in LLM Agents",
            url="https://arxiv.org/abs/2601.00001",
            summary_raw=(
                "We present a benchmark for long-horizon tool use. Agents must complete "
                "multi-step tasks with 20+ tool calls. Current SOTA models solve 41% of tasks, "
                "with failures concentrated in error recovery and context management."
            ),
            published_at=_NOW - timedelta(hours=6),
            tags=["cs.AI", "cs.CL"],
        ),
        RawDoc(
            source="arxiv",
            title="AgentBench-X: Evaluating Long-Horizon Tool Use in LLM Agents",  # 重复条目
            url="https://arxiv.org/abs/2601.00001v1",
            summary_raw="duplicate entry for dedup test",
            published_at=_NOW - timedelta(hours=5),
            tags=["cs.AI"],
        ),
        RawDoc(
            source="huggingface",
            title="OpenReasoner-7B: Open-Source Reasoning Model with Verifier-Guided Decoding",
            url="https://huggingface.co/papers/2601.00002",
            summary_raw=(
                "An open reasoning model trained with verifier-guided decoding. "
                "Reports SOTA on math benchmarks at 7B scale, with full training recipe released."
            ),
            published_at=_NOW - timedelta(hours=10),
            tags=["paper"],
            heat=128,
            heat_label="128 赞",
        ),
        RawDoc(
            source="github",
            title="acme/agent-flow（★1280）",
            url="https://github.com/acme/agent-flow",
            summary_raw="A minimal framework for building tool-using agents with tracing.\n语言：Python",
            published_at=None,
            tags=["agent", "llm"],
            heat=1280,
            heat_label="★1280",
        ),
        RawDoc(
            source="jiqizhixin.com",
            title="某厂商发布新一代多模态大模型，推理成本下降 40%",
            url="https://www.jiqizhixin.com/articles/example",
            summary_raw="该模型在视觉问答与文档理解任务上表现提升，官方称推理成本下降 40%。",
            published_at=_NOW - timedelta(hours=3),
            tags=["jiqizhixin.com"],
        ),
    ]
