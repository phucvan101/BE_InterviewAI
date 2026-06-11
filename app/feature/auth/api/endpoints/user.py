from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_superuser
from ...models.user import User
from ...schemas.user import (
    AuthUserResponse,
    PaginatedUsers,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    UserUpdatePassword,
    ForgotPasswordRequest,
    MessageResponse,
)
from ...services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await UserService(db).create(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT tokens",
)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await UserService(db).login(data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await UserService(db).refresh_token(data)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a new password",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await UserService(db).forgot_password(data.email)
    return MessageResponse(message="Nếu email tồn tại, mật khẩu mới đã được gửi.")


# ── Email Verification ─────────────────────────────────────────────────────────

import httpx
from fastapi import HTTPException

@router.get(
    "/verify-email",
    summary="Verify if an email exists using ZeroBounce API",
)
async def verify_email(
    email: str = Query(..., description="Email address to verify")
):
    from app.core.config import settings
    
    if not settings.ZEROBOUNCE_API_KEY:
        raise HTTPException(status_code=400, detail="Chưa cấu hình API Key cho ZeroBounce (ZEROBOUNCE_API_KEY).")
        
    url = f"https://api.zerobounce.net/v2/validate?api_key={settings.ZEROBOUNCE_API_KEY}&email={email}&ip_address="
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            # ZeroBounce trả về status: "valid", "invalid", "catch-all", "unknown", "spamtrap", "abuse", "do_not_mail"
            if "error" in data:
                raise HTTPException(status_code=400, detail=f"Lỗi từ ZeroBounce: {data['error']}")
                
            status = data.get("status")
            if status in ["valid", "catch-all"]:
                return {"deliverability": "DELIVERABLE", "status": status}
            elif status == "invalid":
                return {"deliverability": "UNDELIVERABLE", "status": status}
            else:
                return {"deliverability": "UNKNOWN", "status": status}
                
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Lỗi kết nối tới dịch vụ ZeroBounce.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi hệ thống khi kiểm tra email: {str(e)}")


# ── Current user ─────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=AuthUserResponse,
    summary="Get current authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AuthUserResponse:
    return await UserService(db).build_auth_user_response(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await UserService(db).update(current_user.id, data)


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password",
)
async def change_password(
    data: UserUpdatePassword,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await UserService(db).update_password(current_user.id, data)


# ── Admin — list & manage users ───────────────────────────────────────────────

@router.get(
    "/",
    response_model=PaginatedUsers,
    summary="[Admin] List all users with pagination",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedUsers:
    return await UserService(db).get_all(page=page, page_size=page_size)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="[Admin] Get user by ID",
)
async def get_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await UserService(db)._get_or_404(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="[Admin] Update a user",
)
async def update_user(
    user_id: int,
    data: UserUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await UserService(db).update(user_id, data)


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="[Admin] Deactivate a user",
)
async def deactivate_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await UserService(db).deactivate(user_id)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Soft delete a user (is_deleted=true)",
)
async def delete_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    await UserService(db).delete(user_id)
