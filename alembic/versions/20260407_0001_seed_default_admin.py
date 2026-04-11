"""seed default admin user

Revision ID: 20260407_0001
Revises: 
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

from app.core.config import settings
from app.core.security import hash_password

# revision identifiers, used by Alembic.
revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "users" not in inspector.get_table_names():
        # Tables are expected to be created elsewhere (e.g., init_db).
        return

    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("username", sa.String),
        sa.column("full_name", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("auth_provider", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("is_superuser", sa.Boolean),
        sa.column("is_verified", sa.Boolean),
    )

    admin_email = settings.DEFAULT_ADMIN_EMAIL
    admin_username = settings.DEFAULT_ADMIN_USERNAME
    admin_password = settings.DEFAULT_ADMIN_PASSWORD
    admin_full_name = settings.DEFAULT_ADMIN_FULL_NAME

    existing = conn.execute(
        sa.select(users.c.id).where(
            sa.or_(
                users.c.email == admin_email,
                users.c.username == admin_username,
            )
        )
    ).first()

    if existing is None:
        conn.execute(
            users.insert().values(
                email=admin_email,
                username=admin_username,
                full_name=admin_full_name,
                hashed_password=hash_password(admin_password),
                auth_provider="password",
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "users" not in inspector.get_table_names():
        return

    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("username", sa.String),
    )

    conn.execute(
        users.delete().where(
            sa.or_(
                users.c.email == settings.DEFAULT_ADMIN_EMAIL,
                users.c.username == settings.DEFAULT_ADMIN_USERNAME,
            )
        )
    )
