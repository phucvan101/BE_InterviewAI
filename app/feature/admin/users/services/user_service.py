from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.admin.users.models.user import User
from app.feature.admin.users.schemas.user import AdminPaginatedUsers, AdminUserUpdate


class AdminUserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_all(self, page: int = 1, page_size: int = 20, username: str | None = None, email: str | None = None, is_active: bool | None = None, auth_provider: str | None = None) -> AdminPaginatedUsers:
        offset = (page - 1) * page_size

        stmt = select(User)
        filters = []
        filters.extend([
            User.is_superuser == False, # loại bỏ tài khoản admin
            User.is_deleted == False # loại bỏ tài khoản đã xóa
        ])

        if username:
            filters.append(User.username.ilike(f"%{username}%"))
        if email:
            filters.append(User.email.ilike(f"%{email}%"))
        if is_active is not None:
            filters.append(User.is_active == is_active)
        if auth_provider is not None:
            filters.append(User.auth_provider == auth_provider)
        if filters:
            stmt = stmt.where(*filters)

        # ✅ Đếm đúng theo filter
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # ✅ Query đúng theo filter
        users_result = await self.db.execute(
            stmt.offset(offset).limit(page_size).order_by(User.created_at.desc())
        )
        users = list(users_result.scalars().all())

        return AdminPaginatedUsers(total=total, page=page, page_size=page_size, items=users)
    
    async def update(self, user_id: int, data: AdminUserUpdate) -> User:
        user = await self._get_or_404(user_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != user.email:
            if await self.get_by_email(update_data["email"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

        if "username" in update_data and update_data["username"] != user.username:
            if await self.get_by_username(update_data["username"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def deactivate(self, user_id: int) -> User:
        user = await self._get_or_404(user_id)
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: int) -> None:
        user = await self._get_or_404(user_id)
        user.is_deleted = True
        user.is_active = False
        await self.db.flush()

    async def _get_or_404(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
