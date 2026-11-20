"""推送渠道的测试：不真的发消息，只验证“选对了渠道、消息拼对了”。"""

from aidaily.notifiers.base import build_notifier
from aidaily.notifiers.email import EmailNotifier


def test_build_email_notifier(settings):
    settings.notify_channel = "email"
    notifier = build_notifier(settings)
    assert notifier.name == "email"


def test_unknown_channel_falls_back_to_console(settings):
    settings.notify_channel = "not-exist"
    assert build_notifier(settings).name == "console"


def test_email_message_contains_subject_and_body(settings):
    settings.smtp_user = "sender@qq.com"
    settings.mail_to = "a@qq.com,b@qq.com"
    notifier = EmailNotifier(settings)
    msg = notifier.build_message("AI 日报", "# 标题\n内容")
    assert msg["Subject"] == "AI 日报"
    assert msg["From"] == "sender@qq.com"
    assert "b@qq.com" in msg["To"]
    body = msg.get_body(preferencelist=("plain",)).get_content()
    assert "# 标题" in body


def test_email_without_config_returns_false(settings):
    settings.smtp_user = ""
    settings.mail_to = ""
    assert EmailNotifier(settings).configured is False
    assert EmailNotifier(settings).send("t", "md") is False


# ---------------------------------------------------------------- Markdown 转 HTML
def test_markdown_to_html_basic():
    from aidaily.notifiers.email import markdown_to_html

    md = (
        "# AI 技术前沿日报 · 2026-11-20\n"
        "\n"
        "> 抓取 128 条 · 精选 5 条\n"
        "\n"
        "## 1. TideCache\n"
        "\n"
        "**GitHub** ｜ [原文](https://github.com/x)\n"
        "\n"
        "---\n"
    )
    out = markdown_to_html(md)
    assert "<h2>AI 技术前沿日报 · 2026-11-20</h2>" in out
    assert "<h3>1. TideCache</h3>" in out
    assert "<strong>GitHub</strong>" in out
    assert '<a href="https://github.com/x">原文</a>' in out
    assert "<hr>" in out
    assert "##" not in out.replace("</h2>", "").replace("</h3>", "")  # 标题符号被消化掉


def test_markdown_to_html_escapes_raw_html():
    from aidaily.notifiers.email import markdown_to_html

    out = markdown_to_html('## <script>alert("x")</script>')
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_email_message_has_html_alternative(settings):
    settings.smtp_user = "sender@qq.com"
    settings.mail_to = "a@qq.com"
    notifier = EmailNotifier(settings)
    msg = notifier.build_message("AI 日报", "## 标题\n内容")
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert "<h3>标题</h3>" in html_body
