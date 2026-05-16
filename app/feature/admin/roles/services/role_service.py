from fastapi import HTTPException, status
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.feature.audit.services import AuditLogService, diff_dicts
from app.feature.admin.roles.constants import DEFAULT_PERMISSION_CODES
from app.feature.admin.roles.models.role import Permission, Role, role_permissions, user_roles
from app.feature.admin.roles.schemas.role import PaginatedRoles, RoleCreate, RoleUpdate
from app.feature.auth.models.user import User


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit_service = AuditLogService(db)

    async def list_permissions(self) -> list[Permission]:
        result = await self.db.execute(select(Permission).order_by(Permission.module, Permission.code))
        return list(result.scalars().all())

    async def get_all(self, page: int = 1, page_size: int = 20) -> PaginatedRoles:
        offset = (page - 1) * page_size
        total_result = await self.db.execute(select(func.count()).select_from(Role))
        total = total_result.scalar_one()
        roles_result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .offset(offset)
            .limit(page_size)
            .order_by(Role.created_at.desc())
        )
        roles = list(roles_result.scalars().all())
        return PaginatedRoles(total=total, page=page, page_size=page_size, items=roles)

    async def create(self, data: RoleCreate, actor: User | None = None) -> Role:
        if await self._get_by_name(data.name):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")

        permissions = await self._get_permissions_by_codes(data.permission_codes)
        role = Role(
            name=data.name,
            description=data.description,
            permissions=permissions,
        )
        self.db.add(role)
        await self.db.flush()
        role = await self._get_or_404(role.id)
        await self.audit_service.log_change(
            actor=actor,
            entity_type="role",
            entity_id=role.id,
            action="create",
            new_data=self._serialize_role(role),
        )
        return role

    async def update(self, role_id: int, data: RoleUpdate, actor: User | None = None) -> Role:
        role = await self._get_or_404(role_id)
        before_state = self._serialize_role(role)
        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != role.name:
            if await self._get_by_name(update_data["name"]):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")
            role.name = update_data["name"]

        if "description" in update_data:
            role.description = update_data["description"]

        if data.permission_codes is not None:
            role.permissions = await self._get_permissions_by_codes(data.permission_codes)

        await self.db.flush()
        role = await self._get_or_404(role.id)
        after_state = self._serialize_role(role)
        old_data, new_data = diff_dicts(before_state, after_state)
        if new_data:
            await self.audit_service.log_change(
                actor=actor,
                entity_type="role",
                entity_id=role.id,
                action="update",
                old_data=old_data,
                new_data=new_data,
            )
        return role

    async def delete(self, role_id: int, actor: User | None = None) -> None:
        role = await self._get_or_404(role_id)
        if role.is_system:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System role cannot be deleted")

        before_state = self._serialize_role(role)
        await self.db.delete(role)
        await self.db.flush()
        await self.audit_service.log_change(
            actor=actor,
            entity_type="role",
            entity_id=role_id,
            action="delete",
            old_data=before_state,
        )

    async def set_user_roles(self, user_id: int, role_ids: list[int], actor: User | None = None) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        current_role_ids_result = await self.db.execute(
            select(user_roles.c.role_id).where(user_roles.c.user_id == user_id)
        )
        current_role_ids = sorted(set(current_role_ids_result.scalars().all()))
        next_role_ids = sorted(set(role_ids))

        if next_role_ids:
            roles_result = await self.db.execute(select(Role.id).where(Role.id.in_(next_role_ids)))
            existing_role_ids = set(roles_result.scalars().all())
            missing_role_ids = sorted(set(next_role_ids) - existing_role_ids)
            if missing_role_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role not found: {missing_role_ids}",
                )

        if current_role_ids == next_role_ids:
            return

        await self.db.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
        if next_role_ids:
            await self.db.execute(
                insert(user_roles),
                [{"user_id": user_id, "role_id": role_id} for role_id in next_role_ids],
            )
        await self.db.flush()
        await self.audit_service.log_change(
            actor=actor,
            entity_type="user",
            entity_id=user_id,
            action="roles.update",
            old_data={"role_ids": current_role_ids},
            new_data={"role_ids": next_role_ids},
        )

    async def get_user_roles(self, user_id: int) -> list[Role]:
        user = await self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        result = await self.db.execute(
            select(Role)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .options(selectinload(Role.permissions))
            .where(user_roles.c.user_id == user_id)
            .order_by(Role.name)
        )
        return list(result.scalars().all())

    async def _get_by_name(self, name: str) -> Role | None:
        result = await self.db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def _get_or_404(self, role_id: int) -> Role:
        result = await self.db.execute(
            select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        )
        role = result.scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return role

    async def _get_permissions_by_codes(self, permission_codes: list[str]) -> list[Permission]:
        unique_codes = sorted(set(permission_codes))
        invalid_codes = sorted(set(unique_codes) - DEFAULT_PERMISSION_CODES) #  được sử dụng để xác thực permission codes trước khi lưu vào database.
        if invalid_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission code: {invalid_codes}",
            )

        if not unique_codes:
            return []

        result = await self.db.execute(select(Permission).where(Permission.code.in_(unique_codes)))
        permissions = list(result.scalars().all())
        found_codes = {permission.code for permission in permissions}
        missing_codes = sorted(set(unique_codes) - found_codes)
        if missing_codes:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Default permission is not seeded: {missing_codes}",
            )
        return permissions

    @staticmethod
    def _serialize_role(role: Role) -> dict[str, object]:
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "permission_codes": sorted(permission.code for permission in role.permissions),
            "created_at": role.created_at,
            "updated_at": role.updated_at,
        }
