"""端到端测试：用内置示例数据 + 离线 mock LLM 跑完整条链路，不联网。"""

import pytest

from aidaily.db import Store
from aidaily.llm import LLMClient
from aidaily.main import normalize, run_once
from aidaily.samples import sample_raw_docs


def test_normalize_dedups_identical_raw(settings):
    docs = normalize(sample_raw_docs(), settings)
    # 示例里有一组重复标题，规范化后只应剩一条
    titles = [d.title for d in docs]
    assert len(titles) == len(set(titles))


def test_run_once_end_to_end(settings):
    digest = run_once(
        settings,
        client=LLMClient(None),
        raw_docs=sample_raw_docs(),
        dry_run=True,
    )
    assert digest.date
    assert 0 < len(digest.items) <= settings.top_n
    assert "# AI 技术前沿日报" in digest.markdown
    assert all(item.summary_zh for item in digest.items)
    assert [item.rank for item in digest.items] == list(range(1, len(digest.items) + 1))
    assert digest.stats["fetched"] == len(sample_raw_docs())


def test_top_n_respected(settings):
    digest = run_once(
        settings,
        client=LLMClient(None),
        raw_docs=sample_raw_docs(),
        dry_run=True,
        top_n=2,
    )
    assert len(digest.items) == 2


def test_second_run_does_not_repeat_items(settings):
    """核心业务规则：同一篇内容第二次不能再进日报。"""
    first = run_once(settings, client=LLMClient(None), raw_docs=sample_raw_docs(), dry_run=True)
    assert len(first.items) > 0

    store = Store(settings.db_path)
    store.mark_pushed([item.doc.id for item in first.items], first.date)

    second = run_once(settings, client=LLMClient(None), raw_docs=sample_raw_docs(), dry_run=True)
    assert len(second.items) == 0


def test_dry_run_does_not_write_digest_file(settings, workdir):
    run_once(settings, client=LLMClient(None), raw_docs=sample_raw_docs(), dry_run=True)
    assert not list((workdir / "out").glob("*.md"))


def test_select_failure_raises_and_rolls_back(settings):
    """模型选不出来（且不是离线 mock）时要报错，并把这一轮入库的条目回滚。"""

    class BrokenClient:
        offline = False
        backend = "broken"
        switched = False

        def json(self, system, user, schema):
            raise TypeError("process() takes no keyword arguments")

    with pytest.raises(RuntimeError, match="精选失败"):
        run_once(settings, client=BrokenClient(), raw_docs=sample_raw_docs(), dry_run=True)

    assert Store(settings.db_path).count() == 0
