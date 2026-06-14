from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.email.repository import AnalysisSessionRepository
from app.feature.email.utils import extract_company_email, extract_company_name_from_jd

try:
    from app.feature.email.service.sendgrid_service import SendGridService
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    SendGridService = None


class EmailApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AnalysisSessionRepository(db)
        self.sendgrid_service = None
        if SENDGRID_AVAILABLE:
            try:
                self.sendgrid_service = SendGridService()
            except ImportError:
                pass

    async def send_job_application(self, session_id: int, user_id: Optional[int] = None) -> tuple[bool, str]:
        """
        Gửi email xin việc cho công ty dựa vào analysis session.
        Flow:
        1. Lấy jd_raw_text và cv_file_path từ repository
        2. Trích xuất email công ty từ jd_raw_text
        3. Gửi email qua SendGrid
        """
        try:
            if not self.sendgrid_service:
                return False, "SendGrid service not available. Install sendgrid package: pip install sendgrid==7.0.0"

            session_data = await self.repository.get_session_with_cv(session_id)

            if not session_data:
                return False, "Analysis session not found"

            if user_id is not None and session_data.get("user_id") != user_id:
                return False, "You do not have permission to send this CV"

            jd_text = session_data.get("jd_raw_text")
            cv_file_path = session_data.get("cv_file_path")

            if not jd_text:
                return False, "Job description text not found"

            company_email = extract_company_email(jd_text)
            if not company_email:
                return False, "Company email not found in job description"

            company_name = extract_company_name_from_jd(jd_text)

            success, message = await self.sendgrid_service.send_job_application_email(
                to_email=company_email,
                company_name=company_name,
                cv_file_path=cv_file_path,
            )

            return success, message

        except Exception as e:
            return False, f"Error processing job application: {str(e)}"
