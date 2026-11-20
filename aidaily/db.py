"""SQLite 存储：解决"同一篇文章不要推两次"。

只做三件事：入库去重、记录精选结果、标记已推送。
不用 ORM，sqlite3 标准库足够，也方便讲清楚每条 SQL 在干什么。

注意 `_migrate()`：老版本的库没有 rank/reason 这些列，
启动时自动补齐，避免用户升级代码后报 "no such column"。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import DigestItem, Doc

SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS docs (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    summary_raw  TEXT DEFAULT '',
    published_at TEXT,
    fetched_at   TEXT NOT NULL,
    heat         INTEGER DEFAULT 0,
    rank         INTEGER,
    reason       TEXT,
    summary_zh   TEXT,
    why          TEXT,
    digest_date  TEXT,
    created_at   TEXT NOT NULL
);
"""

# 索引放在迁移之后建：老库可能还没有 digest_date 列
SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_docs_digest ON docs(digest_date);
CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(source);
"""

# 老库升级：缺哪列补哪列
MIGRATIONS: dict[str, str] = {
    "heat": "INTEGER DEFAULT 0",
    "rank": "INTEGER",
    "reason": "TEXT",
    "summary_zh": "TEXT",
    "why": "TEXT",
    "digest_date": "TEXT",
}


class Store:
    def __init__(self, db_path: str | Path) -> None:
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_TABLE)
        self._migrate()
        self._conn.executescript(SCHEMA_INDEXES)
        self._conn.commit()

    def _migrate(self) -> None:
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(docs)")}
        for column, ddl in MIGRATIONS.items():
            if column not in existing:
                self._conn.execute(f"ALTER TABLE docs ADD COLUMN {column} {ddl}")

    # ---------------------------------------------------------------- 写入
    def add_doc(self, doc: Doc) -> bool:
        """返回 True 表示库里原本没有（这条是新内容）。"""
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO docs
               (id, source, title, url, summary_raw, published_at, fetched_at, heat, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc.id,
                doc.source,
                doc.title,
                doc.url,
                doc.summary_raw,
                doc.published_at.isoformat() if doc.published_at else None,
                doc.fetched_at.isoformat(),
                doc.heat,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def save_item(self, item: DigestItem, digest_date: str | None = None) -> None:
        self._conn.execute(
            """UPDATE docs SET rank=?, reason=?, summary_zh=?, why=?,
                               digest_date=COALESCE(?, digest_date)
               WHERE id=?""",
            (item.rank, item.reason, item.summary_zh, item.why, digest_date, item.doc.id),
        )
        self._conn.commit()

    def mark_pushed(self, ids: list[str], digest_date: str) -> None:
        self._conn.executemany(
            "UPDATE docs SET digest_date=? WHERE id=?",
            [(digest_date, i) for i in ids],
        )
        self._conn.commit()

    def delete_docs(self, ids: list[str]) -> None:
        """回滚：整轮跑失败时，把这一轮新入库的条目删掉，下次还能重新抓、重新选。

        没有这一步会发生什么：第一天模型挂了 → 内容已入库 → 第二天抓到的都算"见过"，
        这批内容永远进不了日报。
        """
        if not ids:
            return
        self._conn.executemany("DELETE FROM docs WHERE id=?", [(i,) for i in ids])
        self._conn.commit()

    # ---------------------------------------------------------------- 查询
    def is_known(self, doc_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM docs WHERE id=?", (doc_id,)).fetchone()
        return row is not None

    def is_pushed(self, doc_id: str) -> bool:
        row = self._conn.execute(
            "SELECT digest_date FROM docs WHERE id=?", (doc_id,)
        ).fetchone()
        return bool(row and row["digest_date"])

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"])

    def count_pushed(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) AS c FROM docs WHERE digest_date IS NOT NULL"
            ).fetchone()["c"]
        )

    def recent(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            """SELECT id, source, title, heat, rank, digest_date
               FROM docs ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_docs(self, limit: int = 500) -> list[dict]:
        """导出用：返回完整字段（含摘要和链接）。"""
        rows = self._conn.execute(
            """SELECT id, source, title, url, summary_raw, published_at, heat, digest_date
               FROM docs ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
