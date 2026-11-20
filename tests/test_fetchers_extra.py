"""新增数据源的解析测试（离线样本，不联网）。"""

from aidaily.fetchers.hackernews import parse_hn
from aidaily.fetchers.hf_models import parse_hf_models
from aidaily.fetchers.reddit import parse_reddit


def test_parse_hn_keeps_ai_and_drops_others():
    payload = {
        "hits": [
            {"title": "New open-source LLM beats GPT on coding", "url": "https://a.com/1",
             "points": 320, "num_comments": 88, "created_at_i": 1763600000, "objectID": "1"},
            {"title": "My favourite coffee recipe", "url": "https://a.com/2",
             "points": 12, "num_comments": 1, "created_at_i": 1763600000, "objectID": "2"},
            {"title": "Ask HN: how do you evaluate agents?", "points": 42,
             "num_comments": 30, "created_at_i": 1763600000, "objectID": "3"},
        ]
    }
    docs = parse_hn(payload)
    titles = [d.title for d in docs]
    assert any("open-source LLM" in t for t in titles)
    assert not any("coffee" in t for t in titles)
    # 没有外链的帖子回退到 HN 讨论页
    ask = next(d for d in docs if d.title.startswith("Ask HN"))
    assert ask.url == "https://news.ycombinator.com/item?id=3"
    assert ask.heat == 42 and ask.heat_label == "🔥42"
    assert ask.published_at is not None


def test_parse_reddit_reads_score_and_permalink():
    payload = {
        "data": {
            "children": [
                {"data": {"title": "Llama 4 released", "permalink": "/r/LocalLLaMA/comments/x/",
                          "score": 512, "num_comments": 140, "created_utc": 1763600000,
                          "selftext": "weights are out"}},
                {"data": {"title": "每周闲聊帖", "permalink": "/r/LocalLLaMA/comments/y/",
                          "score": 3, "num_comments": 0, "created_utc": 1763600000,
                          "stickied": True}},
            ]
        }
    }
    docs = parse_reddit(payload, "LocalLLaMA")
    assert len(docs) == 1
    assert docs[0].heat == 512
    assert docs[0].url == "https://www.reddit.com/r/LocalLLaMA/comments/x/"
    assert "140 评论" in docs[0].summary_raw


def test_parse_hf_models_uses_likes_as_heat():
    payload = [
        {"id": "deepseek-ai/DeepSeek-V3", "likes": 2400, "downloads": 900000,
         "pipeline_tag": "text-generation", "createdAt": "2026-11-01T00:00:00.000Z"},
        {"id": "", "likes": 1},
    ]
    docs = parse_hf_models(payload)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "deepseek-ai/DeepSeek-V3（♥2400）"
    assert doc.url == "https://huggingface.co/deepseek-ai/DeepSeek-V3"
    assert doc.heat == 2400
    assert doc.published_at is not None


def test_registry_filters_by_sources(settings):
    from aidaily.fetchers import build_fetchers

    settings.sources = "arxiv,hackernews"
    names = [f.name for f in build_fetchers(settings)]
    assert names == ["arxiv", "hackernews"]


def test_registry_warns_on_unknown_source(settings, caplog):
    from aidaily.fetchers import build_fetchers

    settings.sources = "arxiv,not-exist"
    with caplog.at_level("WARNING"):
        fetchers = build_fetchers(settings)
    assert [f.name for f in fetchers] == ["arxiv"]
    assert "未知数据源" in caplog.text
