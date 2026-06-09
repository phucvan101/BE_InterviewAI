# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import InterviewResultResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{session_id}/end",
    response_model=InterviewResultResponse,
    summary="Kết thúc phiên phỏng vấn",
)
async def end_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewResultResponse:
    logger.info(f"[end_interview] Ending interview for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[end_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[end_interview] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status != "active":
        logger.warning(f"[end_interview] Conversation not active: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )

    try:
        from app.feature.conversation.interview_agent.agent import interview_agent

        logger.info(f"[end_interview] Evaluating interview results for session_id={session_id}")
        evaluation = await interview_agent.evaluate_interview(
            job_description=conversation.job_description,
            cv_profile=conversation.cv_profile,
            conversation_id=conversation.id,
        )

        score = evaluation.get("fit_score", 0)
        logger.info(f"[end_interview] Interview evaluation complete: score={score}")
        await service.end_conversation(
            conversation.id,
            result=evaluation,
            score=score,
        )
        await db.commit()

        messages = await service.get_conversation_messages(conversation.id)
        logger.info(f"[end_interview] Interview ended successfully: total_messages={len(messages)}")

        return InterviewResultResponse(
            session_id=session_id,
            status=conversation.status,
            score=score,
            result=evaluation,
            total_messages=len(messages),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"[end_interview] Error ending interview: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kết thúc phỏng vấn: {str(e)}",
        )
