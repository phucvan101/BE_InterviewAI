from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ──────────────────────────────────────────────────────────────
# Message Schemas
# ──────────────────────────────────────────────────────────────

class ConversationMessageBase(BaseModel):
    """Base schema cho message"""
    role: str  # "interviewer", "candidate", "system"
    content: str
    question: Optional[str] = None
    answer: Optional[str] = None


class ConversationMessageCreate(ConversationMessageBase):
    """Schema để tạo message"""
    pass


class ConversationMessageResponse(ConversationMessageBase):
    """Schema response cho message"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    created_at: datetime


# ──────────────────────────────────────────────────────────────
# Conversation Schemas
# ──────────────────────────────────────────────────────────────

class ConversationBase(BaseModel):
    """Base schema cho conversation"""
    job_position: Optional[str] = Field(default=None, description="Tên vị trí phỏng vấn")
    company_name: Optional[str] = Field(default=None, description="Tên công ty nếu có")
    job_description: Optional[str] = Field(default=None, description="Job description")
    cv_profile: Optional[str] = Field(default=None, description="CV profile của ứng viên")


class ConversationCreate(ConversationBase):
    """Schema để tạo conversation mới"""
    pass


class ConversationStartRequest(ConversationBase):
    """Schema để bắt đầu phiên phỏng vấn mới"""
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID trung gian (từ analysis_sessions.session_id) để lấy JD/CV raw text",
    )

    @model_validator(mode="after")
    def _validate_source(self):
        # Ưu tiên session_id; nếu không có thì bắt buộc nhập trực tiếp JD + CV (backward compatibility)
        if self.session_id:
            return self
        if not self.job_description or not self.cv_profile:
            raise ValueError("Cần cung cấp `session_id` hoặc cả `job_description` và `cv_profile`")
        return self


class ConversationResponse(BaseModel):
    """Schema response cho conversation"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str = Field(..., description="Unique session ID")
    user_id: int
    job_position: str
    company_name: Optional[str] = None
    job_description: str
    cv_profile: str
    status: str
    result: Optional[str] = None
    score: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    interview_duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = []


class ConversationListResponse(BaseModel):
    """Schema response cho list conversations"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    user_id: int
    job_position: str
    company_name: Optional[str] = None
    status: str
    score: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    interview_duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationPaginatedResponse(BaseModel):
    """Paginated response cho list conversations"""
    total: int
    page: int
    page_size: int
    items: list[ConversationListResponse]


# ──────────────────────────────────────────────────────────────
# Message Interaction Schemas
# ──────────────────────────────────────────────────────────────

class SendCandidateAnswerRequest(BaseModel):
    """Schema để ứng viên gửi câu trả lời"""
    answer: str = Field(..., min_length=1, description="Câu trả lời của ứng viên")


class GetNextQuestionResponse(BaseModel):
    """Schema response khi lấy câu hỏi tiếp theo"""
    session_id: str
    question: str = Field(..., description="Câu hỏi từ AI")
    message_id: int = Field(..., description="ID của message vừa tạo")


class InterviewResultResponse(BaseModel):
    """Schema response cho kết quả phỏng vấn"""
    session_id: str
    status: str
    score: Optional[float] = None
    result: Optional[dict] = None
    total_messages: int


class ScoreCriterion(BaseModel):
    """Điểm chi tiết cho một tiêu chí đánh giá"""
    score: int = Field(..., ge=0, le=100)
    evidence: str = Field(..., min_length=1)


class AiCoachInsight(BaseModel):
    """Nhận xét ngắn để FE render phần AI Coach"""
    type: str = Field(..., pattern="^(positive|warning|improvement)$")
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class KnowledgeGap(BaseModel):
    """Lỗ hổng kiến thức hoặc điểm yếu cần cải thiện"""
    title: str = Field(..., min_length=1)
    impact: str = Field(..., pattern="^(low|medium|high)$")
    evidence: str = Field(..., min_length=1)
    recommendation: str = Field(..., min_length=1)


class StudyPlanItem(BaseModel):
    """Một mục trong lộ trình ôn tập"""
    priority: int = Field(..., ge=1)
    topic: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    actions: list[str] = Field(default_factory=list)


class AnalysisScores(BaseModel):
    """Các nhóm điểm chính của báo cáo"""
    technical: ScoreCriterion
    communication: ScoreCriterion
    confidence: ScoreCriterion
    soft_skills: ScoreCriterion
    company_knowledge: ScoreCriterion


class AnalysisReportPayload(BaseModel):
    """Payload JSON do AI tạo và backend validate trước khi lưu"""
    overall_score: int = Field(..., ge=0, le=100)
    overall_grade: str = Field(..., min_length=1, max_length=10)
    level: str = Field(..., min_length=1, max_length=50)
    summary: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    scores: AnalysisScores
    ai_coach_insights: list[AiCoachInsight] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    knowledge_gaps: list[KnowledgeGap] = Field(default_factory=list)
    study_plan: list[StudyPlanItem] = Field(default_factory=list)


class ConversationAnalysisReportResponse(AnalysisReportPayload):
    """Response báo cáo phân tích kết quả phỏng vấn"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    conversation_id: int
    user_id: int
    job_position: str
    company_name: Optional[str] = None
    status: str
    total_messages: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    interview_duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ConversationAnalysisReportPaginatedResponse(BaseModel):
    """Paginated response cho danh sách báo cáo phân tích"""
    total: int
    page: int
    page_size: int
    items: list[ConversationAnalysisReportResponse]
