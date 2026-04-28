from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class CVProfileBase(BaseModel):
    title: str = Field(..., max_length=255)
    summary: str | None = None
    file_url: str | None = None


# ── Request ──────────────────────────────────────

class CVProfileCreate(CVProfileBase):
    pass


class CVProfileUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    file_url: str | None = None


# ── Response ─────────────────────────────────────

class CVProfileResponse(CVProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime