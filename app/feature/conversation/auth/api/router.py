# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.feature.conversation.auth.api.endpoints import (
    start_interview,
    list_interviews,
    get_interview,
    next_question,
    send_answer,
    end_interview,
    pause_resume,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

router.include_router(start_interview.router)
router.include_router(list_interviews.router)
router.include_router(get_interview.router)
router.include_router(next_question.router)
router.include_router(send_answer.router)
router.include_router(end_interview.router)
router.include_router(pause_resume.router)

__all__ = ["router"]
