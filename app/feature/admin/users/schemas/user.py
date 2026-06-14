from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserRow(BaseModel):
    """Compact row for admin data table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    full_name: str | None
    avatar_url: str | None = None
    auth_provider: str
    is_active: bool
    is_deleted: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    interview_count: int = 0


class AdminUserResponse(AdminUserRow):
    google_id: str | None
    

class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

    full_name: Optional[str] = Field(None, max_length=100)

    is_active: bool = True
    is_verified: bool = False

    auth_provider: str = "password"

class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = None 
    is_active: Optional[bool] = None
    is_deleted: Optional[bool] = None
    is_verified: Optional[bool] = None


class AdminUserRolesUpdate(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class AdminPaginatedUsers(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminUserRow]
