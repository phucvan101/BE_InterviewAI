from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class JobDescriptionBase(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    embedding_vector_url: Optional[str] = None


# ── Request ──────────────────────────────────────

class JobDescriptionCreate(JobDescriptionBase):
    pass


class JobDescriptionUpdate(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    embedding_vector_url: Optional[str] = None


# ── Response ─────────────────────────────────────

class JobDescriptionResponse(JobDescriptionBase):
    model_config = ConfigDict(from_attributes=True)

    id_jd: int
    user_id: int
    upload_at: datetime
