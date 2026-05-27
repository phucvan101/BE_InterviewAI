"""add_columms_started_at_ended_at_and_interview_duration_seconds

Revision ID: 8dd9d7da9120
Revises: 8c8e5d6e9b1a
Create Date: 2026-05-26 10:41:00.765359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dd9d7da9120'
down_revision: Union[str, None] = '8c8e5d6e9b1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("interview_duration_seconds", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE conversations
        SET
            started_at = COALESCE(started_at, created_at),
            ended_at = CASE
                WHEN status = 'completed' THEN COALESCE(ended_at, updated_at)
                ELSE ended_at
            END,
            interview_duration_seconds = CASE
                WHEN status = 'completed' AND updated_at IS NOT NULL THEN
                    GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (updated_at - created_at)))::int)
                ELSE interview_duration_seconds
            END
        """
    )

    op.alter_column(
        "conversations",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("conversations", "interview_duration_seconds")
    op.drop_column("conversations", "ended_at")
    op.drop_column("conversations", "started_at")
