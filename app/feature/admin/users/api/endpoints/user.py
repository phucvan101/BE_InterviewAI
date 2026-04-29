from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_superuser
from app.feature.admin.users.models.user import User
from app.feature.admin.users.schemas.user import (
    AdminPaginatedUsers,
    AdminUserResponse,
    AdminUserUpdate,
)
from app.feature.admin.users.services.user_service import AdminUserService

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


@router.get(
    "/",
    response_model=AdminPaginatedUsers,
    summary="[Admin] List users for admin table",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    username: str | None = None, 
    email: str | None = None, 
    is_active: bool | None = None,
    auth_provider: str | None = None,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminPaginatedUsers:
    return await AdminUserService(db).get_all(page=page, page_size=page_size, username=username, email=email, is_active=is_active, auth_provider=auth_provider)


@router.get(
    "/{user_id}",
    response_model=AdminUserResponse,
    summary="[Admin] Get user detail",
)
async def get_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db)._get_or_404(user_id)


@router.patch(
    "/{user_id}",
    response_model=AdminUserResponse,
    summary="[Admin] Update user",
)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db).update(user_id, data)


@router.patch(
    "/{user_id}/deactivate",
    response_model=AdminUserResponse,
    summary="[Admin] Deactivate user",
)
async def deactivate_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db).deactivate(user_id)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Soft delete user (is_deleted=true)",
)
async def delete_user(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    await AdminUserService(db).delete(user_id)
