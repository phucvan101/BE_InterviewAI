from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


# ── Base ─────────────────────────────────────────

class AnalysisSessionBase(BaseModel):
    id_cv: int
    id_jd: int
    id_ci: Optional[int] = None
    cv_raw_text: Optional[str] = None
    jd_raw_text: Optional[str] = None
    ci_raw_text: Optional[str] = None
    score: Optional[float] = None
    experience_score: Optional[float] = None
    skills_score: Optional[float] = None
    education_score: Optional[float] = None
    companyfit_score: Optional[float] = None
    result_analysis_file_url: Optional[str] = None


# ── Request ──────────────────────────────────────

class AnalysisSessionCreate(AnalysisSessionBase):
    pass


class AnalysisSessionUpdate(BaseModel):
    cv_raw_text: Optional[str] = None
    jd_raw_text: Optional[str] = None
    ci_raw_text: Optional[str] = None
    score: Optional[float] = None
    experience_score: Optional[float] = None
    skills_score: Optional[float] = None
    education_score: Optional[float] = None
    companyfit_score: Optional[float] = None
    result_analysis_file_url: Optional[str] = None
    id_ci: Optional[int] = None


# ── Response ─────────────────────────────────────

class AnalysisSessionResponse(AnalysisSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id_session: int
    user_id: int
    create_at: datetime
