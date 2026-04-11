"""seed default admin user

Revision ID: 20260407_0001
Revises: 
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


def simple_hash(password: str) -> str:
    # tạm thời hash đơn giản (KHÔNG import app)
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "users" not in inspector.get_table_names():
        return

    users = table(
        "users",
        column("email", sa.String),
        column("username", sa.String),
        column("full_name", sa.String),
        column("hashed_password", sa.String),
        column("auth_provider", sa.String),
        column("is_active", sa.Boolean),
        column("is_superuser", sa.Boolean),
        column("is_verified", sa.Boolean),
    )

    admin_email = "admin@example.com"
    admin_username = "admin"
    admin_password = "123456"
    admin_full_name = "Admin"

    existing = conn.execute(
        sa.select(users.c.email).where(
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
                hashed_password=simple_hash(admin_password),
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

    users = table(
        "users",
        column("email", sa.String),
        column("username", sa.String),
    )

    conn.execute(
        users.delete().where(
            sa.or_(
                users.c.email == "admin@example.com",
                users.c.username == "admin",
            )
        )
    )