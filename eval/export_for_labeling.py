"""从数据库导出待标注清单。

用法：
    python -m eval.export_for_labeling                # 默认从 data/aidaily.db 补 50 条到 eval/labeled.csv
    python -m eval.export_for_labeling --add 300      # 一次补 300 条
    python -m eval.export_for_labeling --db data/demo.db --out eval/labeled_demo.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aidaily.db import Store
from eval.labeling import load_rows, merge_pending, save_rows, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出待标注清单")
    parser.add_argument("--db", default="data/aidaily.db", help="SQLite 路径")
    parser.add_argument("--out", default="eval/labeled.csv", help="标注集路径")
    parser.add_argument("--add", type=int, default=50, help="本次最多补充多少条")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在：{db_path}")
        print("先跑一次抓取（python -m aidaily --demo 或 python -m aidaily），或者用 --db 指定其它库。")
        return 1

    store = Store(db_path)
    docs = store.list_docs(limit=args.add * 4)
    if not docs:
        print("库里还没有内容，先跑一次 python -m aidaily")
        return 1

    existing = load_rows(args.out)
    merged, added = merge_pending(existing, docs, limit=args.add)
    save_rows(args.out, merged)

    s = stats(merged)
    print(f"从 {db_path} 读取 {len(docs)} 条，本次新增 {added} 条")
    print(f"标注集 {args.out}：共 {s['total']} 条，已标 {s['labeled']}，待标 {s['pending']}")
    if s["pending"]:
        print("\n下一步：python -m eval.label_tool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
