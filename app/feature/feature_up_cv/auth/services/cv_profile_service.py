from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cv_profile import CVProfile


class CVProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, user_id: int, file_url: str) -> CVProfile:
        cv = CVProfile(user_id=user_id, file_url=file_url)
        self.db.add(cv)
        await self.db.flush()
        await self.db.refresh(cv)
        return cv

    # ── Read ────────────────────────────────
    async def get_by_user(self, user_id: int) -> list[CVProfile]:
        result = await self.db.execute(
            select(CVProfile).where(CVProfile.user_id == user_id)
        )
        return result.scalars().all()

    # ── Delete ──────────────────────────────
    async def delete(self, cv_id: int) -> None:
        result = await self.db.execute(
            select(CVProfile).where(CVProfile.id == cv_id)
        )
        cv = result.scalar_one_or_none()
        if cv:
            await self.db.delete(cv)
            await self.db.flush()