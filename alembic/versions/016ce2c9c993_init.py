"""init

Revision ID: 016ce2c9c993
Revises: 
Create Date: 2026-04-11 09:20:29.980461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '016ce2c9c993'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─────────────────────────────────────────────
    # 1. Add columns (allow NULL temporarily)
    # ─────────────────────────────────────────────
    op.add_column(
        'users',
        sa.Column('auth_provider', sa.String(length=20), nullable=True)
    )

    op.add_column(
        'users',
        sa.Column('google_id', sa.String(length=255), nullable=True)
    )

    op.add_column(
        'users',
        sa.Column('avatar_url', sa.String(length=500), nullable=True)
    )

    # ─────────────────────────────────────────────
    # 2. Backfill existing data
    # ─────────────────────────────────────────────
    op.execute("""
        UPDATE users
        SET auth_provider = 'password'
        WHERE auth_provider IS NULL
    """)

    # ─────────────────────────────────────────────
    # 3. Enforce NOT NULL constraint
    # ─────────────────────────────────────────────
    op.alter_column(
        'users',
        'auth_provider',
        nullable=False
    )

    # ─────────────────────────────────────────────
    # 4. Indexes
    # ─────────────────────────────────────────────
    op.create_index(
        op.f('ix_users_google_id'),
        'users',
        ['google_id'],
        unique=True
    )


def downgrade() -> None:
    # ─────────────────────────────────────────────
    # Rollback changes
    # ─────────────────────────────────────────────
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'google_id')
    op.drop_column('users', 'auth_provider')