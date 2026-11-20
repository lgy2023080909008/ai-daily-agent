"""评测：衡量「模型挑出来的 TOP_N 条里，有几条是你认为值得看的」。

和旧版的区别：不再逐条打 1-5 分再比阈值，而是直接评测"精选结果"——
因为线上流程就是"从候选里挑 N 条"，评测口径应该和线上一致。

用法：
    python -m eval.run_eval              # 用 eval/labeled.csv（需要 LLM_API_KEY）
    python -m eval.run_eval --mock       # 不调真实模型，验证脚本能跑
    python -m eval.run_eval --limit 40   # 只用前 40 条已标注样本
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aidaily.config import load_settings  # noqa: E402
from aidaily.llm import LLMClient, build_llm_client  # noqa: E402
from aidaily.models import Doc, RawDoc  # noqa: E402
from aidaily.pipeline.select import select_top  # noqa: E402
from eval.labeling import is_labeled, load_rows, stats  # noqa: E402

RESULT_DIR = Path(__file__).resolve().parent / "results"


def to_doc(row: dict) -> Doc:
    return Doc.from_raw(
        RawDoc(
            source=row.get("source") or "labeled",
            title=row["title"],
            url=row.get("url") or f"https://example.com/{abs(hash(row['title']))}",
            summary_raw=row.get("summary") or "",
        )
    )


def evaluate(client: LLMClient, rows: list[dict], settings, top_n: int) -> dict:
    docs = [to_doc(row) for row in rows]
    label_by_id = {doc.id: int(row.get("label") or 0) for row, doc in zip(rows, docs)}

    items, failed = select_top(client, docs, settings, n=top_n)
    picked = [label_by_id.get(item.doc.id, 0) for item in items]
    positives = sum(label_by_id.values())

    precision = sum(picked) / max(len(picked), 1)
    recall = sum(picked) / positives if positives else 0.0
    baseline = positives / max(len(rows), 1)   # 随机挑的期望精确率

    return {
        "样本数": len(rows),
        "正样本": positives,
        "正样本占比": round(baseline, 3),
        "精选条数": len(items),
        "命中正样本": sum(picked),
        "precision@N": round(precision, 3),
        "recall@N": round(recall, 3),
        "比随机好多少": round(precision - baseline, 3),
        "模型是否降级": failed,
        "命中列表": [
            {"rank": item.rank, "title": item.doc.title, "label": label_by_id.get(item.doc.id, 0)}
            for item in items
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="精选效果评测")
    parser.add_argument("--csv", default=str(Path(__file__).resolve().parent / "labeled.csv"))
    parser.add_argument("--top", type=int, default=None, help="精选几条，默认读 TOP_N")
    parser.add_argument("--limit", type=int, default=0, help="只用前 N 条已标注样本（0=全部）")
    parser.add_argument("--mock", action="store_true", help="不调用真实模型")
    args = parser.parse_args(argv)

    settings = load_settings()
    client = LLMClient(None) if args.mock else build_llm_client(settings)

    all_rows = load_rows(Path(args.csv))
    rows = [r for r in all_rows if is_labeled(r)]
    progress = stats(all_rows)
    if progress["pending"]:
        print(f"[提示] 标注集共 {progress['total']} 条，其中 {progress['pending']} 条未标注，本次只评测已标的。")
    if not rows:
        print(f"没有已标注的样本：{args.csv}")
        return 1
    if args.limit:
        rows = rows[: args.limit]

    top_n = args.top or settings.top_n
    result = evaluate(client, rows, settings, top_n)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    (RESULT_DIR / "latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# 精选效果评测",
        "",
        f"- 数据：`{Path(args.csv).name}`",
        f"- 模式：{'mock' if args.mock else settings.llm_model}",
        f"- 精选条数：{result['精选条数']}",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
    ]
    for key in ("样本数", "正样本", "正样本占比", "精选条数", "命中正样本",
                "precision@N", "recall@N", "比随机好多少", "模型是否降级"):
        lines.append(f"| {key} | {result[key]} |")
    lines += ["", "## 本次精选命中情况", "", "| # | 内容 | 你的标注 |", "| --- | --- | --- |"]
    for entry in result["命中列表"]:
        mark = "✅ 值得" if entry["label"] == 1 else "❌ 不值得"
        lines.append(f"| {entry['rank']} | {entry['title'][:50]} | {mark} |")

    (RESULT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
