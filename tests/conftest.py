import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aidaily.config import Settings  # noqa: E402

# 默认把临时目录放在项目内（.tmp-tests/，已 gitignore）；
# 某些受限环境（CI 沙箱、只读系统临时盘）可用 AIDAILY_TEST_TMP 指定到可写目录。
BASE = Path(os.environ.get("AIDAILY_TEST_TMP") or (ROOT / ".tmp-tests"))


@pytest.fixture()
def workdir():
    """每个测试一个独立临时目录。"""
    BASE.mkdir(parents=True, exist_ok=True)
    path = BASE / f"case-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def settings(workdir):
    """配置全部指向临时目录，互不影响，且强制离线 mock。"""
    return Settings(
        db_path=str(workdir / "test.db"),
        cache_dir=str(workdir / "cache"),
        out_dir=str(workdir / "out"),
        lookback_hours=0,          # 测试里不过滤时间
        llm_api_key="",            # 强制离线 mock
        max_retries=2,
        top_n=3,
        max_candidates=10,
    )
