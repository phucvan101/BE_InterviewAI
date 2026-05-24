from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.company_info import CompanyInfo
from ..schemas.company_info import CompanyInfoCreate, CompanyInfoUpdate


class CompanyInfoService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, user_id: int, data: CompanyInfoCreate) -> CompanyInfo:
        ci = CompanyInfo(
            user_id=user_id,
            parser_file_url=data.parser_file_url,
            raw_file_url=data.raw_file_url,
            text_hashed=data.text_hashed,
            text_content=data.text_content,
        )
        self.db.add(ci)
        await self.db.flush()
        await self.db.refresh(ci)
        return ci

    # ── Read ────────────────────────────────
    async def get_by_id(self, id_ci: int) -> CompanyInfo | None:
        result = await self.db.execute(
            select(CompanyInfo).where(CompanyInfo.id_ci == id_ci)
        )
        return result.scalar_one_or_none()

    async def get_by_text_hash(self, text_hashed: str) -> CompanyInfo | None:
        """Find a company info with the same extracted text hash (for parser cache)."""
        result = await self.db.execute(
            select(CompanyInfo).where(CompanyInfo.text_hashed == text_hashed).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[CompanyInfo]:
        result = await self.db.execute(
            select(CompanyInfo).where(CompanyInfo.user_id == user_id).order_by(CompanyInfo.upload_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[CompanyInfo]:
        result = await self.db.execute(
            select(CompanyInfo).offset(skip).limit(limit).order_by(CompanyInfo.upload_at.desc())
        )
        return list(result.scalars().all())

    # ── Update ──────────────────────────────
    async def update(self, id_ci: int, data: CompanyInfoUpdate) -> CompanyInfo | None:
        ci = await self.get_by_id(id_ci)
        if not ci:
            return None
        
        if data.parser_file_url is not None:
            ci.parser_file_url = data.parser_file_url
        if data.raw_file_url is not None:
            ci.raw_file_url = data.raw_file_url
        if data.text_hashed is not None:
            ci.text_hashed = data.text_hashed        
        if data.text_content is not None:
            ci.text_content = data.text_content        
        await self.db.flush()
        await self.db.refresh(ci)
        return ci

    # ── Delete ──────────────────────────────
    async def delete(self, id_ci: int) -> bool:
        ci = await self.get_by_id(id_ci)
        if ci:
            await self.db.delete(ci)
            await self.db.flush()
            return True
        return False
