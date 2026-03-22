from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.feature.auth.models.user import User
from app.feature.auth.schemas.user import (
    PaginatedUsers,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserUpdatePassword,
)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_all(self, page: int = 1, page_size: int = 20) -> PaginatedUsers:
        offset = (page - 1) * page_size
        total_result = await self.db.execute(select(func.count()).select_from(User))
        total = total_result.scalar_one()
        users_result = await self.db.execute(
            select(User).offset(offset).limit(page_size).order_by(User.created_at.desc())
        )
        users = list(users_result.scalars().all())
        return PaginatedUsers(total=total, page=page, page_size=page_size, items=users)

    # ── Commands ──────────────────────────────────────────────────────────────

    async def create(self, data: UserCreate) -> User:
        # Check uniqueness
        if await self.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        if await self.get_by_username(data.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        try:
            hashed_password = hash_password(data.password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hashed_password,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user_id: int, data: UserUpdate) -> User:
        user = await self._get_or_404(user_id)
        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != user.email:
            if await self.get_by_email(update_data["email"]):
                raise HTTPException(status_code=409, detail="Email already in use")

        if "username" in update_data and update_data["username"] != user.username:
            if await self.get_by_username(update_data["username"]):
                raise HTTPException(status_code=409, detail="Username already in use")

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_password(self, user_id: int, data: UserUpdatePassword) -> None:
        user = await self._get_or_404(user_id)
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect current password")
        try:
            user.hashed_password = hash_password(data.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        await self.db.flush()

    async def delete(self, user_id: int) -> None:
        user = await self._get_or_404(user_id)
        await self.db.delete(user)
        await self.db.flush()

    async def deactivate(self, user_id: int) -> User:
        user = await self._get_or_404(user_id)
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Account is deactivated")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh_token(self, data: RefreshTokenRequest) -> TokenResponse:
        try:
            payload = decode_token(data.refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Not a refresh token")
            user_id = int(payload["sub"])
        except (JWTError, ValueError, KeyError):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await self._get_or_404(user_id)
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Account is deactivated")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_or_404(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
