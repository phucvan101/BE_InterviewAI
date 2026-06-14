import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.auth.models.user import User
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)


def _parse_positive_id(raw_id: str, field_name: str) -> int:
    try:
        value = int(raw_id)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer")

    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


async def handle_feedback(
    request: FeedbackRequest,
    db: AsyncSession,
    current_user: Optional[User] = None,
) -> FeedbackResponse:
    """
    Nhận feedback về điểm số và lưu override (không còn gọi Agent Feedback nữa).
    """
    cv_id = _parse_positive_id(request.cv_id, "cv_id")
    jd_id = _parse_positive_id(request.jd_id, "jd_id")

    logger.info("[FEEDBACK] Feedback received: cv_id=%s, jd_id=%s", cv_id, jd_id)

    cv_record = (
        await db.execute(select(CVProfile).where(CVProfile.id_cv == cv_id))
    ).scalar_one_or_none()
    jd_record = (
        await db.execute(select(JobDescription).where(JobDescription.id_jd == jd_id))
    ).scalar_one_or_none()

    if not cv_record:
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale="CV not found",
        )
    if not jd_record:
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale="Job description not found",
        )

    if current_user and not getattr(current_user, "is_superuser", False):
        if cv_record.user_id != current_user.id or jd_record.user_id != current_user.id:
            return FeedbackResponse(
                success=False,
                is_overridden=False,
                rationale="You do not have permission to submit feedback for this CV/JD pair",
            )

    return FeedbackResponse(
        success=True,
        is_overridden=False,
        rationale="Cảm ơn bạn đã phản hồi! Hệ thống đã ghi nhận.",
    )
