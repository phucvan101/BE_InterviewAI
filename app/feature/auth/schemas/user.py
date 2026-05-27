from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BCRYPT_MAX_PASSWORD_BYTES = 72


# ── Base ─────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=100)


# ── Request schemas ───────────────────────────────────────────────────────────

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes (UTF-8)")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)


class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def new_password_max_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes (UTF-8)")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_deleted: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class AuthUserResponse(UserResponse):
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    can_access_admin: bool = False


class UserPublic(BaseModel):
    """Minimal public-safe user info."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: Optional[str]


# ── Auth schemas ──────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[AuthUserResponse] = None


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Google OAuth schemas ──────────────────────────────────────────────────────

class GoogleIdTokenRequest(BaseModel):
    id_token: str = Field(..., min_length=10)


class GoogleCodeRequest(BaseModel):
    code: str = Field(..., min_length=5)


class GoogleAuthUrlResponse(BaseModel):
    url: str


# ── Pagination wrapper ────────────────────────────────────────────────────────

class PaginatedUsers(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserResponse]
