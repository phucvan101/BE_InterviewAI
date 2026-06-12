from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.feature.feature_up_cv.auth.models import CVProfile


class AnalysisSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_session_with_cv(self, session_id: int) -> dict | None:
        """
        Lấy analysis session cùng với file path của CV.
        Return: {jd_raw_text, cv_file_path} hoặc None
        """
        query = text("""
            SELECT as1.jd_raw_text, as1.id_cv, as1.user_id
            FROM analysis_sessions as1
            WHERE as1.id_session = :session_id
        """)
        result = await self.db.execute(query, {"session_id": session_id})
        session = result.fetchone()

        if not session:
            return None

        jd_text, cv_id, user_id = session

        cv_query = select(CVProfile).where(CVProfile.id_cv == cv_id)
        cv_result = await self.db.execute(cv_query)
        cv_profile = cv_result.scalar_one_or_none()

        if not cv_profile:
            return None

        return {
            "jd_raw_text": jd_text,
            "cv_file_path": cv_profile.raw_file_url,
            "session_id": session_id,
            "user_id": user_id,
        }
