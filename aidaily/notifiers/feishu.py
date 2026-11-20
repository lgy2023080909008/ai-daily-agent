"""飞书群自定义机器人：个人版飞书就能建群加机器人，不需要企业认证。

用法：飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook 地址。
"""

from __future__ import annotations

import logging

import requests

from ..config import Settings
from .base import Notifier

log = logging.getLogger(__name__)

MAX_CHARS = 8000


class FeishuNotifier(Notifier):
    name = "feishu"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.webhook = settings.feishu_webhook.strip()

    def send(self, title: str, markdown: str) -> bool:
        if not self.webhook:
            log.error("FEISHU_WEBHOOK 未配置，推送跳过")
            return False

        content = f"{title}\n\n{markdown}"
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n（内容过长，已截断）"

        try:
            resp = requests.post(
                self.webhook,
                json={"msg_type": "text", "content": {"text": content}},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.error("飞书推送失败：%s", exc)
            return False

        # 飞书自定义机器人成功时返回 {"code":0} 或 {"StatusCode":0}
        if payload.get("code") == 0 or payload.get("StatusCode") == 0:
            log.info("飞书推送成功")
            return True
        log.error("飞书返回错误：%s", payload)
        return False
