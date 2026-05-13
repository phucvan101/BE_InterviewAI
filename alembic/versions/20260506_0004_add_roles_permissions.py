"""add roles and permissions

Revision ID: 20260506_0004
Revises: 20260428_0003
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


USER_MANAGEMENT_PERMISSIONS = [
    {
        "code": "users.read",
        "name": "Xem người dùng",
        "description": "Xem danh sách và chi tiết người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.update",
        "name": "Cập nhật người dùng",
        "description": "Chỉnh sửa thông tin tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.deactivate",
        "name": "Khóa người dùng",
        "description": "Vô hiệu hóa tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.delete",
        "name": "Xóa người dùng",
        "description": "Xóa mềm tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = set(inspector.get_table_names())

    if "permissions" not in table_names:
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("module", sa.String(length=50), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_permissions_id"), "permissions", ["id"], unique=False)
        op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=False)
        op.create_index(op.f("ix_permissions_module"), "permissions", ["module"], unique=False)

    if "roles" not in table_names:
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
        op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=False)

    table_names = set(sa.inspect(conn).get_table_names())
    if "role_permissions" not in table_names:
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("role_id", "permission_id"),
        )

    if "user_roles" not in table_names:
        op.create_table(
            "user_roles",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "role_id"),
        )

    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("module", sa.String),
        sa.column("is_system", sa.Boolean),
    )
    existing_codes = set(
        conn.execute(sa.select(permissions_table.c.code)).scalars().all()
    )
    permissions_to_insert = [
        permission
        for permission in USER_MANAGEMENT_PERMISSIONS
        if permission["code"] not in existing_codes
    ]
    if permissions_to_insert:
        op.bulk_insert(permissions_table, permissions_to_insert)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    table_names = set(inspector.get_table_names())

    if "user_roles" in table_names:
        op.drop_table("user_roles")
    if "role_permissions" in table_names:
        op.drop_table("role_permissions")
    if "roles" in table_names:
        op.drop_index(op.f("ix_roles_name"), table_name="roles")
        op.drop_index(op.f("ix_roles_id"), table_name="roles")
        op.drop_table("roles")
    if "permissions" in table_names:
        op.drop_index(op.f("ix_permissions_module"), table_name="permissions")
        op.drop_index(op.f("ix_permissions_code"), table_name="permissions")
        op.drop_index(op.f("ix_permissions_id"), table_name="permissions")
        op.drop_table("permissions")
