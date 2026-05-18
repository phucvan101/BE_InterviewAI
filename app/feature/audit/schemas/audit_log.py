from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AuditActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    entity_type: str
    entity_id: int
    action: str
    old_data: dict | None
    new_data: dict | None
    extra_data: dict | None
    created_at: datetime
    actor: AuditActorResponse | None = None


class PaginatedAuditLogs(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]