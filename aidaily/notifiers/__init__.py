"""推送渠道。默认 console：写本地文件 + 打印，开发时最省事。"""

from .base import Notifier, build_notifier
from .console import ConsoleNotifier
from .email import EmailNotifier
from .feishu import FeishuNotifier
from .serverchan import ServerChanNotifier
from .wecom import WeComNotifier

__all__ = [
    "Notifier",
    "build_notifier",
    "ConsoleNotifier",
    "EmailNotifier",
    "FeishuNotifier",
    "WeComNotifier",
    "ServerChanNotifier",
]
