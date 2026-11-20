"""预筛的测试：这一层决定了送进模型的候选量，规则一变就要有测试兜住。

重点覆盖两个曾经踩过的坑：
1. GitHub 的 star 数字远大于 HN / HF，直接比大小会让候选全是 GitHub；
2. 大源（arXiv 40 条）会把小源挤没，候选池要按源轮转分配名额。
"""

from datetime import datetime, timedelta, timezone

from aidaily.models import Doc, RawDoc
from aidaily.pipeline.prerank import annotate_heat, heuristic_score, prerank


def _doc(title: str, source: str = "arxiv", summary: str = "x" * 120,
         hours_ago: float | None = 2, heat: int = 0) -> Doc:
    published = (
        datetime.now(timezone.utc) - timedelta(hours=hours_ago) if hours_ago is not None else None
    )
    return Doc.from_raw(
        RawDoc(source=source, title=title, url=f"https://e.com/{title}", summary_raw=summary,
               published_at=published, heat=heat)
    )


def test_fresh_ai_paper_beats_old_generic_news():
    fresh_paper = _doc("A New Method for LLM Reasoning", source="arxiv", hours_ago=1)
    old_news = _doc("某公司的年会报道", source="rss", summary="公司年会", hours_ago=200)
    assert heuristic_score(fresh_paper) > heuristic_score(old_news)


def test_short_summary_penalized():
    long_doc = _doc("大模型推理加速综述", summary="y" * 200)
    short_doc = _doc("大模型推理加速综述", summary="短")
    assert heuristic_score(long_doc) > heuristic_score(short_doc)


# ---------------------------------------------------------------- 热度归一化
def test_heat_rank_and_pct_within_source():
    docs = [
        _doc("hot", source="github", heat=5000, hours_ago=None),
        _doc("mid", source="github", heat=500, hours_ago=None),
        _doc("cold", source="github", heat=5, hours_ago=None),
    ]
    annotate_heat(docs)
    by_title = {d.title: d for d in docs}
    assert by_title["hot"].heat_rank == 1 and by_title["hot"].heat_pct == 1.0
    assert by_title["cold"].heat_rank == 3 and by_title["cold"].heat_pct == 0.0


def test_cross_source_heat_is_comparable_by_percentile():
    """star 5764 的 GitHub 与 1070 分的 HN 都是各自榜第一，评分不应被 star 数字碾压。"""
    github_top = _doc("acme/hot-agent", source="github", heat=5764, hours_ago=None)
    hn_top = _doc("Anthropic IPO", source="hackernews", heat=1070, hours_ago=None)
    annotate_heat([github_top, hn_top])
    assert github_top.heat_pct == 1.0 and hn_top.heat_pct == 1.0
    # 两者都被视为"本榜最热"，规则分差距只来自来源权重
    assert abs(heuristic_score(github_top) - heuristic_score(hn_top)) < 1.0


# ---------------------------------------------------------------- 候选池配额
def test_prerank_truncates_to_limit(settings):
    settings.max_candidates = 3
    docs = [_doc(f"LLM agent 研究 {i}") for i in range(10)]
    assert len(prerank(docs, settings)) == 3


def test_prerank_keeps_all_when_under_limit(settings):
    settings.max_candidates = 20
    docs = [_doc(f"LLM agent 研究 {i}") for i in range(5)]
    assert len(prerank(docs, settings)) == 5


def test_prerank_zero_means_no_limit(settings):
    settings.max_candidates = 0
    docs = [_doc(f"LLM agent 研究 {i}") for i in range(30)]
    assert len(prerank(docs, settings)) == 30


def test_prerank_balances_sources(settings):
    """40 条 arXiv 不能把小源的候选位挤没。"""
    settings.max_candidates = 8
    docs = [_doc(f"论文 {i}", source="arxiv", heat=0) for i in range(40)]
    docs += [_doc(f"repo {i}", source="github", heat=1000 - i, hours_ago=None) for i in range(3)]
    docs += [_doc(f"新闻 {i}", source="rss", hours_ago=1) for i in range(3)]

    picked = prerank(docs, settings)
    sources = {d.source for d in picked}
    assert len(picked) == 8
    assert "github" in sources and "rss" in sources  # 小源也有位置


def test_prerank_sorted_desc(settings):
    settings.max_candidates = 10
    docs = [
        _doc("某公司年会报道", source="rss", summary="年会", hours_ago=300),
        _doc("New SOTA on reasoning benchmarks", source="arxiv", hours_ago=1),
    ]
    assert "SOTA" in prerank(docs, settings)[0].title
