from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
    job_description: str = Field(..., description="Job description")
    cv_profile: str = Field(..., description="CV profile của ứng viên")


class ConversationCreate(ConversationBase):
    """Schema để tạo conversation mới"""
    pass


class ConversationStartRequest(ConversationBase):
    """Schema để bắt đầu phiên phỏng vấn mới"""
    pass


class ConversationResponse(BaseModel):
    """Schema response cho conversation"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str = Field(..., description="Unique session ID")
    user_id: int
    job_description: str
    cv_profile: str
    status: str
    result: Optional[str] = None
    score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = []


class ConversationListResponse(BaseModel):
    """Schema response cho list conversations"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    user_id: int
    status: str
    score: Optional[float] = None
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
