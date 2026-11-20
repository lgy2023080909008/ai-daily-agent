"""LLM 调用层。

设计要点（面试可以直接讲这三点）：
1. 只依赖 langchain-core 的 ChatModel 接口，换 DeepSeek / 通义 / OpenAI 只改 .env；
2. 输出必须是 pydantic 模型 —— 字段固定，才能算指标、才能被下游解析；
3. 没有 API key 时自动降级为 mock，链路（抓取→去重→打分→渲染）照样能跑通、能被测试。

为什么还有一条 httpx/requests 后端：
    langchain-openai 与 openai SDK 的版本组合偶尔会不兼容（例如报
    "process() takes no keyword arguments"，请求已经 200 了但解析响应时崩）。
    这时把 LLM_BACKEND=http 就能绕开 SDK，用 requests 直接打 /chat/completions。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .config import Settings
from .models import RankResult, SummaryResult

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_json(text: str) -> dict:
    """从模型输出中抠出第一个 JSON 对象。

    模型常见的三种脏输出都要能吃下：```json 代码块、前后带解释文字、结尾有逗号。
    """
    if not text or not text.strip():
        raise ValueError("模型返回空响应")

    candidates: list[str] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        candidates.append(fenced.group(1))

    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
        break

    for raw in candidates:
        variants = [raw]
        stripped = raw.strip()
        # 模型有时会照着 prompt 里的模板多输出一层花括号：{{"a": 1}}
        if stripped.startswith("{{") and stripped.endswith("}}"):
            variants.append(stripped[1:-1])
        for variant in variants:
            for attempt in (variant, re.sub(r",\s*([}\]])", r"\1", variant)):
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"无法从模型输出中解析 JSON：{text[:200]}")


# --------------------------------------------------------------------- 后端
class _ChatResponse:
    """模拟 langchain 的 AIMessage，只暴露我们真正用到的 .content。"""

    def __init__(self, content: str) -> None:
        self.content = content


_ROLE = {"system": "system", "human": "user", "ai": "assistant"}


def to_openai_messages(messages: list[Any]) -> list[dict[str, str]]:
    """langchain 的 Message 对象 → OpenAI 接口要的 role/content 列表。"""
    payload: list[dict[str, str]] = []
    for message in messages:
        role = _ROLE.get(getattr(message, "type", "human"), "user")
        payload.append({"role": role, "content": message.content})
    return payload


class RequestsChatClient:
    """不依赖 openai / langchain-openai 的极简聊天客户端。

    接口刻意做得和 BaseChatModel 一样（有个 invoke(messages) 返回带 .content 的对象），
    这样 LLMClient 不用区分后端。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.url = settings.llm_base_url.rstrip("/") + "/chat/completions"

    def invoke(self, messages: list[Any]) -> _ChatResponse:
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.llm_model,
                "messages": to_openai_messages(messages),
                "temperature": self.settings.llm_temperature,
                "max_tokens": self.settings.llm_max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return _ChatResponse(data["choices"][0]["message"]["content"])


def build_chat_backend(settings: Settings) -> tuple[Any | None, str]:
    """返回 (后端对象, 后端名)。后端对象为 None 表示离线 mock 模式。"""
    if not settings.llm_enabled:
        return None, "mock"

    if settings.llm_backend == "http":
        log.info("使用 HTTP 后端直连 %s", settings.llm_base_url)
        return RequestsChatClient(settings), "http"

    try:
        from langchain_openai import ChatOpenAI

        chat = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=60,
            max_retries=2,
        )
        return chat, "langchain"
    except Exception as exc:  # noqa: BLE001
        log.warning("langchain 后端初始化失败（%s），改用 HTTP 后端", exc)
        return RequestsChatClient(settings), "http"


def _is_sdk_error(exc: Exception) -> bool:
    """判断是不是「SDK 版本不兼容」这类错误，这类才值得换后端重试。

    典型特征：TypeError，或消息里出现 takes no keyword arguments / process()。
    业务错误（比如 JSON 解析失败、400 key 无效）不应该触发后端切换。
    """
    text = f"{type(exc).__name__}: {exc}"
    markers = ("takes no keyword arguments", "process()", "unexpected keyword")
    return isinstance(exc, TypeError) or any(m in text for m in markers)


class LLMClient:
    """薄封装：统一走 json(...)，屏蔽各家 SDK 与结构化输出的差异。

    带自动降级：langchain 后端如果报 SDK 层错误（典型是 openai 版本不兼容导致的
    "process() takes no keyword arguments"），会自动切到 HTTP 后端并继续跑，
    不需要用户改任何配置。
    """

    def __init__(
        self,
        chat: Any | None = None,
        backend: str = "mock",
        fallback_chat: Any | None = None,
        fallback_backend: str = "http",
    ) -> None:
        self._chat = chat
        self._fallback = fallback_chat
        self._fallback_backend = fallback_backend
        self.backend = backend
        self.switched = False

    @property
    def offline(self) -> bool:
        return self._chat is None

    def json(self, system: str, user: str, schema: type[T]) -> T:
        if self._chat is None:
            return self._mock(user, schema)
        try:
            return self._call(self._chat, system, user, schema)
        except Exception as exc:  # noqa: BLE001
            if self._fallback is not None and not self.switched and _is_sdk_error(exc):
                log.warning(
                    "主后端（%s）报 SDK 兼容错误：%s；已自动切换到 HTTP 后端",
                    self.backend,
                    exc,
                )
                self._chat = self._fallback
                self.backend = self._fallback_backend
                self.switched = True
                return self._call(self._chat, system, user, schema)
            raise

    @staticmethod
    def _call(chat: Any, system: str, user: str, schema: type[T]) -> T:
        message = chat.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        content = message.content
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        return schema.model_validate(extract_json(text))

    # ------------------------------------------------------------------ mock
    @staticmethod
    def _mock(user: str, schema: type[T]) -> T:
        """无 key 时的确定性替身：只用来验证链路，不代表真实效果。"""
        if schema is SummaryResult:
            # 从「标题：xxx」里取标题当摘要，离线演示时至少读得懂
            title = ""
            for line in user.splitlines():
                if line.startswith("标题："):
                    title = line[len("标题："):].strip()
                    break
            return SummaryResult(  # type: ignore[return-value]
                summary_zh=f"{title[:48]}（mock 摘要，配置 LLM_API_KEY 后为真实中文摘要）",
                why="mock 推荐理由：仅用于验证链路",
            )
        if schema is RankResult:
            # 精选的 mock：按候选编号顺序取前 5 条
            from .models import RankPick

            indices = [int(n) for n in re.findall(r"^\[(\d+)\]", user, re.M)]
            return RankResult(  # type: ignore[return-value]
                picks=[
                    RankPick(index=i, reason="mock：按候选顺序取前几条")
                    for i in indices[:5]
                ]
            )
        raise ValueError(f"mock 不支持 {schema.__name__}，请配置 LLM_API_KEY")


def build_llm_client(settings: Settings) -> LLMClient:
    """有 key 就走真实模型（langchain 或 http），没有就返回离线客户端。"""
    chat, backend = build_chat_backend(settings)
    fallback = RequestsChatClient(settings) if backend == "langchain" else None
    return LLMClient(
        chat,
        backend=backend,
        fallback_chat=fallback,
        fallback_backend="http",
    )
