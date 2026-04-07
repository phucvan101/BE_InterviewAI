from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.interview_question import InterviewQuestion


class InterviewQuestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Add question to session ─────────────
    async def add_question(
        self,
        session_id: int,
        question_id: int,
    ) -> InterviewQuestion:
        iq = InterviewQuestion(
            session_id=session_id,
            question_id=question_id,
        )
        self.db.add(iq)
        await self.db.flush()
        await self.db.refresh(iq)
        return iq

    # ── Answer question ─────────────────────
    async def answer(
        self,
        interview_question_id: int,
        answer: str,
        score: float | None = None,
    ) -> InterviewQuestion:
        result = await self.db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.id == interview_question_id
            )
        )
        iq = result.scalar_one_or_none()

        if not iq:
            raise ValueError("InterviewQuestion not found")

        iq.answer = answer
        iq.score = score

        await self.db.flush()
        await self.db.refresh(iq)
        return iq

    # ── Get all questions in session ────────
    async def get_by_session(self, session_id: int):
        result = await self.db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.session_id == session_id
            )
        )
        return result.scalars().all()