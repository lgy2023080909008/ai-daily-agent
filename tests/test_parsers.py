"""解析层测试：用离线样本固定住各源的字段映射，源一改版测试就会红。"""

from aidaily.fetchers.arxiv import parse_arxiv
from aidaily.fetchers.github import parse_github
from aidaily.fetchers.huggingface import parse_hf
from aidaily.fetchers.rss import parse_feed_xml

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <published>2026-11-20T08:00:00Z</published>
    <title>Test   Paper
    with newline</title>
    <summary>We test parsing.</summary>
    <category term="cs.AI"/>
  </entry>
</feed>
"""

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>OpenAI 发布新一代大模型</title>
      <link>https://a.com/1</link>
      <description>推理能力提升</description>
      <pubDate>Thu, 20 Nov 2026 08:00:00 +0800</pubDate>
    </item>
    <item>
      <title>今日菜谱：番茄炒蛋</title>
      <link>https://a.com/2</link>
      <description>家常菜做法</description>
    </item>
  </channel>
</rss>
"""

ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>某多模态模型开源</title>
    <link href="https://b.com/1"/>
    <summary>权重与训练细节公开</summary>
    <published>2026-11-20T09:00:00Z</published>
  </entry>
</feed>
"""


def test_parse_arxiv():
    docs = parse_arxiv(ARXIV_XML)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "arxiv"
    assert doc.title == "Test Paper with newline"  # 换行被压平
    assert doc.url.endswith("2601.00001v1")
    assert doc.published_at is not None
    assert doc.tags == ["cs.AI"]


def test_parse_hf():
    payload = [
        {"paper": {"id": "2601.00002", "title": "A Reasoner", "summary": "S", "publishedAt": "2026-11-20T00:00:00Z"}},
        {"paper": {}},
    ]
    docs = parse_hf(payload)
    assert len(docs) == 1
    assert docs[0].url == "https://huggingface.co/papers/2601.00002"


def test_parse_github_filters_irrelevant():
    payload = {
        "items": [
            {"full_name": "acme/llm-agent", "description": "agent framework", "topics": ["llm"], "html_url": "https://github.com/acme/llm-agent", "stargazers_count": 99, "language": "Python"},
            {"full_name": "bob/recipe-app", "description": "cooking recipes", "topics": [], "html_url": "https://github.com/bob/recipe-app", "stargazers_count": 99, "language": "JS"},
        ]
    }
    docs = parse_github(payload)
    assert len(docs) == 1
    assert "llm-agent" in docs[0].title


def test_parse_rss_filters_by_keywords():
    docs = parse_feed_xml(RSS_XML, source="test.com")
    assert len(docs) == 1
    assert docs[0].title == "OpenAI 发布新一代大模型"
    assert docs[0].published_at is not None


def test_parse_atom_link_href():
    docs = parse_feed_xml(ATOM_XML, source="b.com")
    assert len(docs) == 1
    assert docs[0].url == "https://b.com/1"
    assert docs[0].published_at is not None
