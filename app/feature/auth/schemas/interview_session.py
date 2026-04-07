from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class InterviewSessionBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None


# ── Request ──────────────────────────────────────

class InterviewSessionCreate(InterviewSessionBase):
    cv_profile_id: int


class InterviewSessionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


# ── Response ─────────────────────────────────────

class InterviewSessionResponse(InterviewSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    cv_profile_id: int
    created_at: datetime