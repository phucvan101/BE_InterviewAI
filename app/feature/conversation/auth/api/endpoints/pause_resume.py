# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.models.conversation import ConversationStatus
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{session_id}/pause",
    summary="Tạm dừng phiên phỏng vấn",
)
async def pause_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Tạm dừng phiên phỏng vấn đang hoạt động."""
    logger.info(f"[pause_interview] Pausing interview for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[pause_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[pause_interview] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status == ConversationStatus.PAUSED:
        logger.warning(f"[pause_interview] Already paused: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn đã được tạm dừng",
        )

    if conversation.status != ConversationStatus.ACTIVE:
        logger.warning(f"[pause_interview] Cannot pause non-active conversation: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể tạm dừng phiên phỏng vấn có trạng thái: {conversation.status}",
        )

    try:
        conversation.status = ConversationStatus.PAUSED
        await db.flush()
        await db.refresh(conversation)
        await db.commit()

        logger.info(f"[pause_interview] Interview paused successfully: session_id={session_id}")
        return {
            "success": True,
            "message": "Phiên phỏng vấn đã được tạm dừng",
            "session_id": session_id,
            "status": conversation.status,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"[pause_interview] Error pausing interview: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạm dừng phỏng vấn: {str(e)}",
        )


@router.post(
    "/{session_id}/resume",
    summary="Tiếp tục phiên phỏng vấn",
)
async def resume_interview(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Tiếp tục phiên phỏng vấn đã tạm dừng."""
    logger.info(f"[resume_interview] Resuming interview for session_id={session_id}")
    service = ConversationService(db)
    conversation = await service.get_conversation_by_session_id(session_id)

    if not conversation:
        logger.warning(f"[resume_interview] Conversation not found: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên phỏng vấn không tìm thấy",
        )

    if conversation.user_id != current_user.id:
        logger.warning(f"[resume_interview] Unauthorized access by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập phiên phỏng vấn này",
        )

    if conversation.status == ConversationStatus.ACTIVE:
        logger.warning(f"[resume_interview] Already active: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn đang hoạt động",
        )

    if conversation.status != ConversationStatus.PAUSED:
        logger.warning(f"[resume_interview] Cannot resume non-paused conversation: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể tiếp tục phiên phỏng vấn có trạng thái: {conversation.status}",
        )

    try:
        conversation.status = ConversationStatus.ACTIVE
        await db.flush()
        await db.refresh(conversation)
        await db.commit()

        logger.info(f"[resume_interview] Interview resumed successfully: session_id={session_id}")
        return {
            "success": True,
            "message": "Phiên phỏng vấn đã được tiếp tục",
            "session_id": session_id,
            "status": conversation.status,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"[resume_interview] Error resuming interview: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tiếp tục phỏng vấn: {str(e)}",
        )
