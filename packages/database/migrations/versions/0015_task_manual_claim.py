"""Nhiệm vụ nhận thưởng thủ công — migration 0015.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-11

Thêm ``user_task_progress.claimed_at``: thời điểm user bấm "Nhận thưởng" thủ
công. Trước đây phòng thưởng được cộng thẳng vào ``cash_balance`` khi hoàn
thành (auto-credit). Từ bản này mọi nhiệm vụ hoàn thành sẽ nằm ở trạng thái
"chưa nhận" (claimed_at IS NULL, claimable) cho tới khi user bấm nhận — badge
thông báo trên đầu hiển thị số phần thưởng đang chờ.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_task_progress",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Các dòng đã completed trước đây đều đã được auto-credit — coi như đã nhận.
    op.execute(
        "UPDATE user_task_progress SET claimed_at = completed_at "
        "WHERE completed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("user_task_progress", "claimed_at")