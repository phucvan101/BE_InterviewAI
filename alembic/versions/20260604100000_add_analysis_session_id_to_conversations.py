"""add_analysis_session_id_to_conversations

Revision ID: 20260604100000
Revises: 8dd9d7da9120
Create Date: 2026-06-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260604100000"
down_revision: Union[str, None] = "8dd9d7da9120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("analysis_session_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_conversations_analysis_session_id",
        "conversations",
        ["analysis_session_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_conversations_analysis_session_id_analysis_sessions",
        "conversations",
        "analysis_sessions",
        ["analysis_session_id"],
        ["id_session"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_analysis_session_id_analysis_sessions",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index("ix_conversations_analysis_session_id", table_name="conversations")
    op.drop_column("conversations", "analysis_session_id")
