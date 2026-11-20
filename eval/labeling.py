"""标注集的读写与合并。

标注集是整个项目里唯一"人工产生"的数据，格式必须稳定：
    source,title,summary,label,url
    （label：1=值得进日报，0=不值得，留空=还没标）
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["source", "title", "summary", "label", "url"]
VALID_LABELS = {"0", "1"}
MAX_SUMMARY = 600


_IGNORE = set(" \t\r\n：:，,。.！!？?\"'“”‘’（）()【】[]《》<>·-—_/\\|+*")

def normalize_title(title: str) -> str:
    """标题归一化，用于判断"这条是不是已经标过"。"""
    return "".join(ch.lower() for ch in (title or "") if ch not in _IGNORE).strip()


def load_rows(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [
            {k: (row.get(k) or "") for k in FIELDS}
            for row in csv.DictReader(f)
        ]


def save_rows(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def is_labeled(row: dict) -> bool:
    return str(row.get("label", "")).strip() in VALID_LABELS


def pending(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not is_labeled(r)]


def stats(rows: list[dict]) -> dict[str, int]:
    labeled = sum(1 for r in rows if is_labeled(r))
    positives = sum(1 for r in rows if str(r.get("label", "")).strip() == "1")
    return {
        "total": len(rows),
        "labeled": labeled,
        "pending": len(rows) - labeled,
        "positive": positives,
        "negative": labeled - positives,
    }


def doc_to_row(doc: dict) -> dict:
    """把数据库里的一条记录转成标注行（label 留空，等人来填）。"""
    summary = " ".join(str(doc.get("summary_raw") or "").split())[:MAX_SUMMARY]
    return {
        "source": doc.get("source") or "",
        "title": " ".join(str(doc.get("title") or "").split()),
        "summary": summary,
        "label": "",
        "url": doc.get("url") or "",
    }


def merge_pending(
    existing: list[dict], docs: list[dict], limit: int
) -> tuple[list[dict], int]:
    """把数据库里的新内容追加到标注集，返回 (合并后的行, 新增条数)。

    已经在集合里的标题跳过；limit 表示"最多补充多少条"。
    """
    known = {normalize_title(r["title"]) for r in existing}
    fresh_rows: list[dict] = []
    for doc in docs:
        row = doc_to_row(doc)
        if not row["title"]:
            continue
        key = normalize_title(row["title"])
        if key in known:
            continue
        known.add(key)
        fresh_rows.append(row)
        if len(fresh_rows) >= limit:
            break
    return existing + fresh_rows, len(fresh_rows)
