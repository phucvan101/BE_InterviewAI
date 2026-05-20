from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis_session import AnalysisSession
from ..schemas.analysis_session import AnalysisSessionCreate, AnalysisSessionUpdate


class AnalysisSessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────
    async def create(self, user_id: int, data: AnalysisSessionCreate) -> AnalysisSession:
        session = AnalysisSession(
            user_id=user_id,
            id_cv=data.id_cv,
            id_jd=data.id_jd,
            id_ci=data.id_ci,
            cv_raw_text=data.cv_raw_text,
            jd_raw_text=data.jd_raw_text,
            ci_raw_text=data.ci_raw_text,
            score=data.score,
            experience_score=data.experience_score,
            skills_score=data.skills_score,
            education_score=data.education_score,
            companyfit_score=data.companyfit_score,
            result_analysis_file_url=data.result_analysis_file_url,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    # ── Read ────────────────────────────────
    async def get_by_id(self, id_session: int) -> AnalysisSession | None:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.id_session == id_session)
        )
        return result.scalar_one_or_none()

    async def get_by_session_id(self, session_id: int) -> AnalysisSession | None:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.id_session == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_documents(self, user_id: int, id_cv: int, id_jd: int, id_ci: int | None = None) -> AnalysisSession | None:
        query = select(AnalysisSession).where(
            AnalysisSession.user_id == user_id,
            AnalysisSession.id_cv == id_cv,
            AnalysisSession.id_jd == id_jd
        )
        if id_ci is not None:
            query = query.where(AnalysisSession.id_ci == id_ci)
        else:
            query = query.where(AnalysisSession.id_ci.is_(None))
            
        result = await self.db.execute(query.order_by(AnalysisSession.create_at.desc()))
        return result.scalars().first()

    async def get_by_user(self, user_id: int) -> list[AnalysisSession]:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.user_id == user_id).order_by(AnalysisSession.create_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_cv(self, id_cv: int) -> list[AnalysisSession]:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.id_cv == id_cv).order_by(AnalysisSession.create_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_jd(self, id_jd: int) -> list[AnalysisSession]:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.id_jd == id_jd).order_by(AnalysisSession.create_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_company_info(self, id_ci: int) -> list[AnalysisSession]:
        result = await self.db.execute(
            select(AnalysisSession).where(AnalysisSession.id_ci == id_ci).order_by(AnalysisSession.create_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[AnalysisSession]:
        result = await self.db.execute(
            select(AnalysisSession).offset(skip).limit(limit).order_by(AnalysisSession.create_at.desc())
        )
        return list(result.scalars().all())

    # ── Update ──────────────────────────────
    async def update(self, id_session: int, data: AnalysisSessionUpdate) -> AnalysisSession | None:
        session = await self.get_by_id(id_session)
        if not session:
            return None
        
        if data.cv_raw_text is not None:
            session.cv_raw_text = data.cv_raw_text
        if data.jd_raw_text is not None:
            session.jd_raw_text = data.jd_raw_text
        if data.score is not None:
            session.score = data.score
        if data.experience_score is not None:
            session.experience_score = data.experience_score
        if data.skills_score is not None:
            session.skills_score = data.skills_score
        if data.education_score is not None:
            session.education_score = data.education_score
        if data.companyfit_score is not None:
            session.companyfit_score = data.companyfit_score
        if data.id_ci is not None:
            session.id_ci = data.id_ci
        if data.result_analysis_file_url is not None:
            session.result_analysis_file_url = data.result_analysis_file_url
        
        await self.db.flush()
        await self.db.refresh(session)
        return session

    # ── Delete ──────────────────────────────
    async def delete(self, id_session: int) -> bool:
        session = await self.get_by_id(id_session)
        if session:
            await self.db.delete(session)
            await self.db.flush()
            return True
        return False
