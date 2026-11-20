"""终端标注工具：一条条按 1/0，自动保存，随时退出续标。

用法：
    python -m eval.label_tool              # 从 eval/labeled.csv 里挑未标的逐条过
    python -m eval.label_tool --limit 50   # 这次只标 50 条

判定标准只有一个问题：
    「如果今天的日报里只有这一条，我会觉得有用吗？」
    会 = 1，不会 = 0。别想太久，5 秒一条，凭第一反应。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eval.labeling import is_labeled, load_rows, pending, save_rows, stats

HELP = "1 = 值得   0 = 不值得   s = 跳过   q = 保存并退出"


def show(row: dict, index: int, total: int) -> None:
    print("=" * 64)
    print(f"[{index}/{total}] 来源：{row.get('source', '?')}")
    print(f"标题：{row.get('title', '')}")
    summary = (row.get("summary") or "").strip()
    if summary:
        print(f"摘要：{summary[:280]}{'…' if len(summary) > 280 else ''}")
    print("-" * 64)
    print(HELP)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="终端交互式标注")
    parser.add_argument("--csv", default="eval/labeled.csv")
    parser.add_argument("--limit", type=int, default=0, help="本次最多标多少条（0=全部）")
    args = parser.parse_args(argv)

    path = Path(args.csv)
    rows = load_rows(path)
    if not rows:
        print(f"{path} 不存在或为空。先运行：python -m eval.export_for_labeling")
        return 1

    todo = pending(rows)
    if not todo:
        print("都标完了。跑评测：python -m eval.run_eval")
        return 0

    print(f"待标注 {len(todo)} 条。随时按 q 退出，进度会自动保存。\n")
    answer_map = {"1": "1", "0": "0", "s": "s", "q": "q"}
    done = 0

    try:
        for index, row in enumerate(todo, start=1):
            if args.limit and done >= args.limit:
                break
            show(row, index, len(todo))
            while True:
                answer = input("> ").strip().lower()
                if answer in answer_map:
                    break
                print("只认 1 / 0 / s / q")

            if answer == "q":
                break
            if answer == "s":
                continue

            row["label"] = answer
            save_rows(path, rows)  # 每条都落盘，崩了也不丢
            done += 1

            s = stats(rows)
            print(f"已标 {s['labeled']}/{s['total']}（正 {s['positive']} / 负 {s['negative']}）\n")
    except KeyboardInterrupt:
        print("\n已中断，进度已保存。")

    s = stats(rows)
    print(f"\n本次标了 {done} 条；累计 {s['labeled']}/{s['total']}，还剩 {s['pending']} 条")
    if s["labeled"]:
        print("跑评测：python -m eval.run_eval --csv " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
