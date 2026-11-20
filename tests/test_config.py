"""配置的健壮性测试：空环境变量不能把默认值冲掉。

真实场景：GitHub Actions 里没配置的 secret 会以空字符串注入环境变量，
如果不处理，`SOURCES=""` 会让一个源都不抓，`TOP_N=""` 会直接抛类型错误。
"""

from aidaily.config import Settings


def test_empty_string_falls_back_to_default():
    settings = Settings(sources="", top_n=None, notify_channel="", smtp_host="")
    assert settings.source_list == ["arxiv", "huggingface", "github", "rss", "hackernews"]
    assert settings.top_n == 5
    assert settings.notify_channel == "console"
    assert settings.smtp_host == "smtp.qq.com"


def test_empty_api_key_means_offline():
    settings = Settings(llm_api_key="")
    assert settings.llm_enabled is False
    assert settings.llm_backend == "langchain"


def test_explicit_values_are_kept():
    settings = Settings(sources="arxiv,hackernews", top_n=3, notify_channel="email")
    assert settings.source_list == ["arxiv", "hackernews"]
    assert settings.top_n == 3
    assert settings.notify_channel == "email"


def test_source_list_ignores_blank_entries():
    settings = Settings(sources="arxiv, ,github,")
    assert settings.source_list == ["arxiv", "github"]
