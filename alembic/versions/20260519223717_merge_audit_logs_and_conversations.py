"""merge audit_logs and conversations

Revision ID: 37ad13d06aab
Revises: 20260514232029, 20260517162427
Create Date: 2026-05-19 22:37:17.874929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37ad13d06aab'
down_revision: Union[str, None] = ('20260514232029', '20260517162427')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
