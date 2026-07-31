import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-finsim-ws-tests-0123456789")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _UnavailableCache:
    """Redis không khả dụng trong test → mọi lệnh raise ngay lập tức.

    Các module WebSocket (leader lock, dedup, backplane, snapshot cache) đều bắt
    ngoại lệ và rơi về chế độ local-only, nên test không cần một Redis thật và
    không chờ retry kết nối.
    """

    def __getattr__(self, name):
        async def _raise(*args, **kwargs):
            raise ConnectionError("Redis unavailable in tests")

        return _raise

    def pipeline(self):
        raise ConnectionError("Redis unavailable in tests")


@pytest.fixture(autouse=True)
def _redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from websockets import backplane as backplane_module
    from websockets import leader as leader_module
    from websockets import price_ws as price_ws_module
    from websockets import trade_ws as trade_ws_module

    unavailable = _UnavailableCache()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: unavailable)
    monkeypatch.setattr(leader_module, "get_cache", lambda: unavailable)
    monkeypatch.setattr(price_ws_module, "get_cache", lambda: unavailable)
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: unavailable)

    # Bộ test chạy như 1 instance duy nhất: leader election local (không phụ thuộc
    # Redis), trong khi get_cache vẫn "hỏng" để các nhánh fallback được chạy.
    from core.config import settings

    monkeypatch.setattr(settings, "ws_local_mode", True)

