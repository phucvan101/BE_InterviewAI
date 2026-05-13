from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserRow(BaseModel):
    """Compact row for admin data table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    full_name: str | None
    auth_provider: str
    is_active: bool
    is_deleted: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class AdminUserResponse(AdminUserRow):
    avatar_url: str | None
    google_id: str | None
    

class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

    full_name: str | None = Field(None, max_length=100)

    is_active: bool = True
    is_verified: bool = False

    auth_provider: str = "password"

class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str | None = Field(None, max_length=100)
    password: str | None = None 
    is_active: bool | None = None
    is_deleted: bool | None = None
    is_verified: bool | None = None


class AdminUserRolesUpdate(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class AdminPaginatedUsers(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminUserRow]
