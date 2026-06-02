"""add_cv_score_overrides

Revision ID: 1bef7696bbf2
Revises: 20260518080000
Create Date: 2026-05-30 16:01:50.152605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1bef7696bbf2"
down_revision: Union[str, None] = "20260518080000"
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
    op.drop_index(
        op.f("ix_users_google_id"),
        table_name="users",
    )

    op.drop_index(
        op.f("ix_roles_name"),
        table_name="roles",
    )

    op.create_index(
        "ix_roles_name",
        "roles",
        ["name"],
        unique=False,
    )

    op.create_unique_constraint(
        "roles_name_key",
        "roles",
        ["name"],
    )

    op.drop_index(
        op.f("ix_permissions_code"),
        table_name="permissions",
    )

    op.create_index(
        "ix_permissions_code",
        "permissions",
        ["code"],
        unique=False,
    )

    op.create_unique_constraint(
        "permissions_code_key",
        "permissions",
        ["code"],
    )

    op.drop_index(
        op.f("ix_cv_score_overrides_user_id"),
        table_name="cv_score_overrides",
    )

    op.drop_index(
        op.f("ix_cv_score_overrides_jd_id"),
        table_name="cv_score_overrides",
    )

    op.drop_index(
        op.f("ix_cv_score_overrides_id"),
        table_name="cv_score_overrides",
    )

    op.drop_index(
        op.f("ix_cv_score_overrides_cv_id"),
        table_name="cv_score_overrides",
    )

    op.drop_table("cv_score_overrides")