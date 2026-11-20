"""全局配置：全部从环境变量 / .env 读取，代码里不硬编码任何 key。"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_empty(cls, data):
        """空字符串不应该覆盖默认值。

        典型场景：GitHub Actions 里 `secrets.X` 没配时是空字符串，
        如果直接覆盖，`SOURCES=""` 会导致一个源都不抓、`TOP_N=""` 会报类型错误。
        这里统一丢弃空值，让默认值生效。
        """
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v not in ("", None)}
        return data

    # ---- LLM ----
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # langchain（默认，走 ChatOpenAI）| http（requests 直连，SDK 版本冲突时用）
    llm_backend: str = "langchain"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024

    # ---- 抓取 ----
    # 启用的数据源，逗号分隔。可用值：
    #   arxiv / huggingface / github / rss / hackernews / reddit / hf_models
    # reddit 与 hf_models 在国内直连通常不通，有代理时再加进列表
    sources: str = "arxiv,huggingface,github,rss,hackernews"
    lookback_hours: int = 24
    request_timeout: int = 15
    max_retries: int = 3
    arxiv_max_results: int = 40
    github_days: int = 7
    rss_urls: str = "https://www.jiqizhixin.com/rss,https://www.qbitai.com/feed,https://www.ithome.com/rss/"

    # ---- 筛选（热度 + 相关性，由模型直接挑）----
    top_n: int = 5            # 最终推送到邮箱的条数
    max_candidates: int = 30  # 送进模型让它挑的候选数量（预筛上限）
    dedup_mode: str = "jaccard"   # jaccard | embedding
    dedup_threshold: float = 0.86

    # ---- 存储 ----
    db_path: str = "data/aidaily.db"
    cache_dir: str = "data/cache"
    out_dir: str = "data/digests"

    # ---- 推送 ----
    # console（写文件+打印）| email（SMTP，最省事）| feishu（飞书群机器人）
    # | wecom（企业微信群机器人）| serverchan（Server酱）
    notify_channel: str = "console"
    wecom_webhook: str = ""
    feishu_webhook: str = ""
    serverchan_key: str = ""
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""   # 邮箱「授权码」，不是登录密码
    mail_to: str = ""     # 收件人，多个用逗号分隔

    @property
    def rss_url_list(self) -> list[str]:
        return [u.strip() for u in self.rss_urls.split(",") if u.strip()]

    @property
    def source_list(self) -> list[str]:
        return [s.strip().lower() for s in self.sources.split(",") if s.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())


def load_settings(**overrides) -> Settings:
    """读取配置；测试里可以直接传 overrides 覆盖。"""
    return Settings(**overrides)
