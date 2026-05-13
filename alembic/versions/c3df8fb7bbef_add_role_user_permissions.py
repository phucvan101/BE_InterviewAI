"""add role user create permissions

Revision ID: c3df8fb7bbef
Revises: 20260509_0005
Create Date: 2026-05-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3df8fb7bbef"
down_revision: Union[str, None] = "20260509_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS = [
    {
        "code": "users.create",
        "name": "Tạo người dùng",
        "description": "Tạo tài khoản người dùng mới",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "roles.create",
        "name": "Tạo vai trò",
        "description": "Tạo vai trò mới",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.read",
        "name": "Xem vai trò",
        "description": "Xem danh sách vai trò",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.update",
        "name": "Chỉnh sửa vai trò",
        "description": "Cập nhật thông tin vai trò",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.delete",
        "name": "Xóa vai trò",
        "description": "Xóa vai trò",
        "module": "roles",
        "is_system": True,
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("module", sa.String),
        sa.column("is_system", sa.Boolean),
    )

    existing_codes = set(
        row[0]
        for row in conn.execute(
            sa.text("SELECT code FROM permissions")
        ).fetchall()
    )

    permissions_to_insert = [
        permission
        for permission in NEW_PERMISSIONS
        if permission["code"] not in existing_codes
    ]

    if permissions_to_insert:
        op.bulk_insert(
            permissions_table,
            permissions_to_insert
        )


def downgrade() -> None:
    conn = op.get_bind()

    codes = [permission["code"] for permission in NEW_PERMISSIONS]

    conn.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN :codes
            """
        ).bindparams(
            sa.bindparam(
                "codes",
                expanding=True
            )
        ),
        {
            "codes": codes
        }
    )