"""关键词粗筛的回归测试。

这里的用例都来自真实踩坑：
- "Air" 里的 ai 被当成 AI 关键词，导致充电宝新闻进了日报；
- 加了词边界之后 "OpenAI" 又被漏掉（ai 前面是 n，不是边界）。
"""

from aidaily.keywords import count_hits, looks_ai_related


def test_air_is_not_ai():
    assert not looks_ai_related("酷态科推出 5 号磁吸电能卡 Air")
    assert not looks_ai_related("chairman said hello")


def test_openai_matched_despite_word_boundary():
    assert looks_ai_related("OpenAI 发布新模型")


def test_plural_forms_matched():
    assert looks_ai_related("LLMs are cool")


def test_chinese_keywords():
    assert looks_ai_related("腾讯混元大模型开源")
    assert not looks_ai_related("今日菜谱：番茄炒蛋")


def test_count_hits_greater_for_ai_text():
    assert count_hits("大模型 agent 推理") > count_hits("菜谱 番茄 炒蛋")
