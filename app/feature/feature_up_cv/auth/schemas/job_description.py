from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class JobDescriptionBase(BaseModel):
    parser_file_url: str | None = None
    raw_file_url: str | None = None
    text_hashed: str | None = None


# ── Request ──────────────────────────────────────

class JobDescriptionCreate(JobDescriptionBase):
    pass


class JobDescriptionUpdate(BaseModel):
    parser_file_url: str | None = None
    raw_file_url: str | None = None
    text_hashed: str | None = None


# ── Response ─────────────────────────────────────

class JobDescriptionResponse(JobDescriptionBase):
    model_config = ConfigDict(from_attributes=True)

    id_jd: int
    user_id: int
    upload_at: datetime
