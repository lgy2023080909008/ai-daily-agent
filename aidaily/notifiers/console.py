"""默认渠道：写到本地文件 + 打印摘要。开发调试、GitHub Actions 里都用它。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..config import Settings
from .base import Notifier


class ConsoleNotifier(Notifier):
    name = "console"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.out_dir = Path(settings.out_dir)

    def save(self, digest_date: str, markdown: str) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{digest_date or date.today().isoformat()}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def send(self, title: str, markdown: str) -> bool:
        path = self.save("", markdown)
        print(f"\n===== {title} =====")
        print(markdown)
        print(f"[console] 已写入 {path}")
        return True
