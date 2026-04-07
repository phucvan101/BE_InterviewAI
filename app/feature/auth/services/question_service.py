from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.question import Question
from sqlalchemy import func


class QuestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, content: str, difficulty: str) -> Question:
        question = Question(content=content, difficulty=difficulty)
        self.db.add(question)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    # ── Read ────────────────────────────────
    async def get_all(self) -> list[Question]:
        result = await self.db.execute(select(Question))
        return result.scalars().all()

    async def get_by_difficulty(self, difficulty: str) -> list[Question]:
        result = await self.db.execute(
            select(Question).where(Question.difficulty == difficulty)
        )
        return result.scalars().all()

    async def get_random(self, limit: int = 5) -> list[Question]:
        result = await self.db.execute(
            select(Question).order_by(func.random()).limit(limit)
        )
        return result.scalars().all()

    # ── Delete ──────────────────────────────
    async def delete(self, question_id: int) -> None:
        result = await self.db.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()
        if question:
            await self.db.delete(question)
            await self.db.flush()