"""WS production-hardening vòng 2 — index hiệu năng cho trade watermark poll.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-31

Lý do: vòng poll của leader TradeNotifier query transactions theo watermark
(ORDER BY created_at ASC, id ASC + WHERE (created_at, id) > watermark) mỗi 1-3
giây. Nếu không có composite index trên (created_at, id), Postgres phải Seq Scan
+ Sort toàn bộ bảng mỗi nhịp khi lưu lượng giao dịch cao.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_transactions_watermark",
        "transactions",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_transactions_watermark", table_name="transactions")
