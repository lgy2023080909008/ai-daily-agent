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
import re
import smtplib
from email.message import EmailMessage

from ..config import Settings
from .base import Notifier

log = logging.getLogger(__name__)

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """行内元素：链接、加粗、行内代码。输入必须已经过 html.escape。"""
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _CODE.sub(r"<code>\1</code>", text)
    return text


def markdown_to_html(markdown: str) -> str:
    """把日报用的 Markdown 转成邮件友好的 HTML。

    只支持我们实际用到的那几种语法（标题、引用、分隔线、链接、加粗、行内代码），
    不引第三方 markdown 库——依赖越少越好，行为也完全可控。
    """
    blocks: list[str] = []
    for raw in markdown.splitlines():
        line = html.escape(raw.rstrip())
        if not line.strip():
            continue
        if line.startswith("### "):
            blocks.append(f"<h4>{_inline(line[4:])}</h4>")
        elif line.startswith("## "):
            blocks.append(f"<h3>{_inline(line[3:])}</h3>")
        elif line.startswith("# "):
            blocks.append(f"<h2>{_inline(line[2:])}</h2>")
        elif line.startswith("&gt; "):
            blocks.append(f'<p class="quote">{_inline(line[5:])}</p>')
        elif line.strip() in ("---", "***"):
            blocks.append("<hr>")
        else:
            blocks.append(f"<p>{_inline(line)}</p>")

    body = "\n".join(blocks)
    return (
        "<div style=\"font-family:-apple-system,'Microsoft YaHei',sans-serif;"
        "font-size:14px;line-height:1.75;color:#1a1a1a;max-width:720px\">\n"
        "<style>h2{font-size:19px;margin:18px 0 10px}h3{font-size:16px;margin:16px 0 8px;"
        "color:#1F3864}h4{font-size:14px;margin:12px 0 6px}"
        ".quote{color:#666;font-size:13px;border-left:3px solid #C9D3E0;padding-left:10px;margin:8px 0}"
        "a{color:#1F3864}hr{border:none;border-top:1px solid #e5e5e5;margin:16px 0}"
        "p{margin:6px 0}</style>\n"
        f"{body}\n</div>"
    )


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
        # 纯文本兜底（不支持 HTML 的客户端）
        msg.set_content(markdown)
        # HTML 版：正常排版，手机上看不再是一堆 ## 和 **
        msg.add_alternative(markdown_to_html(markdown), subtype="html")
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
