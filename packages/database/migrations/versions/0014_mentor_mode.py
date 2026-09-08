"""Mentor 3-mode DB — migration 0014.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-07

Bổ sung 2 cột cho `mentor_messages` phục vụ AI Mentor 3 chế độ
(xem docs/ai_mentor_3mode_plan.md v2.0, Giai đoạn 1.1):

- `mode`: VARCHAR(16) nullable, mặc định 'socratic' cho các row cũ (_NULL_ trong
  DB cũ, đổ backfill 'socratic' để audit không bị lỗi). Giá trị:
  'concept' | 'plan' | 'trade_now' | 'socratic'.
- `metadata_json`: JSONB nullable — chứa `MentorMetadata` versioned (schema_version,
  mode, prompt_version, model, focus, trade_snapshot, used_layers) cho mục đích
  audit. NULL với các row cũ.

Cả 2 cột nullable để không phá historical rows và test migration up/down.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mentor_messages",
        sa.Column("mode", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "mentor_messages",
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
    )
    # Backfill: các hội thoại cũ đều là Socratic deterministic (v1).
    statement = sa.text(
        "UPDATE mentor_messages SET mode = 'socratic' WHERE mode IS NULL"
    )
    op.execute(statement)


def downgrade() -> None:
    op.drop_column("mentor_messages", "metadata_json")
    op.drop_column("mentor_messages", "mode")
