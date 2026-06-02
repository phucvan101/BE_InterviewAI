from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.auth.services.score_feedback_service import handle_feedback

router = APIRouter(prefix="/scoring-feedback", tags=["Agent"])

@router.post("/", response_model=FeedbackResponse)
async def submit_score_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint nhận phản hồi của ứng viên về điểm số, giao cho Agent phân tích,
    kiểm chứng và tự động đưa ra quyết định ghi đè điểm (Score Override).
    """
    response = await handle_feedback(request, db)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.rationale)
    return response
