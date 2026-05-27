"""add_embedding_vector_urls

Revision ID: 20260517120000
Revises: 20260514232029
Create Date: 2026-05-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '20260517120000'
down_revision: Union[str, None] = '0f160c703113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cv_profiles', sa.Column('embedding_vector_url', sa.String(500), nullable=True))
    op.add_column('job_descriptions', sa.Column('embedding_vector_url', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('job_descriptions', 'embedding_vector_url')
    op.drop_column('cv_profiles', 'embedding_vector_url')
