from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_superuser, require_permission
from app.feature.audit.schemas import PaginatedAuditLogs
from app.feature.audit.services import AuditLogService
from app.feature.admin.roles.services.role_service import RoleService
from app.feature.admin.users.models.user import User
from app.feature.admin.roles.schemas.role import RoleResponse
from app.feature.admin.users.schemas.user import AdminUserCreate
from app.feature.admin.users.schemas.user import (
    AdminPaginatedUsers,
    AdminUserResponse,
    AdminUserRolesUpdate,
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
    username: Optional[str] = None, 
    email: Optional[str] = None, 
    is_active: Optional[bool] = None,
    auth_provider: Optional[str] = None,
    _: User = Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
) -> AdminPaginatedUsers:
    return await AdminUserService(db).get_all(page=page, page_size=page_size, username=username, email=email, is_active=is_active, auth_provider=auth_provider)


@router.post(
    "/",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create user",
)
async def create_user(
    data: AdminUserCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db).create(data, actor=current_user)


@router.get(
    "/{user_id}",
    response_model=AdminUserResponse,
    summary="[Admin] Get user detail",
)
async def get_user(
    user_id: int,
    _: User = Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db)._get_or_404(user_id)


@router.get(
    "/{user_id}/roles",
    response_model=list[RoleResponse],
    summary="[Admin] Get user roles",
)
async def get_user_roles(
    user_id: int,
    _: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[RoleResponse]:
    return await RoleService(db).get_user_roles(user_id)


@router.patch(
    "/{user_id}",
    response_model=AdminUserResponse,
    summary="[Admin] Update user",
)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    current_user: User = Depends(require_permission("users.update")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db).update(user_id, data, actor=current_user)


@router.patch(
    "/{user_id}/roles",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Assign roles to user",
)
async def update_user_roles(
    user_id: int,
    data: AdminUserRolesUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    await RoleService(db).set_user_roles(user_id, data.role_ids, actor=current_user)


@router.patch(
    "/{user_id}/deactivate",
    response_model=AdminUserResponse,
    summary="[Admin] Deactivate user",
)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.deactivate")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    return await AdminUserService(db).deactivate(user_id, actor=current_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Soft delete user (is_deleted=true)",
)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_permission("users.delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await AdminUserService(db).delete(user_id, actor=current_user)


@router.get(
    "/{user_id}/audit-logs",
    response_model=PaginatedAuditLogs,
    summary="[Admin] Get user audit logs",
)
async def get_user_audit_logs(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("users.read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAuditLogs:
    await AdminUserService(db)._get_or_404(user_id)
    return await AuditLogService(db).list_by_entity(
        entity_type="user",
        entity_id=user_id,
        page=page,
        page_size=page_size,
    )
