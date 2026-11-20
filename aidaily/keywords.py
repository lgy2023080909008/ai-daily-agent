"""AI 相关关键词表：用于粗筛（RSS 源混杂时先过滤一遍，省 LLM 的钱）。

踩过的坑：早期用 `"ai" in text` 做匹配，结果 "Air"、"said"、"chair" 全被当成 AI 相关。
现在英文关键词按「词边界」匹配（允许复数），中文关键词才用子串匹配。
"""

from __future__ import annotations

import re

AI_KEYWORDS: tuple[str, ...] = (
    "ai", "人工智能", "大模型", "llm", "gpt", "chatgpt", "claude", "gemini", "deepseek",
    "qwen", "通义", "文心", "kimi", "豆包", "智能体", "agent", "rag", "向量", "embedding",
    "微调", "fine-tune", "lora", "推理", "reasoning", "多模态", "multimodal", "扩散模型",
    "diffusion", "transformer", "开源模型", "open source model", "sota", "benchmark",
    "机器学习", "深度学习", "神经网络", "算力", "gpu", "nvidia", "昇腾", "具身智能",
    "机器人", "自动驾驶", "语音识别", "计算机视觉", "nlp", "aigc", "提示词", "prompt",
    # 专有名词（"openai" 里的 ai 不是独立单词，必须单列，否则会被词边界匹配漏掉）
    "openai", "anthropic", "huggingface", "llama", "mistral", "copilot", "cursor",
    "midjourney", "sora", "suno", "glm", "智谱", "混元", "minimax", "百川",
)

_CJK = re.compile(r"[\u4e00-\u9fff]")
_patterns: dict[str, re.Pattern[str]] = {}


def _pattern(keyword: str) -> re.Pattern[str]:
    """英文关键词用词边界，允许复数；中文关键词用子串。"""
    if keyword not in _patterns:
        if _CJK.search(keyword):
            _patterns[keyword] = re.compile(re.escape(keyword))
        else:
            _patterns[keyword] = re.compile(
                rf"(?<![a-z0-9]){re.escape(keyword)}s?(?![a-z0-9])"
            )
    return _patterns[keyword]


def count_hits(*texts: str) -> int:
    blob = " ".join(t or "" for t in texts).lower()
    return sum(1 for k in AI_KEYWORDS if _pattern(k).search(blob))


def looks_ai_related(*texts: str) -> bool:
    """任意一段文本命中关键词即认为相关（宁可多留，后面还有 LLM 打分兜底）。"""
    blob = " ".join(t or "" for t in texts).lower()
    return any(_pattern(k).search(blob) for k in AI_KEYWORDS)
