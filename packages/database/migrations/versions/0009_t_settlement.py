"""Thanh toán T+2 thực — cột settling_cash & settles_at — migration 0009.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-01

Thêm thanh toán bù trừ T+2 (luật chứng khoán Việt Nam) cho backend:
- ``users.settling_cash``: tiền của lượt bán ĐÃ KHỚP nhưng chưa về tài khoản
  khả dụng (chờ 2 ngày giao dịch ảo). Tách riêng khỏi ``cash_balance`` (khả dụng
  ngay) và ``frozen_cash`` (đang đóng băng cho lệnh mua treo) để user không thể
  tiêu tiền chưa về.
- ``transactions.settles_at``: mốc thời gian mà tiền bán được giải phóng
  (NULL với chiều mua / khớp tức thời). Worker ``SettlementService.release_due``
  dùng cột này để chuyển ``settling_cash`` → ``cash_balance`` một cách idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "settling_cash",
            sa.Numeric(precision=20, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "settles_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_transactions_settles_at",
        "transactions",
        ["settles_at"],
        postgresql_where=sa.text("settles_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_transactions_settles_at", table_name="transactions")
    op.drop_column("transactions", "settles_at")
    op.drop_column("users", "settling_cash")
