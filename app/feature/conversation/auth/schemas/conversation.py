# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationBase(BaseModel):
    job_description: Optional[str] = Field(default=None, description="Job description")
    cv_profile: Optional[str] = Field(default=None, description="CV profile của ứng viên")


class ConversationCreate(ConversationBase):
    pass


class ConversationStartRequest(ConversationBase):
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID trung gian (từ analysis_sessions.session_id) để lấy JD/CV raw text",
    )

    @model_validator(mode="after")
    def _validate_source(self):
        if self.session_id:
            return self
        if not self.job_description or not self.cv_profile:
            raise ValueError("Cần cung cấp `session_id` hoặc cả `job_description` và `cv_profile`")
        return self


class ConversationResponse(BaseModel):
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
    messages: list = []


class ConversationListResponse(BaseModel):
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
    total: int
    page: int
    page_size: int
    items: list[ConversationListResponse]
