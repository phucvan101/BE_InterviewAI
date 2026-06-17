import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal 

PERMISSIONS = [
    {
        "code": "sessions.read",
        "name": "Xem phiên phỏng vấn",
        "description": "Xem danh sách và chi tiết phiên phỏng vấn",
        "module": "sessions",
        "is_system": True,
    },
    {
        "code": "sessions.delete",
        "name": "Xóa phiên phỏng vấn",
        "description": "Xóa phiên phỏng vấn và toàn bộ dữ liệu liên quan",
        "module": "sessions",
        "is_system": True,
    },

    # Users
    {
        "code": "users.read",
        "name": "Xem người dùng",
        "description": "Xem danh sách và thông tin chi tiết người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.create",
        "name": "Tạo người dùng",
        "description": "Tạo mới tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.update",
        "name": "Cập nhật người dùng",
        "description": "Chỉnh sửa thông tin người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.delete",
        "name": "Xóa người dùng",
        "description": "Xóa tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },
    {
        "code": "users.deactivate",
        "name": "Vô hiệu hóa người dùng",
        "description": "Khóa hoặc vô hiệu hóa tài khoản người dùng",
        "module": "users",
        "is_system": True,
    },

    # Roles
    {
        "code": "roles.read",
        "name": "Xem vai trò",
        "description": "Xem danh sách và chi tiết vai trò",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.create",
        "name": "Tạo vai trò",
        "description": "Tạo mới vai trò và phân quyền",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.update",
        "name": "Cập nhật vai trò",
        "description": "Chỉnh sửa thông tin và quyền của vai trò",
        "module": "roles",
        "is_system": True,
    },
    {
        "code": "roles.delete",
        "name": "Xóa vai trò",
        "description": "Xóa vai trò khỏi hệ thống",
        "module": "roles",
        "is_system": True,
    },
    
]

async def seed():
    async with AsyncSessionLocal() as session:
        for perm in PERMISSIONS:
            result = await session.execute(text("""
                SELECT 1 FROM permissions WHERE code = :code
            """), {"code": perm["code"]})

            if result.scalar_one_or_none():
                print(f"⏭️  Skip (exists): {perm['code']}")
                continue

            await session.execute(text("""
                INSERT INTO permissions (code, name, description, module, is_system)
                VALUES (:code, :name, :description, :module, :is_system)
            """), perm)
            print(f"✅ Added: {perm['code']}")

        await session.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(seed())