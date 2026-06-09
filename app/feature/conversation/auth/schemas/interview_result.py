# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import BaseModel, Field


class SendCandidateAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="Câu trả lời của ứng viên")


class GetNextQuestionResponse(BaseModel):
    session_id: str
    question: str = Field(..., description="Câu hỏi từ AI")
    message_id: int = Field(..., description="ID của message vừa tạo")


class InterviewResultResponse(BaseModel):
    session_id: str
    status: str
    score: Optional[float] = None
    result: Optional[dict] = None
    total_messages: int
