from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Base ─────────────────────────────────────────

class CompanyInfoBase(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    text_content: Optional[str] = None


# ── Request ──────────────────────────────────────

class CompanyInfoCreate(CompanyInfoBase):
    pass


class CompanyInfoUpdate(BaseModel):
    parser_file_url: Optional[str] = None
    raw_file_url: Optional[str] = None
    text_hashed: Optional[str] = None
    text_content: Optional[str] = None


# ── Response ─────────────────────────────────────

class CompanyInfoResponse(CompanyInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id_ci: int
    user_id: int
    upload_at: datetime
