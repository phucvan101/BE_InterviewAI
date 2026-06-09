"""add_cv_score_overrides

Revision ID: 1bef7696bbf2
Revises: 8dd9d7da9120
Create Date: 2026-05-30 16:01:50.152605
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1bef7696bbf2"
down_revision: Union[str, None] = "8dd9d7da9120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cv_score_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cv_id", sa.String(), nullable=False),
        sa.Column("jd_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("overridden_scores", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_cv_score_overrides_cv_id"),
        "cv_score_overrides",
        ["cv_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_cv_score_overrides_id"),
        "cv_score_overrides",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_cv_score_overrides_jd_id"),
        "cv_score_overrides",
        ["jd_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_cv_score_overrides_user_id"),
        "cv_score_overrides",
        ["user_id"],
        unique=False,
    )

    op.drop_constraint(
        "permissions_code_key",
        "permissions",
        type_="unique",
    )

    op.drop_index(
        "ix_permissions_code",
        table_name="permissions",
    )

    op.create_index(
        op.f("ix_permissions_code"),
        "permissions",
        ["code"],
        unique=True,
    )

    op.drop_constraint(
        "roles_name_key",
        "roles",
        type_="unique",
    )

    op.drop_index(
        "ix_roles_name",
        table_name="roles",
    )

    op.create_index(
        op.f("ix_roles_name"),
        "roles",
        ["name"],
        unique=True,
    )

    op.create_index(
        op.f("ix_users_google_id"),
        "users",
        ["google_id"],
        unique=True,
    )


def downgrade() -> None:
    # users
    op.execute(
        sa.text("DROP INDEX IF EXISTS ix_users_google_id")
    )

    # roles
    op.execute(
        sa.text("DROP INDEX IF EXISTS ix_roles_name")
    )

    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS ix_roles_name
        ON roles (name)
        """)
    )

    op.execute(
        sa.text("""
        ALTER TABLE roles
        DROP CONSTRAINT IF EXISTS roles_name_key
        """)
    )

    op.execute(
        sa.text("""
        ALTER TABLE roles
        ADD CONSTRAINT roles_name_key UNIQUE (name)
        """)
    )

    # permissions
    op.execute(
        sa.text("DROP INDEX IF EXISTS ix_permissions_code")
    )

    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS ix_permissions_code
        ON permissions (code)
        """)
    )

    op.execute(
        sa.text("""
        ALTER TABLE permissions
        DROP CONSTRAINT IF EXISTS permissions_code_key
        """)
    )

    op.execute(
        sa.text("""
        ALTER TABLE permissions
        ADD CONSTRAINT permissions_code_key UNIQUE (code)
        """)
    )

    # cv_score_overrides
    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_cv_score_overrides_user_id"
        )
    )

    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_cv_score_overrides_jd_id"
        )
    )

    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_cv_score_overrides_id"
        )
    )

    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS ix_cv_score_overrides_cv_id"
        )
    )

    op.execute(
        sa.text(
            "DROP TABLE IF EXISTS cv_score_overrides"
        )
    )