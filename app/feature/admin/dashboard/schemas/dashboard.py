from datetime import date as date_type

from pydantic import BaseModel, EmailStr, Field


class AdminDashboardStats(BaseModel):
    total_interviews: int = Field(..., description="Tổng số phiên phỏng vấn")
    total_interviews_growth_percent: float = Field(
        ..., description="Tăng trưởng số phiên so với kỳ trước"
    )
    live_sessions: int = Field(..., description="Số phiên đang active")
    live_sessions_label: str = Field(..., description="Nhãn hiển thị cho card live sessions")
    success_rate: float = Field(..., description="Tỷ lệ phiên completed trên tổng phiên")
    success_rate_label: str = Field(..., description="Nhãn trạng thái success rate")
    average_score: float | None = Field(
        None,
        description="Điểm trung bình của các phiên có score, thang /100",
    )
    average_score_denominator: int = Field(100, description="Mẫu số hiển thị điểm trung bình")


class AdminDashboardActivityPoint(BaseModel):
    label: str = Field(..., description="Nhãn hiển thị trên chart")
    date: date_type = Field(..., description="Ngày đại diện cho điểm dữ liệu")
    total_interviews: int = Field(..., description="Số phiên tạo trong kỳ")
    completed_interviews: int = Field(..., description="Số phiên completed trong kỳ")


class AdminDashboardTopUser(BaseModel):
    user_id: int
    full_name: str | None = None
    username: str
    email: EmailStr
    avatar_url: str | None = None
    session_count: int


class AdminDashboardSystemUtilization(BaseModel):
    level: str = Field(..., description="low | normal | high")
    message: str


class AdminDashboardOverview(BaseModel):
    stats: AdminDashboardStats
    interview_activity_range: str = Field(..., description="week | month")
    interview_activity: list[AdminDashboardActivityPoint]
    top_interview_activity: list[AdminDashboardTopUser]
    system_utilization: AdminDashboardSystemUtilization
