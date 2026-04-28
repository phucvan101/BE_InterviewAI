"""drop interview tables

Revision ID: 20260422_0002
Revises: 20260407_0001
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa

revision = "20260422_0002"
down_revision = "20260407_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interview_questions CASCADE")
    op.execute("DROP TABLE IF EXISTS interview_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS questions CASCADE")

def downgrade() -> None:
    pass
