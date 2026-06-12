from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.auth.services.score_feedback_service import handle_feedback

router = APIRouter(prefix="/scoring-feedback", tags=["Agent"])

@router.post("/", response_model=FeedbackResponse)
async def submit_score_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Endpoint nhận phản hồi của ứng viên về điểm số, giao cho Agent phân tích,
    kiểm chứng và tự động đưa ra quyết định ghi đè điểm (Score Override).
    """
    try:
        response = await handle_feedback(request, db, current_user=current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not response.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.rationale)
    return response
