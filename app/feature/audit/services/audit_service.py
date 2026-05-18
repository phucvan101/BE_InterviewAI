from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.feature.audit.models.audit_log import AuditLog
from app.feature.audit.schemas.audit_log import PaginatedAuditLogs
from app.feature.auth.models.user import User


def normalize_for_audit(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_for_audit(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_for_audit(item) for key, item in value.items()}
    return value


def diff_dicts(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    old_data: dict[str, Any] = {}
    new_data: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = normalize_for_audit(before.get(key))
        after_value = normalize_for_audit(after.get(key))
        if before_value != after_value:
            old_data[key] = before_value
            new_data[key] = after_value
    return old_data, new_data


class AuditLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_change(
        self,
        *,
        actor: User | None,
        entity_type: str,
        entity_id: int,
        action: str,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor_user_id=actor.id if actor else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_data=normalize_for_audit(old_data) if old_data is not None else None,
            new_data=normalize_for_audit(new_data) if new_data is not None else None,
            extra_data=normalize_for_audit(extra_data) if extra_data is not None else None,
        )
        self.db.add(audit_log)
        await self.db.flush()
        await self.db.refresh(audit_log)
        return audit_log

    async def list_by_entity(
        self,
        *,
        entity_type: str,
        entity_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedAuditLogs:
        offset = (page - 1) * page_size

        base_stmt = select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        total_result = await self.db.execute(select(func.count()).select_from(base_stmt.subquery()))
        total = total_result.scalar_one()

        result = await self.db.execute(
            base_stmt
            .options(joinedload(AuditLog.actor))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return PaginatedAuditLogs(total=total, page=page, page_size=page_size, items=items)
