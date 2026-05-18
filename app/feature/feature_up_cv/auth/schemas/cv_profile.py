from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class CVProfileBase(BaseModel):
    parser_file_url: str | None = None
    raw_file_url: str | None = None
    text_hashed: str | None = None
    embedding_vector_url: str | None = None


# ── Request ──────────────────────────────────────

class CVProfileCreate(CVProfileBase):
    pass


class CVProfileUpdate(BaseModel):
    parser_file_url: str | None = None
    raw_file_url: str | None = None
    text_hashed: str | None = None
    embedding_vector_url: str | None = None


# ── Response ─────────────────────────────────────

class CVProfileResponse(CVProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id_cv: int
    user_id: int
    created_at: datetime