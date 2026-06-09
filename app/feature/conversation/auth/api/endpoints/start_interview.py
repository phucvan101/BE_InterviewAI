# -*- coding: utf-8 -*-
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.schemas import ConversationStartRequest, ConversationResponse
from app.feature.conversation.auth.services import ConversationService
from app.feature.feature_up_cv.auth.services.analysis_session_service import AnalysisSessionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên phỏng vấn mới",
)
async def start_interview(
    request: ConversationStartRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    logger.info(f"[start_interview] User {current_user.id} ({current_user.email}) starting new interview")
    service = ConversationService(db)

    job_description = request.job_description
    cv_profile = request.cv_profile

    if request.session_id:
        session_service = AnalysisSessionService(db)
        analysis_session = await session_service.get_by_session_id(request.session_id)
        if not analysis_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session không tìm thấy (analysis_sessions)",
            )
        if analysis_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập session này",
            )
        if not analysis_session.jd_raw_text or not analysis_session.cv_raw_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session chưa có dữ liệu raw text (cv_raw_text/jd_raw_text)",
            )
        job_description = analysis_session.jd_raw_text
        cv_profile = analysis_session.cv_raw_text

    conversation = await service.create_conversation(
        user_id=current_user.id,
        job_description=job_description or "",
        cv_profile=cv_profile or "",
        session_id=request.session_id,
    )
    logger.info(f"[start_interview] Created conversation: session_id={conversation.session_id}, id={conversation.id}")
    await db.commit()
    return ConversationResponse.model_validate(conversation)
