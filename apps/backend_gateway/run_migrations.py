"""Chạy ``alembic upgrade head`` trước khi server khởi động.

Đọc ``DATABASE_URL_SYNC`` từ môi trường (DSN sync, scheme ``postgresql://``),
trỏ vào ``packages/database/alembic.ini`` của monorepo rồi nâng schema DB lên
head. Nếu biến chưa được đặt hoặc thư mục migrations không tồn tại, chỉ cảnh
báo và thoát 0 — server sẽ tự phát hiện DB lỗi ở health check khi khởi động.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_PKG = REPO_ROOT / "packages" / "database"
ALEMBIC_INI = DATABASE_PKG / "alembic.ini"


def _database_url_sync() -> str | None:
    url = os.environ.get("DATABASE_URL_SYNC")
    if url:
        return url
    try:
        from core.config import settings

        return settings.database_url_sync
    except Exception:
        return None


def run_migrations() -> None:
    url = _database_url_sync()
    if not url:
        logger.warning(
            "DATABASE_URL_SYNC chưa được đặt — bỏ qua alembic upgrade. "
            "Nếu bảng DB chưa tồn tại, server sẽ trả lỗi khi truy vấn."
        )
        return
    if not ALEMBIC_INI.exists():
        logger.warning("Không tìm thấy %s — bỏ qua alembic upgrade.", ALEMBIC_INI)
        return

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str((DATABASE_PKG / "migrations").resolve()))
    cfg.set_main_option("sqlalchemy.url", url)

    logger.info("Đang chạy alembic upgrade head…")
    command.upgrade(cfg, "head")
    logger.info("Migration database hoàn tất.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_migrations()
