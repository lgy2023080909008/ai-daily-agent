"""存储层测试：确保「同一篇不会推两次」，以及老库能自动补列。"""

import pytest

from aidaily.db import Store
from aidaily.models import DigestItem, Doc, RawDoc


def _doc(title="标题", heat=0) -> Doc:
    return Doc.from_raw(
        RawDoc(source="x", title=title, url="https://e.com/1", summary_raw="s", heat=heat)
    )


def test_add_doc_returns_true_only_once(settings):
    store = Store(settings.db_path)
    doc = _doc()
    assert store.add_doc(doc) is True
    assert store.add_doc(doc) is False
    assert store.count() == 1


def test_mark_pushed(settings):
    store = Store(settings.db_path)
    doc = _doc()
    store.add_doc(doc)
    assert store.is_pushed(doc.id) is False
    store.mark_pushed([doc.id], "2026-11-21")
    assert store.is_pushed(doc.id) is True
    assert store.count_pushed() == 1


def test_save_item_persists_selection(settings):
    store = Store(settings.db_path)
    doc = _doc(heat=1280)
    store.add_doc(doc)
    item = DigestItem(doc=doc, rank=1, reason="热度最高", summary_zh="摘要", why="值得看")
    store.save_item(item)
    row = store.recent(1)[0]
    assert row["rank"] == 1
    assert row["heat"] == 1280


def test_delete_docs_rolls_back(settings):
    store = Store(settings.db_path)
    doc = _doc()
    store.add_doc(doc)
    store.delete_docs([doc.id])
    assert store.count() == 0


def test_list_docs_returns_full_fields(settings):
    store = Store(settings.db_path)
    store.add_doc(
        Doc.from_raw(RawDoc(source="arxiv", title="T", url="https://e.com/1", summary_raw="完整摘要"))
    )
    docs = store.list_docs(limit=10)
    assert docs[0]["summary_raw"] == "完整摘要"
    assert docs[0]["url"] == "https://e.com/1"


def test_migration_adds_missing_columns(settings, workdir):
    """模拟老版本库（没有 rank / reason 列），打开时应自动补齐。"""
    import sqlite3

    path = workdir / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE docs (id TEXT PRIMARY KEY, source TEXT, title TEXT, url TEXT, "
        "summary_raw TEXT, published_at TEXT, fetched_at TEXT, created_at TEXT)"
    )
    conn.commit()
    conn.close()

    store = Store(path)
    store.add_doc(_doc())
    assert store.count() == 1
