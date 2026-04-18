from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from ...models.user import User
from ...services.interview_question_service import InterviewQuestionService

router = APIRouter(prefix="/interview-questions", tags=["Interview Questions"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_question_to_session(
    session_id: int,
    question_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewQuestionService(db).add_question(session_id, question_id)


@router.post("/{iq_id}/answer")
async def answer_question(
    iq_id: int,
    answer: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewQuestionService(db).answer(iq_id, answer)


@router.get("/session/{session_id}")
async def get_session_questions(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await InterviewQuestionService(db).get_by_session(session_id)