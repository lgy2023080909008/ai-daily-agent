"""去重逻辑的单元测试：这是全项目最容易写错、也最需要测试的一层。"""

from aidaily.models import Doc, RawDoc
from aidaily.pipeline.dedup import Deduper, jaccard, similarity


def _doc(title: str, summary: str = "", source: str = "x") -> Doc:
    return Doc.from_raw(RawDoc(source=source, title=title, url=f"https://example.com/{title}", summary_raw=summary))


def test_jaccard_same_text_is_one():
    assert jaccard("Attention is all you need", "Attention is all you need") == 1.0


def test_jaccard_unrelated_is_low():
    assert jaccard("大模型推理加速", "英伟达发布新显卡驱动") < 0.2


def test_identical_title_deduped(settings):
    docs = [_doc("同一个标题"), _doc("同一个标题")]
    result = Deduper(settings).filter(docs)
    assert len(result.kept) == 1
    assert result.dropped_count == 1


def test_near_duplicate_title_deduped(settings):
    docs = [
        _doc("OpenAI 发布 GPT-5，推理能力大幅提升"),
        _doc("OpenAI 发布 GPT-5 推理能力大幅提升！"),
    ]
    assert similarity(docs[0], docs[1]) > 0.6
    result = Deduper(settings).filter(docs)
    assert len(result.kept) == 1


def test_different_docs_kept(settings):
    docs = [_doc("大模型推理加速方案综述", "讲 speculation decoding"), _doc("机器人抓取新方法", "讲灵巧手")]
    result = Deduper(settings).filter(docs)
    assert len(result.kept) == 2


def test_threshold_is_configurable(settings):
    # 两条标题相近但不完全相同（id 不同），相似度约 0.77
    a = _doc("大模型推理加速方法综述", "介绍投机解码")
    b = _doc("大模型推理加速方法总结", "介绍投机解码")

    settings.dedup_threshold = 0.99
    assert len(Deduper(settings).filter([a, b]).kept) == 2  # 阈值高 → 都保留

    settings.dedup_threshold = 0.5
    assert len(Deduper(settings).filter([a, b]).kept) == 1  # 阈值低 → 判为重复
