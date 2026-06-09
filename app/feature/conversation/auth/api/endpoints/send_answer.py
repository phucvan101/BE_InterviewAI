# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import SendCandidateAnswerRequest, GetNextQuestionResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{session_id}/answer",
    response_model=GetNextQuestionResponse,
    summary="Gửi câu trả lời",
)
async def send_answer(
    session_id: str,
    request: SendCandidateAnswerRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GetNextQuestionResponse:
    logger.debug(f"[send_answer] Receiving answer for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[send_answer] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[send_answer] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status != "active":
        logger.warning(f"[send_answer] Conversation not active: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )

    try:
        from app.feature.conversation.interview_agent.agent import interview_agent

        await service.add_message(
            conversation_id=conversation.id,
            role="candidate",
            content=request.answer,
            answer=request.answer,
        )

        logger.info(f"[send_answer] Generating next question based on answer")
        question = await interview_agent.generate_question(
            job_description=conversation.job_description,
            cv_profile=conversation.cv_profile,
            conversation_id=conversation.id,
            previous_answer=request.answer,
        )

        message = await service.add_message(
            conversation_id=conversation.id,
            role="interviewer",
            content=question,
            question=question,
        )
        await db.commit()

        logger.info(f"[send_answer] Next question generated: message_id={message.id}")
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"[send_answer] Error processing answer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gửi câu trả lời: {str(e)}",
        )
