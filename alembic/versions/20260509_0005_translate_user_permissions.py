"""translate user management permissions

Revision ID: 20260509_0005
Revises: 20260506_0004
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260509_0005"
down_revision = "20260506_0004"
branch_labels = None
depends_on = None


VIETNAMESE_LABELS = {
    "users.read": {
        "name": "Xem người dùng",
        "description": "Xem danh sách và chi tiết người dùng",
    },
    "users.update": {
        "name": "Cập nhật người dùng",
        "description": "Chỉnh sửa thông tin tài khoản người dùng",
    },
    "users.deactivate": {
        "name": "Khóa người dùng",
        "description": "Vô hiệu hóa tài khoản người dùng",
    },
    "users.delete": {
        "name": "Xóa người dùng",
        "description": "Xóa mềm tài khoản người dùng",
    },
}

ENGLISH_LABELS = {
    "users.read": {
        "name": "View users",
        "description": "View user lists and user details",
    },
    "users.update": {
        "name": "Update users",
        "description": "Edit user account information",
    },
    "users.deactivate": {
        "name": "Deactivate users",
        "description": "Deactivate user accounts",
    },
    "users.delete": {
        "name": "Delete users",
        "description": "Soft delete user accounts",
    },
}


def upgrade() -> None:
    _update_permission_labels(VIETNAMESE_LABELS)


def downgrade() -> None:
    _update_permission_labels(ENGLISH_LABELS)


def _update_permission_labels(labels: dict[str, dict[str, str]]) -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "permissions" not in inspector.get_table_names():
        return

    permissions = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    for code, label in labels.items():
        conn.execute(
            permissions.update()
            .where(permissions.c.code == code)
            .values(name=label["name"], description=label["description"])
        )
