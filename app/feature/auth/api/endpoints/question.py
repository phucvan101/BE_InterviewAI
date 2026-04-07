from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_superuser
from ...services.question_service import QuestionService

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_question(
    content: str,
    difficulty: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser),
):
    return await QuestionService(db).create(content, difficulty)


@router.get("/")
async def get_questions(
    difficulty: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)

    if difficulty:
        return await service.get_by_difficulty(difficulty)

    return await service.get_all()


@router.get("/random")
async def get_random_questions(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    return await QuestionService(db).get_random(limit)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser),
):
    await QuestionService(db).delete(question_id)