"""模型输出解析的测试：脏 JSON 是线上最常见的故障来源。

这里的用例来自真实踩坑：
- 模型把 JSON 包在 ```json 代码块里；
- 前后带"好的，结果如下"这种废话；
- prompt 里如果写成了双花括号 {{ }}，模型会原样输出双花括号；
- 结尾多逗号。
"""

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from aidaily.llm import LLMClient, extract_json
from aidaily.models import RankResult


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json_with_noise():
    text = '好的，结果如下：\n```json\n{"picks": [{"index": 1}]}\n```\n希望有帮助'
    assert extract_json(text)["picks"][0]["index"] == 1


def test_json_followed_by_explanation():
    text = '{"picks": []} 以上是结果。'
    assert extract_json(text) == {"picks": []}


def test_trailing_comma_tolerated():
    assert extract_json('{"a": 1,}') == {"a": 1}


def test_double_braces_tolerated():
    """模型照抄 prompt 模板时，会输出 {{...}} 这种多套一层的花括号。"""
    assert extract_json('{{"a": 1}}') == {"a": 1}
    assert extract_json('```json\n{{"a": 1}}\n```') == {"a": 1}


def test_garbage_raises():
    with pytest.raises(ValueError):
        extract_json("完全没有 JSON")


def test_prompts_use_single_braces():
    """回归测试：prompt 里的 JSON 示例必须是单层花括号，否则模型会照着输出双份。"""
    from aidaily.pipeline.select import SELECT_SYSTEM
    from aidaily.pipeline.summarize import SUMMARY_SYSTEM

    # SELECT_SYSTEM 里 {n} 是占位符，替换后不能残留双花括号
    for prompt in (SELECT_SYSTEM.replace("{n}", "5"), SUMMARY_SYSTEM):
        assert "{{" not in prompt, prompt[:60]
        assert "}}" not in prompt, prompt[:60]


def test_client_validates_schema():
    class Chat:
        def invoke(self, messages):
            return type("R", (), {"content": '{"picks": [{"index": 2, "reason": "热"}]}'})()

    result = LLMClient(Chat(), backend="http").json("system", "user", RankResult)
    assert isinstance(result, RankResult)
    assert result.picks[0].index == 2


def test_offline_client_returns_mock():
    result = LLMClient(None).json(
        "system", '[1] 来源：x\n标题：t\n摘要：s\n\n[2] 来源：y\n标题：u\n摘要：v', RankResult
    )
    assert [p.index for p in result.picks] == [1, 2]
