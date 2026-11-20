"""企业微信群机器人：最常见也最省事的推送方式（免费、无需审核）。

注意：企业微信 markdown 消息有长度上限，超长会整条发送失败，
所以这里主动截断，而不是让它静默失败。
"""

from __future__ import annotations

import logging

import requests

from ..config import Settings
from .base import Notifier

log = logging.getLogger(__name__)

MAX_CHARS = 3800


class WeComNotifier(Notifier):
    name = "wecom"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.webhook = settings.wecom_webhook.strip()

    def send(self, title: str, markdown: str) -> bool:
        if not self.webhook:
            log.error("WECOM_WEBHOOK 未配置，推送跳过")
            return False

        content = markdown
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n\n> 内容过长，已截断，完整版见仓库 data/digests/"

        try:
            resp = requests.post(
                self.webhook,
                json={"msgtype": "markdown", "markdown": {"content": content}},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.error("企业微信推送失败：%s", exc)
            return False

        if payload.get("errcode") == 0:
            log.info("企业微信推送成功")
            return True
        log.error("企业微信返回错误：%s", payload)
        return False
