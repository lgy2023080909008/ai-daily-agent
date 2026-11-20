"""日报渲染：把结构化数据变成可直接读的 Markdown。

选 Markdown 而不是 HTML：企业微信/飞书/邮件都能直接吃，推到 GitHub 也能预览。
"""

from __future__ import annotations

from ..models import Digest

SOURCE_LABEL = {
    "arxiv": "arXiv",
    "huggingface": "HF Daily",
    "github": "GitHub",
    "rss": "资讯",
}


def _fmt_source(doc) -> str:
    return SOURCE_LABEL.get(doc.source, doc.source)


def _fmt_heat(doc) -> str:
    if doc.heat_label:
        return doc.heat_label
    if doc.heat:
        return str(doc.heat)
    return ""


def render_markdown(digest: Digest, max_items: int | None = None) -> str:
    items = digest.items[:max_items] if max_items else digest.items
    lines: list[str] = [f"# AI 技术前沿日报 · {digest.date}", ""]

    stats = digest.stats
    if stats:
        lines.append(
            "> 抓取 {fetched} 条 · 新增 {new} 条 · 去重后 {deduped} 条 · "
            "候选 {candidates} 条 · 精选 {selected} 条".format(
                fetched=stats.get("fetched", "-"),
                new=stats.get("new", "-"),
                deduped=stats.get("deduped", "-"),
                candidates=stats.get("candidates", "-"),
                selected=stats.get("selected", "-"),
            )
        )
        lines.append("")

    if not items:
        lines.append("今天没有通过筛选的新内容。")
        lines.append("")

    for index, item in enumerate(items, 1):
        doc = item.doc
        heat = _fmt_heat(doc)
        meta = [f"**{_fmt_source(doc)}**"]
        if heat:
            meta.append(f"热度 {heat}")
        meta.append(f"[原文]({doc.url})")
        lines.append(f"## {index}. {doc.title}")
        lines.append("")
        lines.append(" ｜ ".join(meta))
        lines.append("")
        if item.reason:
            lines.append(f"**为什么选它**：{item.reason}")
            lines.append("")
        if item.summary_zh:
            lines.append(f"**摘要**：{item.summary_zh}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("由 [ai-daily-agent](https://github.com/) 自动生成：抓取 → 去重 → 预筛 → 精选 → 摘要 → 推送。")
    lines.append("")
    return "\n".join(lines)


def render_brief(digest: Digest, limit: int = 5) -> str:
    """纯文本摘要，用于命令行快速预览。"""
    out = [f"[{digest.date}] 共 {len(digest.items)} 条"]
    for item in digest.items[:limit]:
        heat = _fmt_heat(item.doc)
        suffix = f"  {heat}" if heat else ""
        out.append(f"  {item.rank}. {item.doc.title[:52]}{suffix}")
    return "\n".join(out)
