"""add_audit_logs

Revision ID: 20260514232029
Revises: c3df8fb7bbef
Create Date: 2026-05-14 23:20:29.175050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '20260514232029'
down_revision: Union[str, None] = 'c3df8fb7bbef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL NOT NULL,
            actor_user_id INTEGER,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            action VARCHAR(50) NOT NULL,
            old_data JSON,
            new_data JSON,
            extra_data JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (actor_user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    """))

    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs (actor_user_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs (entity_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs (entity_type)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id)"))


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")