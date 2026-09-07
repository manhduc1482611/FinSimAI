"""Chi phí giao dịch thực — cột thuế bán hàng — migration 0007.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-21

Thêm cột ``tax`` vào bảng ``transactions``: thuế thu nhập từ chuyển nhượng vốn
0.1% giá trị khớp, chỉ áp chiều BÁN (mô phỏng luật chứng khoán Việt Nam).
Tách riêng khỏi ``fee`` (phí môi giới 0.15% cả hai chiều) để báo cáo và kiểm
toán từng loại chi phí độc lập. Dòng cũ giữ nguyên 0.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "tax",
            sa.Numeric(precision=20, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "tax")
