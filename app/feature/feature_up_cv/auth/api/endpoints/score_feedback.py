"""
Feedback endpoint for the CV-JD scoring Feedback Agent.

POST /scoring-feedback/
  Body: FeedbackRequest
  Auth: required (regular user or superuser)

  1. Authenticated user submits a natural-language complaint about the
     score they received.
  2. The server loads the relevant CV/JD text, calls the agent and
     returns the agent's decision + actions.

This endpoint is part of the optional ``feedback_agent`` package. The
router is included by ``app/feature/feature_up_cv/auth/api/router.py``
with a ``try/except`` guard so branches without the agent still boot
cleanly.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User

from app.feature.feature_up_cv.auth.schemas.score_feedback import (
    FeedbackRequest,
    FeedbackResponse,
)
from app.feature.feature_up_cv.auth.services.score_feedback_service import (
    handle_feedback,
)


router = APIRouter(prefix="/scoring-feedback", tags=["Agent"])


@router.post("/", response_model=FeedbackResponse)
async def submit_score_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Submit a free-form complaint about a CV-JD scoring result. The
    Feedback Agent will analyse it and (when warranted) extend the
    skill-synonym knowledge base so future scoring runs are more
    accurate.
    """
    try:
        return await handle_feedback(request, db, current_user=current_user)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
