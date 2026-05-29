"""add conversation analysis reports

Revision ID: 8c8e5d6e9b1a
Revises: f3bcf1f5e34a
Create Date: 2026-05-25 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c8e5d6e9b1a"
down_revision: Union[str, None] = "f3bcf1f5e34a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_analysis_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("overall_grade", sa.String(length=10), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("scores", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ai_coach_insights", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("strengths", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("weaknesses", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("knowledge_gaps", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("study_plan", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("raw_ai_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", name="uq_conversation_analysis_reports_conversation_id"),
    )
    op.create_index(
        op.f("ix_conversation_analysis_reports_id"),
        "conversation_analysis_reports",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_analysis_reports_conversation_id"),
        "conversation_analysis_reports",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_analysis_reports_conversation_id"), table_name="conversation_analysis_reports")
    op.drop_index(op.f("ix_conversation_analysis_reports_id"), table_name="conversation_analysis_reports")
    op.drop_table("conversation_analysis_reports")
