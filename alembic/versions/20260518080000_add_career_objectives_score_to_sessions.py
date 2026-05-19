"""add_career_objectives_score_to_sessions

Revision ID: 20260518080000
Revises: 20260517120000
Create Date: 2026-05-18 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260518080000'
down_revision: Union[str, None] = '20260517120000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('analysis_sessions', sa.Column('career_objectives_score', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('analysis_sessions', 'career_objectives_score')
