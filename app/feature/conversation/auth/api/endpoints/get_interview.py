# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import ConversationResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{session_id}",
    response_model=ConversationResponse,
    summary="Lấy chi tiết phiên phỏng vấn",
)
async def get_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    logger.debug(f"[get_interview] Getting conversation session_id={session_id} for user {current_user.id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[get_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[get_interview] Unauthorized access to conversation {session_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    logger.info(f"[get_interview] Retrieved conversation: session_id={session_id}, status={conversation.status}")
    return ConversationResponse.model_validate(conversation)
