"""merge 20260423 + 20260428

Revision ID: 20260429_0004
Revises: 20260423_0003, 20260428_0003
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260429_0004'
down_revision: Union[str, None] = ('20260423_0003', '20260428_0003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
