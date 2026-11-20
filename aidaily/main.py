"""主流程：抓取 → 规范化 → 入库去重 → 近重复 → 预筛 → 模型精选 → 摘要 → 推送。

每个环节都可以单独替换：
- 换数据源 → 加一个 Fetcher
- 换模型 → 改 .env
- 换推送渠道 → 加一个 Notifier
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .db import Store
from .fetchers import fetch_all
from .llm import LLMClient, build_llm_client
from .models import Digest, Doc, RawDoc
from .notifiers import build_notifier
from .pipeline.dedup import Deduper
from .pipeline.prerank import prerank
from .pipeline.render import render_markdown
from .pipeline.select import select_top
from .pipeline.summarize import summarize_doc

log = logging.getLogger(__name__)


def normalize(raw_docs: list[RawDoc], settings: Settings) -> list[Doc]:
    """RawDoc → Doc，并做时间窗过滤（论文给 2 倍窗口，避免周末没更新）。"""
    now = datetime.now(timezone.utc)
    docs: list[Doc] = []
    seen: set[str] = set()
    for raw in raw_docs:
        doc = Doc.from_raw(raw)
        if doc.id in seen:
            continue
        if settings.lookback_hours > 0 and doc.published_at:
            published = doc.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age_hours = (now - published).total_seconds() / 3600
            if age_hours > settings.lookback_hours * 2:
                continue
        seen.add(doc.id)
        docs.append(doc)
    return docs


def run_once(
    settings: Settings,
    *,
    client: LLMClient | None = None,
    raw_docs: list[RawDoc] | None = None,
    store: Store | None = None,
    dry_run: bool = False,
    top_n: int | None = None,
) -> Digest:
    """跑一次日报。raw_docs / client / store 可注入，便于测试与离线演示。"""
    started = time.time()
    date_str = datetime.now().strftime("%Y-%m-%d")
    client = client or build_llm_client(settings)
    store = store or Store(settings.db_path)
    limit = top_n or settings.top_n

    # 1. 抓取
    raw = raw_docs if raw_docs is not None else fetch_all(settings)
    docs = normalize(raw, settings)
    log.info("抓取 %d 条 → 规范化后 %d 条", len(raw), len(docs))

    # 2. 入库（add_doc 返回 True 表示库里没有过），顺便过滤掉推过的
    fresh: list[Doc] = []
    for doc in docs:
        if store.add_doc(doc) and not store.is_pushed(doc.id):
            fresh.append(doc)
    log.info("其中新内容 %d 条", len(fresh))

    # 3. 去重
    dedup = Deduper(settings).filter(fresh)

    try:
        # 3.5 预筛：规则排序砍到 max_candidates 条
        candidates = prerank(dedup.kept, settings)

        # 4. 模型精选：直接从候选里挑出最值得看的 N 条并排序
        items, used_fallback = select_top(client, candidates, settings, n=limit)

        # 模型调用失败却默默用规则兜底 = 配置有问题，宁可不发也不要发一份没人挑过的日报
        if used_fallback and not client.offline:
            raise RuntimeError(
                "模型精选失败，已退回规则兜底，本次不推送。请检查 LLM 配置：\n"
                "  LLM_API_KEY / LLM_BASE_URL / LLM_MODEL\n"
                f"  当前后端：{client.backend}\n"
                "  先跑 python -m aidaily --check 看配置"
            )
    except RuntimeError:
        # 回滚这一轮新入库的条目，否则这批内容会被当成"抓过了"，明天再也进不来
        store.delete_docs([doc.id for doc in fresh])
        log.error("本轮失败，已回滚 %d 条新入库内容，下次运行会重新抓取", len(fresh))
        raise

    # 5. 摘要（只对入选的几条做，成本可控）
    for item in items:
        summary = summarize_doc(client, item.doc, item.reason)
        item.summary_zh = summary.summary_zh
        item.why = summary.why

    digest = Digest(
        date=date_str,
        items=items,
        stats={
            "fetched": len(raw),
            "normalized": len(docs),
            "new": len(fresh),
            "deduped": len(dedup.kept),
            "dropped_duplicates": dedup.dropped_count,
            "candidates": len(candidates),
            "selected": len(items),
            "llm": "offline-mock" if client.offline else f"{client.backend}:{settings.llm_model}",
            "elapsed_s": round(time.time() - started, 1),
        },
    )
    digest.markdown = render_markdown(digest)

    # 6. 落库 + 存档 + 推送
    # 先无条件把 Markdown 存一份到本地：不管推送用什么渠道（邮件/飞书/…），
    # 都应该能在磁盘上找到"今天到底发了什么"，否则线上排查只能靠猜。
    if not dry_run:
        out_dir = Path(settings.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        digest_path = out_dir / f"{date_str}.md"
        digest_path.write_text(digest.markdown, encoding="utf-8")
        log.info("日报已存档：%s", digest_path)

        for item in items:
            store.save_item(item, date_str)
        notifier = build_notifier(settings)
        ok = notifier.send(f"AI 技术前沿日报 · {date_str}", digest.markdown)
        if ok:
            store.mark_pushed([item.doc.id for item in items], date_str)
            log.info("已标记 %d 条为已推送", len(items))
        else:
            log.warning("推送失败，本次条目不会标记为已推送，明天会重试")

    log.info(
        "完成：抓取 %d / 新增 %d / 去重后 %d / 精选 %d，用时 %.1fs",
        len(raw), len(fresh), len(dedup.kept), len(items), time.time() - started,
    )
    return digest
