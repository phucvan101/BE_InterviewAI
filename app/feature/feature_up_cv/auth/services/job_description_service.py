from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.job_description import JobDescription
from ..schemas.job_description import JobDescriptionCreate, JobDescriptionUpdate


class JobDescriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, user_id: int, data: JobDescriptionCreate) -> JobDescription:
        jd = JobDescription(
            user_id=user_id,
            parser_file_url=data.parser_file_url,
            raw_file_url=data.raw_file_url,
            text_hashed=data.text_hashed,
        )
        self.db.add(jd)
        await self.db.flush()
        await self.db.refresh(jd)
        return jd

    # ── Read ────────────────────────────────
    async def get_by_id(self, id_jd: int) -> JobDescription | None:
        result = await self.db.execute(
            select(JobDescription).where(JobDescription.id_jd == id_jd)
        )
        return result.scalar_one_or_none()

    async def get_by_text_hash(self, text_hashed: str) -> JobDescription | None:
        """Find a JD with the same extracted text hash (for parser cache)."""
        result = await self.db.execute(
            select(JobDescription).where(JobDescription.text_hashed == text_hashed).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[JobDescription]:
        result = await self.db.execute(
            select(JobDescription).where(JobDescription.user_id == user_id).order_by(JobDescription.upload_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[JobDescription]:
        result = await self.db.execute(
            select(JobDescription).offset(skip).limit(limit).order_by(JobDescription.upload_at.desc())
        )
        return list(result.scalars().all())

    # ── Update ──────────────────────────────
    async def update(self, id_jd: int, data: JobDescriptionUpdate) -> JobDescription | None:
        jd = await self.get_by_id(id_jd)
        if not jd:
            return None
        
        if data.parser_file_url is not None:
            jd.parser_file_url = data.parser_file_url
        if data.raw_file_url is not None:
            jd.raw_file_url = data.raw_file_url
        if data.text_hashed is not None:
            jd.text_hashed = data.text_hashed
        
        await self.db.flush()
        await self.db.refresh(jd)
        return jd

    # ── Delete ──────────────────────────────
    async def delete(self, id_jd: int) -> bool:
        jd = await self.get_by_id(id_jd)
        if jd:
            await self.db.delete(jd)
            await self.db.flush()
            return True
        return False
