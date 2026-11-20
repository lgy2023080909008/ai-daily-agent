"""抓取基类：重试 + 缓存兜底。

真实世界的抓取一定会有失败（限流、超时、网站改版），
所以每个抓取器都必须能回答两个问题：失败重试几次？重试都失败用什么兜底？
这里的答案是：指数退避重试 N 次，最后读「上一次成功的缓存」。
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import requests

from ..config import Settings
from ..models import RawDoc

log = logging.getLogger(__name__)

USER_AGENT = "ai-daily-agent/0.1 (+https://github.com/)"


class Fetcher(ABC):
    """所有抓取器的父类。子类只需要实现 _fetch()。"""

    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sleep = time.sleep  # 测试里可以替换掉，避免真的等待

    @abstractmethod
    def _fetch(self) -> list[RawDoc]:
        """真正去抓数据，失败请直接抛异常，由父类统一重试。"""

    def fetch(self) -> list[RawDoc]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                docs = self._fetch()
                if docs:
                    self._write_cache(docs)
                log.info("[%s] 抓取成功 %d 条", self.name, len(docs))
                return docs
            except Exception as exc:  # noqa: BLE001 - 抓取层就是要吞掉所有异常
                last_error = exc
                wait = min(2 ** attempt, 8)
                log.warning("[%s] 第 %d/%d 次失败：%s，%ds 后重试",
                            self.name, attempt, self.settings.max_retries, exc, wait)
                if attempt < self.settings.max_retries:
                    self.sleep(wait)

        cached = self._read_cache()
        log.error("[%s] 重试全部失败（%s），回退到缓存 %d 条",
                  self.name, last_error, len(cached))
        return cached

    # ------------------------------------------------------------------ 缓存
    @property
    def _cache_path(self) -> Path:
        path = Path(self.settings.cache_dir) / f"{self.name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_cache(self, docs: list[RawDoc]) -> None:
        payload = {
            "saved_at": datetime.utcnow().isoformat(timespec="seconds"),
            "docs": [d.model_dump(mode="json") for d in docs],
        }
        self._cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _read_cache(self) -> list[RawDoc]:
        if not self._cache_path.exists():
            return []
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return [RawDoc.model_validate(d) for d in payload.get("docs", [])]
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] 缓存读取失败：%s", self.name, exc)
            return []


def http_get(url: str, *, params: dict | None = None, timeout: int = 15,
             headers: dict | None = None) -> requests.Response:
    """统一入口：带 UA、带超时，4xx/5xx 直接抛异常交给重试逻辑。"""
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    resp = requests.get(url, params=params, timeout=timeout, headers=merged)
    resp.raise_for_status()
    return resp
