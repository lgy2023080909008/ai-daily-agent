"""Server 酱（sct.ftqq.com）：个人微信推送，注册后拿一个 sendkey 即可。"""

from __future__ import annotations

import logging

import requests

from ..config import Settings
from .base import Notifier

log = logging.getLogger(__name__)


class ServerChanNotifier(Notifier):
    name = "serverchan"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.key = settings.serverchan_key.strip()

    def send(self, title: str, markdown: str) -> bool:
        if not self.key:
            log.error("SERVERCHAN_KEY 未配置，推送跳过")
            return False
        url = f"https://sctapi.ftqq.com/{self.key}.send"
        try:
            resp = requests.post(
                url, data={"title": title, "desp": markdown[:20000]}, timeout=15
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.error("Server酱推送失败：%s", exc)
            return False
        if payload.get("code") == 0:
            log.info("Server酱推送成功")
            return True
        log.error("Server酱返回错误：%s", payload)
        return False
