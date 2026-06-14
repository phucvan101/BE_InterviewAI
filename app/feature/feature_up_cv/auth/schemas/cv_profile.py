from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class CVProfileBase(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    embedding_vector_url: Optional[str] = None


# ── Request ──────────────────────────────────────

class CVProfileCreate(CVProfileBase):
    pass


class CVProfileUpdate(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    embedding_vector_url: Optional[str] = None


# ── Response ─────────────────────────────────────

class CVProfileResponse(CVProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id_cv: int
    user_id: int
    created_at: datetime