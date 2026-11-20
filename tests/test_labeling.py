"""标注工具链的测试：导出、合并、统计。"""

import json

from aidaily.db import Store
from aidaily.models import Doc, RawDoc
from eval.labeling import (
    doc_to_row,
    is_labeled,
    load_rows,
    merge_pending,
    normalize_title,
    pending,
    save_rows,
    stats,
)


def test_save_and_load_roundtrip(workdir):
    path = workdir / "labeled.csv"
    rows = [{"source": "arxiv", "title": "标题 A", "summary": "摘要", "label": "1", "url": "u"}]
    save_rows(path, rows)
    loaded = load_rows(path)
    assert loaded[0]["title"] == "标题 A"
    assert loaded[0]["label"] == "1"


def test_is_labeled_only_accepts_0_and_1():
    assert is_labeled({"label": "1"})
    assert is_labeled({"label": "0"})
    assert not is_labeled({"label": ""})
    assert not is_labeled({"label": "yes"})
    assert not is_labeled({})


def test_pending_and_stats():
    rows = [
        {"title": "a", "label": "1"},
        {"title": "b", "label": "0"},
        {"title": "c", "label": ""},
    ]
    assert len(pending(rows)) == 1
    s = stats(rows)
    assert (s["total"], s["labeled"], s["pending"], s["positive"], s["negative"]) == (3, 2, 1, 1, 1)


def test_merge_skips_known_titles(workdir):
    existing = [{"source": "x", "title": "OpenAI 发布 GPT-6", "summary": "", "label": "1", "url": "u1"}]
    docs = [
        {"source": "arxiv", "title": "openai发布gpt-6", "summary_raw": "重复", "url": "u2"},   # 归一化后重复
        {"source": "arxiv", "title": "新内容", "summary_raw": "新的", "url": "u3"},
    ]
    merged, added = merge_pending(existing, docs, limit=10)
    assert added == 1
    assert len(merged) == 2
    assert merged[1]["title"] == "新内容"


def test_merge_respects_limit():
    docs = [{"title": f"标题{i}", "summary_raw": "s", "url": f"u{i}"} for i in range(10)]
    merged, added = merge_pending([], docs, limit=3)
    assert added == 3
    assert len(merged) == 3


def test_doc_to_row_truncates_and_flattens():
    doc = {"source": "rss", "title": "标题\n换行", "summary_raw": "很长 " * 500, "url": "u"}
    row = doc_to_row(doc)
    assert "\n" not in row["title"]
    assert len(row["summary"]) <= 600
    assert row["label"] == ""


def test_normalize_title_ignores_case_and_punct():
    assert normalize_title("OpenAI：发布 GPT-5！") == normalize_title("openai 发布 gpt5")


def test_store_list_docs_returns_full_fields(settings):
    store = Store(settings.db_path)
    store.add_doc(
        Doc.from_raw(RawDoc(source="arxiv", title="T", url="https://e.com/1", summary_raw="完整摘要"))
    )
    docs = store.list_docs(limit=10)
    assert docs[0]["summary_raw"] == "完整摘要"
    assert docs[0]["url"] == "https://e.com/1"
