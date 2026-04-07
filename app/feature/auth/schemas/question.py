from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class QuestionBase(BaseModel):
    content: str
    difficulty: str | None = Field(None, max_length=50)
    category: str | None = Field(None, max_length=100)


# ── Request ──────────────────────────────────────

class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    content: str | None = None
    difficulty: str | None = None
    category: str | None = None


# ── Response ─────────────────────────────────────

class QuestionResponse(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime