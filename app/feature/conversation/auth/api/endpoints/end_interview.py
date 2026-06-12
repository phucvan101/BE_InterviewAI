# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.conversation.auth.models.conversation import ConversationStatus
from app.feature.conversation.auth.models.conversation_analysis_report import ConversationAnalysisReport
from app.feature.conversation.auth.schemas import InterviewResultResponse
from app.feature.conversation.auth.services import ConversationService

logger = logging.getLogger(__name__)
router = APIRouter()


def _calculate_grade(score: float) -> tuple[str, str]:
    """Calculate grade and level from score."""
    if score >= 85:
        return "A", "Xuất sắc"
    elif score >= 70:
        return "B", "Tốt"
    elif score >= 50:
        return "C", "Trung bình"
    elif score >= 30:
        return "D", "Yếu"
    else:
        return "F", "Không đạt"


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

    if conversation.status == ConversationStatus.COMPLETED:
        logger.warning(f"[end_interview] Interview already completed: session_id={session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên phỏng vấn đã kết thúc",
        )

    try:
        from app.feature.conversation.interview_agent.agent import interview_agent

        logger.info(f"[end_interview] Evaluating interview results for session_id={session_id}")
        evaluation = await interview_agent.evaluate_interview(
            job_description=conversation.job_description,
            cv_profile=conversation.cv_profile,
            conversation_id=conversation.id,
            db=db,
            analysis_result=conversation.analysis_data,
        )

        score = evaluation.get("fit_score", 0)
        grade, level = _calculate_grade(score)

        logger.info(f"[end_interview] Interview evaluation complete: score={score}, grade={grade}")

        conversation.status = ConversationStatus.COMPLETED
        conversation.ended_at = datetime.now(timezone.utc)
        if conversation.started_at:
            duration_seconds = int((conversation.ended_at - conversation.started_at).total_seconds())
            conversation.interview_duration_seconds = duration_seconds

        if conversation.result:
            existing_result = conversation.result
            try:
                import json
                existing_dict = json.loads(existing_result) if isinstance(existing_result, str) else existing_result
                evaluation = {**existing_dict, **evaluation}
            except:
                pass

        conversation.result = evaluation if isinstance(evaluation, str) else str(evaluation)
        conversation.score = score

        conversation_report = ConversationAnalysisReport(
            conversation_id=conversation.id,
            status="completed",
            overall_score=int(score),
            overall_grade=grade,
            level=level,
            summary=evaluation.get("comments", evaluation.get("recommendation", "")),
            tags=[],
            scores={
                "fit_score": score,
                "cv_jd_score": conversation.analysis_data.get("overall_score", 0) if conversation.analysis_data else 0,
            },
            ai_coach_insights=[],
            strengths=[{"text": s} for s in evaluation.get("strengths", [])],
            weaknesses=[{"text": w} for w in evaluation.get("weaknesses", [])],
            knowledge_gaps=[],
            study_plan=[],
            raw_ai_response=str(evaluation),
        )
        db.add(conversation_report)

        await db.flush()
        await db.refresh(conversation)
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
