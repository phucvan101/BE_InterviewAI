# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.conversation.auth.api.endpoints.rate_limiter import require_question_rate_limit
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import GetNextQuestionResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{session_id}/next-question",
    response_model=GetNextQuestionResponse,
    summary="Lấy câu hỏi tiếp theo",
)
async def get_next_question_get(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GetNextQuestionResponse:
    require_question_rate_limit(current_user.id)
    return await _generate_next_question(session_id, current_user, db)


@router.post(
    "/{session_id}/next-question",
    response_model=GetNextQuestionResponse,
    summary="Lấy câu hỏi tiếp theo",
)
async def get_next_question_post(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GetNextQuestionResponse:
    require_question_rate_limit(current_user.id)
    return await _generate_next_question(session_id, current_user, db)


async def _generate_next_question(
    session_id: str,
    current_user: User,
    db: AsyncSession,
) -> GetNextQuestionResponse:
    logger.debug(f"[get_next_question] Getting next question for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[get_next_question] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[get_next_question] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status != "active":
        logger.warning(f"[get_next_question] Conversation not active: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn không còn hoạt động",
        )

    try:
        from app.feature.conversation.interview_agent.agent import interview_agent

        last_message = await service.get_last_message(conversation.id)

        if not last_message or last_message.role == "candidate":
            if last_message:
                logger.info(f"[get_next_question] Generating next question after candidate answer")
                question = await interview_agent.generate_question(
                    job_description=conversation.job_description,
                    cv_profile=conversation.cv_profile,
                    conversation_id=conversation.id,
                    db=db,
                    analysis_result=conversation.analysis_data,
                    previous_answer=last_message.answer,
                )
            else:
                logger.info(f"[get_next_question] Generating initial question for session_id={session_id}")
                question = await interview_agent.generate_question(
                    job_description=conversation.job_description,
                    cv_profile=conversation.cv_profile,
                    conversation_id=conversation.id,
                    db=db,
                    analysis_result=conversation.analysis_data,
                )
        else:
            logger.warning(f"[get_next_question] Waiting for candidate answer in session_id={session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chờ ứng viên trả lời câu hỏi trước",
            )

        message = await service.add_message(
            conversation_id=conversation.id,
            role="interviewer",
            content=question,
            question=question,
        )
        await db.commit()

        logger.info(f"[get_next_question] Question generated and saved: message_id={message.id}")
        return GetNextQuestionResponse(
            session_id=session_id,
            question=question,
            message_id=message.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"[get_next_question] Error generating question: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo câu hỏi: {str(e)}",
        )
