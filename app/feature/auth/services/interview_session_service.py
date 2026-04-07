from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.interview_session import InterviewSession


class InterviewSessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create session ──────────────────────
    async def create(self, user_id: int) -> InterviewSession:
        session = InterviewSession(user_id=user_id, status="in_progress")
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    # ── Get session ─────────────────────────
    async def get_by_id(self, session_id: int) -> InterviewSession | None:
        result = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int):
        result = await self.db.execute(
            select(InterviewSession).where(InterviewSession.user_id == user_id)
        )
        return result.scalars().all()

    # ── Finish session ──────────────────────
    async def finish(self, session_id: int) -> InterviewSession:
        session = await self.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")

        session.status = "completed"
        await self.db.flush()
        await self.db.refresh(session)
        return session