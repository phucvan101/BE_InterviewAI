from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: EmailStr
    username: str
    avatar_url: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# Message summary (compact view for admin)
# ──────────────────────────────────────────────────────────────

class AdminMessageRow(BaseModel):
    """Compact message row for admin detail view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    question: Optional[str] = None
    answer: Optional[str] = None
    created_at: datetime


# ──────────────────────────────────────────────────────────────
# Analysis report (compact view for admin)
# ──────────────────────────────────────────────────────────────

class AdminAnalysisReportRow(BaseModel):
    """Compact analysis report for admin detail view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    overall_score: int
    overall_grade: str
    level: str
    summary: str
    tags: list
    scores: dict
    strengths: list
    weaknesses: list
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────
# Session row (for paginated list in admin table)
# ──────────────────────────────────────────────────────────────

class AdminSessionRow(BaseModel):
    """Compact session row for admin data table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    user_id: int
    candidate: Optional[AdminUserResponse] = None
    job_position: str
    company_name: Optional[str] = None
    status: str
    score: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    interview_duration_seconds: Optional[int] = None
    message_count: int = Field(default=0, description="Số lượng messages trong session")
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────
# Session detail (full info for admin detail page)
# ──────────────────────────────────────────────────────────────

class AdminSessionDetail(AdminSessionRow):
    """Full session detail including messages and analysis report."""

    job_description: str
    cv_profile: str
    result: Optional[str] = None
    messages: list[AdminMessageRow] = Field(default_factory=list)
    analysis_report: Optional[AdminAnalysisReportRow] = None
    candidate: Optional[AdminUserResponse] = None


# ──────────────────────────────────────────────────────────────
# Status update request
# ──────────────────────────────────────────────────────────────

class AdminSessionStatusUpdate(BaseModel):
    """Schema để admin cập nhật trạng thái session."""

    status: str = Field(
        ...,
        pattern="^(active|completed|paused)$",
        description="Trạng thái mới của session: active | completed | paused",
    )


# ──────────────────────────────────────────────────────────────
# Summary stats
# ──────────────────────────────────────────────────────────────

class AdminSessionStats(BaseModel):
    """Thống kê tổng hợp cho toàn bộ sessions (theo bộ filter hiện tại)."""

    total_sessions: int = Field(..., description="Tổng số phiên phỏng vấn")
    active_sessions: int = Field(..., description="Số phiên đang diễn ra (active)")
    completed_sessions: int = Field(..., description="Số phiên đã hoàn thành (completed)")
    paused_sessions: int = Field(..., description="Số phiên tạm dừng (paused)")
    average_score: Optional[float] = Field(
        None,
        description="Điểm trung bình của các phiên đã có điểm (None nếu chưa có phiên nào có điểm)",
    )


# ──────────────────────────────────────────────────────────────
# Paginated response
# ──────────────────────────────────────────────────────────────

class AdminPaginatedSessions(BaseModel):
    """Paginated response cho danh sách sessions."""

    total: int
    page: int
    page_size: int
    stats: AdminSessionStats = Field(..., description="Thống kê tổng hợp theo filter hiện tại")
    items: list[AdminSessionRow]
