"""命令行入口：

    python -m aidaily                    正常跑一次（抓取 + 精选 + 推送）
    python -m aidaily --dry-run          只跑不推
    python -m aidaily --demo             用内置示例数据跑（不联网）
    python -m aidaily --check            自检：打印生效配置并试调一次模型
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings, load_settings
from .llm import build_llm_client
from .main import run_once
from .pipeline.render import render_brief


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidaily", description="AI 技术前沿资讯与日报 Agent"
    )
    parser.add_argument("--top", type=int, default=None, help="推送条数，默认读配置 TOP_N（5）")
    parser.add_argument("--max-candidates", type=int, default=None, help="送模型挑选的候选条数")
    parser.add_argument("--sources", default=None, help="临时指定数据源，逗号分隔，如 arxiv,hackernews")
    parser.add_argument("--dry-run", action="store_true", help="只跑流程，不推送、不标记已推")
    parser.add_argument("--demo", action="store_true", help="用内置示例数据跑，不联网")
    parser.add_argument("--check", action="store_true", help="自检：打印配置并试调一次模型")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    return parser


def _mask(value: str) -> str:
    if not value:
        return "（空）"
    return value[:6] + "***" + value[-2:] if len(value) > 10 else "***"


def run_check(settings: Settings) -> int:
    """自检：把程序实际读到的配置打出来，再真调一次模型。"""
    env_path = Path(".env").resolve()
    print("=" * 56)
    print("配置自检")
    print("=" * 56)
    print(f"工作目录      : {Path.cwd()}")
    print(f".env 路径     : {env_path}")
    print(f".env 是否存在 : {env_path.exists()}")
    print(f"LLM_BACKEND   : {settings.llm_backend}")
    print(f"LLM_BASE_URL  : {settings.llm_base_url}")
    print(f"LLM_MODEL     : {settings.llm_model}")
    print(f"LLM_API_KEY   : {_mask(settings.llm_api_key)}")
    print(f"TOP_N         : {settings.top_n}")
    print(f"最大候选数    : {settings.max_candidates}")
    print(f"数据源        : {', '.join(settings.source_list)}")
    print(f"NOTIFY_CHANNEL: {settings.notify_channel}")
    print(f"DB_PATH       : {settings.db_path}")
    print("-" * 56)

    if not settings.llm_enabled:
        print("结论：没有读到 LLM_API_KEY，当前会是 mock 模式。")
        print("检查 .env 是否就在上面这个路径，且没有写成 .env.example。")
        return 1

    client = build_llm_client(settings)
    from .models import RankResult

    try:
        result = client.json(
            "你是一个测试助手，只输出 JSON，不要解释。",
            '[1] 来源：test ｜ 热度：无\n标题：连通性测试\n摘要：这是一次连通性测试。\n\n'
            '请只输出 {"picks": [{"index": 1, "reason": "测试"}]}',
            RankResult,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"模型调用失败：{type(exc).__name__}: {exc}")
        if client.switched:
            print("（已尝试自动切换到 HTTP 后端，但仍失败，通常是 key / base_url / 网络问题）")
        else:
            print("建议：在 .env 里加一行 LLM_BACKEND=http 再试。")
        return 1

    print(f"模型调用成功：backend={client.backend}，返回 {len(result.picks)} 条 picks")
    if client.switched:
        print("注意：本次是从 langchain 自动降级到 HTTP 后端的（SDK 版本不兼容）。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    settings = load_settings()
    if args.max_candidates is not None:
        settings = settings.model_copy(update={"max_candidates": args.max_candidates})
    if args.sources:
        settings = settings.model_copy(update={"sources": args.sources})

    if args.check:
        return run_check(settings)

    client = build_llm_client(settings)
    if client.offline:
        print("[提示] 未配置 LLM_API_KEY，当前为离线 mock 模式，精选结果仅用于验证链路。")

    raw_docs = None
    if args.demo:
        from .samples import sample_raw_docs

        raw_docs = sample_raw_docs()
        # demo 用独立数据库，避免把示例数据写进真实库、导致以后真的抓不到同样的标题
        settings = settings.model_copy(update={"db_path": "data/demo.db"})
        print(f"[demo] 使用内置示例数据 {len(raw_docs)} 条（写入 data/demo.db，不影响正式库）")

    try:
        digest = run_once(
            settings, client=client, raw_docs=raw_docs, dry_run=args.dry_run, top_n=args.top
        )
    except RuntimeError as exc:
        print(f"\n[运行失败] {exc}\n")
        return 1

    print()
    print(render_brief(digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
