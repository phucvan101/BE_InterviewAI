"""merge heads

Revision ID: 946e7addaf5c
Revises: 20260407_0001, 016ce2c9c993
Create Date: 2026-04-11 15:59:39.152780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '946e7addaf5c'
down_revision: Union[str, None] = ('20260407_0001', '016ce2c9c993')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
