from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.feature.audit.schemas import PaginatedAuditLogs
from app.feature.audit.services import AuditLogService
from app.feature.admin.roles.schemas.role import (
    PaginatedRoles,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.feature.admin.roles.services.role_service import RoleService
from app.feature.auth.models.user import User

router = APIRouter(prefix="/admin/roles", tags=["Admin Roles"])


@router.get(
    "/permissions",
    response_model=list[PermissionResponse],
    summary="[Admin] List default permissions",
)
async def list_permissions(
    _: User = Depends(require_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionResponse]:
    return await RoleService(db).list_permissions()


@router.get(
    "/",
    response_model=PaginatedRoles,
    summary="[Admin] List roles",
)
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedRoles:
    return await RoleService(db).get_all(page=page, page_size=page_size)


@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create role from default permissions",
)
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(require_permission("roles.create")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    return await RoleService(db).create(data, actor=current_user)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    summary="[Admin] Get role detail",
)
async def get_role(
    role_id: int,
    _: User = Depends(require_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    return await RoleService(db)._get_or_404(role_id)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    summary="[Admin] Update role",
)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: User = Depends(require_permission("roles.update")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    return await RoleService(db).update(role_id, data, actor=current_user)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete role",
)
async def delete_role(
    role_id: int,
    current_user: User = Depends(require_permission("roles.delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await RoleService(db).delete(role_id, actor=current_user)


@router.get(
    "/{role_id}/audit-logs",
    response_model=PaginatedAuditLogs,
    summary="[Admin] Get role audit logs",
)
async def get_role_audit_logs(
    role_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("roles.read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAuditLogs:
    await RoleService(db)._get_or_404(role_id)
    return await AuditLogService(db).list_by_entity(
        entity_type="role",
        entity_id=role_id,
        page=page,
        page_size=page_size,
    )
