"""add company_info to analysis_sessions

Revision ID: 20260613000100
Revises: 20260610001243
Create Date: 2026-06-13 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260613000100"
down_revision = "377994ccc270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_sessions", sa.Column("company_info", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_sessions", "company_info")
