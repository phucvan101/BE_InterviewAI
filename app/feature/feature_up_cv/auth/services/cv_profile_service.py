from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cv_profile import CVProfile
from ..schemas.cv_profile import CVProfileCreate, CVProfileUpdate


class CVProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, user_id: int, data: CVProfileCreate) -> CVProfile:
        cv = CVProfile(
            user_id=user_id,
            parser_file_url=data.parser_file_url,
            raw_file_url=data.raw_file_url,
            text_hashed=data.text_hashed,
        )
        self.db.add(cv)
        await self.db.flush()
        await self.db.refresh(cv)
        return cv

    # ── Read ────────────────────────────────
    async def get_by_id(self, id_cv: int) -> CVProfile | None:
        result = await self.db.execute(
            select(CVProfile).where(CVProfile.id_cv == id_cv)
        )
        return result.scalar_one_or_none()

    async def get_by_text_hash(self, text_hashed: str) -> CVProfile | None:
        """Find a CV profile with the same extracted text hash (for parser cache)."""
        result = await self.db.execute(
            select(CVProfile).where(CVProfile.text_hashed == text_hashed).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[CVProfile]:
        result = await self.db.execute(
            select(CVProfile).where(CVProfile.user_id == user_id).order_by(CVProfile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[CVProfile]:
        result = await self.db.execute(
            select(CVProfile).offset(skip).limit(limit).order_by(CVProfile.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Update ──────────────────────────────
    async def update(self, id_cv: int, data: CVProfileUpdate) -> CVProfile | None:
        cv = await self.get_by_id(id_cv)
        if not cv:
            return None
        
        if data.parser_file_url is not None:
            cv.parser_file_url = data.parser_file_url
        if data.raw_file_url is not None:
            cv.raw_file_url = data.raw_file_url
        if data.text_hashed is not None:
            cv.text_hashed = data.text_hashed
        
        await self.db.flush()
        await self.db.refresh(cv)
        return cv

    # ── Delete ──────────────────────────────
    async def delete(self, id_cv: int) -> bool:
        cv = await self.get_by_id(id_cv)
        if cv:
            await self.db.delete(cv)
            await self.db.flush()
            return True
        return False