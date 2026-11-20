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
