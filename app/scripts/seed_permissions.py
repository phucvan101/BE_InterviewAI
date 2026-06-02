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