"""add interview states and analysis_data to conversations

Revision ID: 20260611235900
Revises: 8c8e5d6e9b1a
Create Date: 2026-06-11 23:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260611235900"
down_revision: Union[str, None] = "8c8e5d6e9b1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add analysis_data column to conversations table
    op.add_column(
        "conversations",
        sa.Column("analysis_data", sa.JSON(), nullable=True)
    )

    # Create interview_states table
    op.create_table(
        "interview_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("current_phase_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phases", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("question_counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("asked_topics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{\"min_questions_per_topic\": 1, \"max_questions_per_topic\": 3, \"total_question_limit\": 15}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", name="uq_interview_states_conversation_id"),
    )
    op.create_index(
        op.f("ix_interview_states_id"),
        "interview_states",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_states_conversation_id"),
        "interview_states",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_states_conversation_id"), table_name="interview_states")
    op.drop_index(op.f("ix_interview_states_id"), table_name="interview_states")
    op.drop_table("interview_states")
    op.drop_column("conversations", "analysis_data")
