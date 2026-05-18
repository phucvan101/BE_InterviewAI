from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.audit.services import AuditLogService, diff_dicts
from app.feature.admin.users.models.user import User
from app.feature.admin.users.schemas.user import AdminPaginatedUsers, AdminUserUpdate, AdminUserCreate
from app.core.security import hash_password

import logging
logger = logging.getLogger(__name__)


class AdminUserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit_service = AuditLogService(db)

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
        # ✅ Log params nhận được
        logger.debug(f"get_all params: page={page}, page_size={page_size}, username={repr(username)}, email={repr(email)}, is_active={is_active}, auth_provider={auth_provider}")

        
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
        
        # ✅ Log câu SQL thực tế
        logger.debug(f"SQL: {stmt.compile(compile_kwargs={'literal_binds': True})}")

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
    
    
    async def create(self, data: AdminUserCreate, actor: User | None = None) -> User:

        # check username
        if await self.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        # check email
        if await self.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            is_active=data.is_active,
            is_verified=data.is_verified,
            auth_provider=data.auth_provider,
            is_deleted=False,
            is_superuser=False,
        )

        self.db.add(user)

        await self.db.flush()
        await self.db.refresh(user)
        await self.audit_service.log_change(
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            action="create",
            new_data=self._serialize_user(user),
        )

        return user
    
    
    async def update(self, user_id: int, data: AdminUserUpdate, actor: User | None = None) -> User:
        user = await self._get_or_404(user_id)
        before_state = self._serialize_user(user)
        update_data = data.model_dump(exclude_unset=True)
        forbidden_fields = {"is_superuser"}
        if forbidden_fields.intersection(update_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update protected user fields",
            )

        if "email" in update_data and update_data["email"] != user.email:
            if await self.get_by_email(update_data["email"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

        if "username" in update_data and update_data["username"] != user.username:
            if await self.get_by_username(update_data["username"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)
        after_state = self._serialize_user(user)
        old_data, new_data = diff_dicts(before_state, after_state)
        if new_data:
            await self.audit_service.log_change(
                actor=actor,
                entity_type="user",
                entity_id=user.id,
                action="update",
                old_data=old_data,
                new_data=new_data,
            )
        return user

    async def deactivate(self, user_id: int, actor: User | None = None) -> User:
        user = await self._get_or_404(user_id)
        before_state = self._serialize_user(user)
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        after_state = self._serialize_user(user)
        old_data, new_data = diff_dicts(before_state, after_state)
        if new_data:
            await self.audit_service.log_change(
                actor=actor,
                entity_type="user",
                entity_id=user.id,
                action="deactivate",
                old_data=old_data,
                new_data=new_data,
            )
        return user

    async def delete(self, user_id: int, actor: User | None = None) -> None:
        user = await self._get_or_404(user_id)
        before_state = self._serialize_user(user)
        user.is_deleted = True
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        after_state = self._serialize_user(user)
        old_data, new_data = diff_dicts(before_state, after_state)
        if new_data:
            await self.audit_service.log_change(
                actor=actor,
                entity_type="user",
                entity_id=user.id,
                action="delete",
                old_data=old_data,
                new_data=new_data,
            )

    async def _get_or_404(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    @staticmethod
    def _serialize_user(user: User) -> dict[str, object]:
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "auth_provider": user.auth_provider,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "is_deleted": user.is_deleted,
            "is_superuser": user.is_superuser,
            "is_verified": user.is_verified,
            "google_id": user.google_id,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
