"""推送抽象：换渠道只改 .env，不改业务代码。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings


class Notifier(ABC):
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def send(self, title: str, markdown: str) -> bool:
        """返回 True 表示推送成功。"""


def build_notifier(settings: Settings) -> Notifier:
    from .console import ConsoleNotifier
    from .email import EmailNotifier
    from .feishu import FeishuNotifier
    from .serverchan import ServerChanNotifier
    from .wecom import WeComNotifier

    channel = (settings.notify_channel or "console").lower()
    if channel == "wecom":
        return WeComNotifier(settings)
    if channel == "feishu":
        return FeishuNotifier(settings)
    if channel == "serverchan":
        return ServerChanNotifier(settings)
    if channel == "email":
        return EmailNotifier(settings)
    return ConsoleNotifier(settings)


__all__ = ["Notifier", "build_notifier"]
