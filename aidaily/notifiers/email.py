"""邮件推送：零门槛渠道，一个 QQ/163 邮箱授权码就能用。

为什么留这条路：
飞书/企业微信的「应用」要企业认证，群机器人有时候也找不到入口；
邮件是唯一不依赖任何第三方平台的推送方式，稳、免费、还能存档。

QQ 邮箱配置步骤：
1. 邮箱设置 → 账户 → 开启「POP3/SMTP 服务」
2. 生成「授权码」（不是登录密码）
3. .env 里：SMTP_USER=你的QQ邮箱，SMTP_PASS=授权码，MAIL_TO=接收邮箱
"""

from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage

from ..config import Settings
from .base import Notifier

log = logging.getLogger(__name__)


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.host = settings.smtp_host.strip()
        self.port = settings.smtp_port
        self.user = settings.smtp_user.strip()
        self.password = settings.smtp_pass.strip()
        self.recipients = [
            addr.strip() for addr in settings.mail_to.split(",") if addr.strip()
        ]

    @property
    def configured(self) -> bool:
        return bool(self.host and self.user and self.password and self.recipients)

    def build_message(self, title: str, markdown: str) -> EmailMessage:
        """单独抽出来，方便测试（不需要真的连 SMTP）。"""
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = self.user
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(markdown)
        # 再加一份 HTML：等宽字体保住 Markdown 的对齐和链接可点
        msg.add_alternative(
            f"<pre style=\"font-family:Consolas,'Microsoft YaHei',monospace;"
            f"white-space:pre-wrap;font-size:14px;line-height:1.6\">"
            f"{html.escape(markdown)}</pre>",
            subtype="html",
        )
        return msg

    def send(self, title: str, markdown: str) -> bool:
        if not self.configured:
            log.error("邮件未配置完整（SMTP_HOST / SMTP_USER / SMTP_PASS / MAIL_TO）")
            return False

        msg = self.build_message(title, markdown)
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=25) as server:
                    server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=25) as server:
                    server.starttls()
                    server.login(self.user, self.password)
                    server.send_message(msg)
        except Exception as exc:  # noqa: BLE001
            log.error("邮件发送失败：%s", exc)
            return False

        log.info("邮件已发送到 %s", ", ".join(self.recipients))
        return True
