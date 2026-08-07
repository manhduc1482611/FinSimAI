"""Tasks & rewards — migration 0006.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-07

Thêm bảng ``tasks`` (danh mục nhiệm vụ, admin quản lý), ``user_task_progress``
(tiến độ + thưởng đã cộng của từng user) và ``user_streaks`` (chuỗi ngày đăng
nhập). Đây là nền tảng của hệ thống thưởng tiền ảo theo hành vi: nhiệm vụ định
hướng/học tập (1 lần), nhiệm vụ hằng ngày (reset theo ngày) và streak.

Cột ``period_date`` của ``user_task_progress`` dùng để phân biệt chu kỳ của nhiệm
vụ hằng ngày: với nhiệm vụ 1 lần thì ``period_date`` = NULL (Postgres UNIQUE cho
phép nhiều NULL), với nhiệm vụ hằng ngày thì là ngày diễn ra (1 dòng/user/ngày).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column(
            "reward_amount", sa.Numeric(precision=20, scale=2),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "target_count", sa.Integer(),
            server_default=sa.text("1"), nullable=False,
        ),
        sa.Column(
            "reset_frequency", sa.String(length=10),
            server_default=sa.text("'none'"), nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            server_default=sa.text("true"), nullable=False,
        ),
        sa.Column(
            "sort_order", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("idx_tasks_code", "tasks", ["code"], unique=True)
    op.create_index("idx_tasks_category", "tasks", ["category"])

    op.create_table(
        "user_task_progress",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "progress_count", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_amount", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("period_date", sa.Date(), nullable=True),
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "task_id", "period_date", name="uq_user_task_period"
        ),
    )
    op.create_index("idx_progress_user", "user_task_progress", ["user_id"])
    op.create_index("idx_progress_task", "user_task_progress", ["task_id"])

    op.create_table(
        "user_streaks",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "current_streak", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column(
            "longest_streak", sa.Integer(),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("last_checkin_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_streaks")
    op.drop_index("idx_progress_task", table_name="user_task_progress")
    op.drop_index("idx_progress_user", table_name="user_task_progress")
    op.drop_table("user_task_progress")
    op.drop_index("idx_tasks_category", table_name="tasks")
    op.drop_index("idx_tasks_code", table_name="tasks")
    op.drop_table("tasks")
