from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from ...models.user import User
from ...services.interview_session_service import InterviewSessionService

router = APIRouter(prefix="/interviews", tags=["Interview Sessions"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewSessionService(db).create(current_user.id)


@router.get("/")
async def get_my_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewSessionService(db).get_by_user(current_user.id)


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewSessionService(db).get_by_id(session_id)


@router.post("/{session_id}/finish")
async def finish_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewSessionService(db).finish(session_id)