# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import ConversationListResponse, ConversationPaginatedResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=ConversationPaginatedResponse,
    summary="Lấy danh sách phiên phỏng vấn",
)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationPaginatedResponse:
    logger.debug(f"[list_conversations] Listing conversations for user {current_user.id}")
    service = ConversationService(db)
    conversations, total = await service.get_user_conversations(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )

    items = []
    for conv in conversations:
        items.append(ConversationListResponse(
            id=conv.id,
            session_id=conv.session_id,
            user_id=conv.user_id,
            status=conv.status,
            score=conv.score,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
        ))

    logger.info(f"[list_conversations] Found {total} conversations for user {current_user.id}")
    return ConversationPaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
