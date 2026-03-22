from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_superuser
from app.feature.auth.models.user import User
from app.feature.auth.schemas.user import (
    PaginatedUsers,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    UserUpdatePassword,
)
from app.feature.auth.services.user_service import UserService

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


# ── Current user ─────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return current_user


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
    summary="[Admin] Hard delete a user",
)
async def delete_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    await UserService(db).delete(user_id)
