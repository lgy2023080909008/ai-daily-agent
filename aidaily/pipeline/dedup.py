"""去重：同一篇论文/新闻往往被多个源同时发，重复条目会把日报撑爆。

两层去重：
1. 精确去重：标题算的 id 相同直接合并（同源重复、跨源转载同名的情况）；
2. 近重复去重：字面相似度超过阈值就认为重复（换了个标题的同一新闻）。

默认用字符 bigram 的 Jaccard，零依赖、可解释、对中英文都有效；
配置 DEDUP_MODE=embedding 时改用向量余弦相似度（需要 embeddings 接口）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import Settings
from ..models import Doc

log = logging.getLogger(__name__)

_PUNCT = " \t\r\n，。、；：？！“”‘’（）《》【】,.;:?!\"'()[]{}<>-—_/\\|+*#@&%$^~`"


def normalize(text: str) -> str:
    """去掉标点空白并转小写，只保留可比较的字符。"""
    return "".join(ch.lower() for ch in (text or "") if ch not in _PUNCT)


def bigrams(text: str) -> set[str]:
    norm = normalize(text)
    if len(norm) < 2:
        return {norm} if norm else set()
    return {norm[i : i + 2] for i in range(len(norm) - 1)}


def jaccard(a: str, b: str) -> float:
    sa, sb = bigrams(a), bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similarity(doc_a: Doc, doc_b: Doc, w_title: float = 0.7) -> float:
    """标题占 7 成权重：标题几乎一样的，基本就是同一条。"""
    title_sim = jaccard(doc_a.title, doc_b.title)
    if not doc_a.summary_raw or not doc_b.summary_raw:
        return title_sim
    summary_sim = jaccard(doc_a.summary_raw[:400], doc_b.summary_raw[:400])
    return w_title * title_sim + (1 - w_title) * summary_sim


@dataclass
class DedupResult:
    kept: list[Doc] = field(default_factory=list)
    dropped: list[tuple[str, str, float]] = field(default_factory=list)

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)


class Deduper:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mode = settings.dedup_mode
        self.threshold = settings.dedup_threshold
        self._embedder = None
        if self.mode == "embedding":
            self._embedder = self._try_build_embedder()

    def _try_build_embedder(self):
        """embedding 模式是可选增强，构建失败就自动退回 jaccard。"""
        try:
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("embedding 模式不可用（%s），回退到 jaccard", exc)
            self.mode = "jaccard"
            return None

    def _similarity(self, a: Doc, b: Doc) -> float:
        if self.mode == "embedding" and self._embedder is not None:
            try:
                va, vb = self._embedder.embed_documents(
                    [f"{a.title}\n{a.summary_raw[:400]}", f"{b.title}\n{b.summary_raw[:400]}"]
                )
                dot = sum(x * y for x, y in zip(va, vb))
                na = sum(x * x for x in va) ** 0.5
                nb = sum(y * y for y in vb) ** 0.5
                return dot / (na * nb + 1e-9)
            except Exception as exc:  # noqa: BLE001
                log.warning("向量相似度计算失败，本条退回 jaccard：%s", exc)
        return similarity(a, b)

    def filter(self, docs: list[Doc]) -> DedupResult:
        result = DedupResult()
        seen_ids: set[str] = set()
        for doc in docs:
            # 第一层：id 完全相同
            if doc.id in seen_ids:
                result.dropped.append((doc.title, "id 重复", 1.0))
                continue
            # 第二层：与已保留条目近重复
            worst: tuple[str, float] | None = None
            for kept in result.kept:
                sim = self._similarity(doc, kept)
                if sim >= self.threshold and (worst is None or sim > worst[1]):
                    worst = (kept.title, sim)
            if worst is not None:
                result.dropped.append((doc.title, worst[0], round(worst[1], 3)))
                continue
            seen_ids.add(doc.id)
            result.kept.append(doc)
        log.info("去重：输入 %d 条，保留 %d 条，丢弃 %d 条",
                 len(docs), len(result.kept), result.dropped_count)
        return result
