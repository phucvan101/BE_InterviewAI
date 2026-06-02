import re
import secrets
import string
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
from ..models.user import User
from ..schemas.user import (
    AuthUserResponse,
    PaginatedUsers,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserUpdatePassword,
)
from app.feature.auth.services.google_oauth_service import GoogleOAuthService
from app.feature.admin.roles.models.role import Permission, Role, role_permissions, user_roles
from app.core.email import send_email_async, generate_forgot_password_html


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
        if user.auth_provider == "google":
            raise HTTPException(status_code=400, detail="Tài khoản đăng nhập bằng Google không thể đổi mật khẩu.")
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect current password")
        try:
            user.hashed_password = hash_password(data.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        await self.db.flush()

    async def delete(self, user_id: int) -> None:
        user = await self._get_or_404(user_id)
        user.is_deleted = True
        user.is_active = False
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
                detail="Sai email hoặc mật khẩu",
            )
        if user.is_deleted:
            raise HTTPException(status_code=400, detail="Tài khoản đã bị xóa")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Tài khoản đã bị khóa")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
            user=await self.build_auth_user_response(user),
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
        if user.is_deleted:
            raise HTTPException(status_code=400, detail="Tài khoản đã bị xóa")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Tài khoản đã bị khóa")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
            user=await self.build_auth_user_response(user),
        )

    async def login_with_google_id_token(self, id_token: str) -> TokenResponse:
        payload = await GoogleOAuthService.verify_id_token(id_token)

        email = payload.get("email")
        email_verified = payload.get("email_verified")
        google_sub = payload.get("sub")

        if not email or not google_sub:
            raise HTTPException(status_code=400, detail="Google token missing required fields")

        if str(email_verified).lower() != "true":
            raise HTTPException(status_code=400, detail="Google email is not verified")

        user = await self.get_by_email(email)
        if user:
            if user.is_deleted:
                raise HTTPException(status_code=400, detail="Tài khoản đã bị xóa")
            if not user.is_active:
                raise HTTPException(status_code=400, detail="Tài khoản đã bị khóa")
            if not user.google_id:
                user.google_id = google_sub
                if not user.avatar_url:
                    user.avatar_url = payload.get("picture")
                if user.auth_provider != "google":
                    user.auth_provider = "google"
                await self.db.flush()
        else:
            username = await self._generate_unique_username(
                base=(payload.get("given_name") or payload.get("name") or email.split("@")[0])
            )
            random_password = secrets.token_urlsafe(32)
            user = User(
                email=email,
                username=username,
                full_name=payload.get("name"),
                hashed_password=hash_password(random_password),
                auth_provider="google",
                google_id=google_sub,
                avatar_url=payload.get("picture"),
                is_verified=True,
            )
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
            user=await self.build_auth_user_response(user),
        )

    async def login_with_google_code(self, code: str) -> TokenResponse:
        tokens = await GoogleOAuthService.exchange_code_for_tokens(code)
        id_token = tokens.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="Google token exchange missing id_token")
        return await self.login_with_google_id_token(id_token)

    async def forgot_password(self, email: str) -> None:
        user = await self.get_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="Email không tồn tại trong hệ thống")
            
        if user.auth_provider == "google":
            raise HTTPException(
                status_code=400,
                detail="Tài khoản này được đăng ký bằng Google. Vui lòng đăng nhập bằng Google thay vì dùng mật khẩu."
            )
            
        # Generate new random password (8 chars)
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for i in range(8))
        
        # Hash and update
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        
        # Send email
        html_content = generate_forgot_password_html(new_password)
        email_sent = await send_email_async(
            to_email=user.email,
            subject="InterviewAI - Khôi Phục Mật Khẩu",
            html_content=html_content
        )
        
        if not email_sent:
            raise HTTPException(status_code=500, detail="Không thể gửi email. Vui lòng thử lại sau.")

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_or_404(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    async def build_auth_user_response(self, user: User) -> AuthUserResponse:
        roles_result = await self.db.execute(
            select(Role.name)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id)
            .order_by(Role.name)
        )
        permissions_result = await self.db.execute(
            select(Permission.code)
            .join(role_permissions, Permission.id == role_permissions.c.permission_id)
            .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
            .where(user_roles.c.user_id == user.id)
            .order_by(Permission.code)
        )
        roles = list(roles_result.scalars().all()) # scalars() lấy trực tiếp giá trị thay vì tuple.
        permissions = list(permissions_result.scalars().unique().all()) # gộp các quyền bị trùng nhau 
        can_access_admin = user.is_superuser or bool(permissions)

        return AuthUserResponse.model_validate(user).model_copy(
            update={
                "roles": roles,
                "permissions": permissions,
                "can_access_admin": can_access_admin,
            }
        )

    async def _generate_unique_username(self, base: str) -> str:
        base = self._normalize_username_base(base)
        candidate = base
        for _ in range(20):
            if not await self.get_by_username(candidate):
                return candidate
            candidate = f"{base}{secrets.randbelow(10000)}"
        raise HTTPException(status_code=500, detail="Failed to generate unique username")

    @staticmethod
    def _normalize_username_base(base: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", base or "")
        if len(cleaned) < 3:
            cleaned = "user"
        return cleaned[:50]
