"""LLM 后端切换的测试：覆盖 langchain / http / mock 三条路径。

背景：langchain-openai 与 openai SDK 的版本组合不兼容时，会出现
"process() takes no keyword arguments"。所以项目保留了 LLM_BACKEND=http 这条
只依赖 requests 的通道，这里把它固定住。
"""

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from aidaily.llm import (
    LLMClient,
    RequestsChatClient,
    build_llm_client,
    to_openai_messages,
)
from aidaily.models import RankResult


def test_message_roles_mapped_correctly():
    payload = to_openai_messages([SystemMessage(content="s"), HumanMessage(content="h")])
    assert payload == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "h"},
    ]


def test_backend_falls_back_to_mock_without_key(settings):
    settings.llm_api_key = ""
    client = build_llm_client(settings)
    assert client.offline is True
    assert client.backend == "mock"


def test_backend_http_selected_by_env(settings):
    settings.llm_api_key = "sk-test"
    settings.llm_backend = "http"
    client = build_llm_client(settings)
    assert client.offline is False
    assert client.backend == "http"


def test_requests_client_parses_completion(settings, monkeypatch):
    settings.llm_api_key = "sk-test"
    client = RequestsChatClient(settings)

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"picks": [{"index": 1, "reason": "热"}]}'}}]}

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)
        return FakeResp()

    monkeypatch.setattr("aidaily.llm.requests.post", fake_post)

    result = LLMClient(client, backend="http").json("sys", "user", RankResult)
    assert result.picks[0].index == 1
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["payload"]["messages"][0]["role"] == "system"


# ------------------------------------------------------------------ 自动降级
def _ok_chat(text: str):
    class Chat:
        def invoke(self, messages):
            return type("Resp", (), {"content": text})()

    return Chat()


def test_is_sdk_error_detects_signature_errors():
    from aidaily.llm import _is_sdk_error

    assert _is_sdk_error(TypeError("process() takes no keyword arguments"))
    assert _is_sdk_error(ValueError("process() takes no keyword arguments"))
    assert not _is_sdk_error(ValueError("无法从模型输出中解析 JSON"))


def test_auto_switch_to_http_when_sdk_broken():
    """langchain 后端报 SDK 错误时，应自动切到 HTTP 后端并继续，而不是整条失败。"""

    class BrokenChat:
        def invoke(self, messages):
            raise TypeError("process() takes no keyword arguments")

    fallback = _ok_chat('{"picks": [{"index": 1, "reason": "补位"}]}')
    client = LLMClient(
        BrokenChat(), backend="langchain", fallback_chat=fallback, fallback_backend="http"
    )

    result = client.json("sys", "user", RankResult)
    assert client.backend == "http"
    assert client.switched is True
    assert result.picks[0].index == 1
    # 第二次直接走 fallback，不再打坏掉的主后端
    assert client.json("sys", "user", RankResult).picks[0].index == 1


def test_business_error_does_not_switch_backend():
    client = LLMClient(
        _ok_chat("这不是 JSON"),
        backend="langchain",
        fallback_chat=_ok_chat('{"picks": [{"index": 1}]}'),
        fallback_backend="http",
    )
    with pytest.raises(ValueError):
        client.json("sys", "user", RankResult)
    assert client.switched is False
