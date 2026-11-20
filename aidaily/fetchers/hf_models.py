"""Hugging Face 模型榜：开源模型发布的第一现场，带 likes 与 downloads。

热度信号：likes（社区认可）和 downloads（实际使用量），比论文点赞更硬。

注意：huggingface.co 在国内直连常常超时，默认**不开启**（见 .env 的 SOURCES）。
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..config import Settings
from ..models import RawDoc
from .base import Fetcher, http_get

log = logging.getLogger(__name__)

API = "https://huggingface.co/api/models"


def parse_hf_models(payload: list[dict], limit: int = 25) -> list[RawDoc]:
    docs: list[RawDoc] = []
    for item in payload[:limit]:
        model_id = str(item.get("modelId") or item.get("id") or "").strip()
        if not model_id:
            continue
        likes = int(item.get("likes") or 0)
        downloads = int(item.get("downloads") or 0)
        pipeline = item.get("pipeline_tag") or "未知任务"
        created = item.get("createdAt")
        published = None
        if created:
            try:
                published = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            except ValueError:
                published = None
        docs.append(
            RawDoc(
                source="hf_models",
                title=f"{model_id}（♥{likes}）",
                url=f"https://huggingface.co/{model_id}",
                summary_raw=f"开源模型 · 任务：{pipeline} · 点赞 {likes} · 下载 {downloads}",
                published_at=published,
                tags=[pipeline],
                heat=likes,
                heat_label=f"♥{likes}",
            )
        )
    return docs


class HuggingFaceModelsFetcher(Fetcher):
    name = "hf_models"

    def _fetch(self) -> list[RawDoc]:
        resp = http_get(
            API,
            params={"sort": "trendingScore", "direction": -1, "limit": 40},
            timeout=self.settings.request_timeout,
        )
        return parse_hf_models(resp.json())
