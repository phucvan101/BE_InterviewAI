import os
import base64
from typing import TYPE_CHECKING, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from sendgrid.helpers.mail import Attachment

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


class SendGridService:
    def __init__(self):
        if not SENDGRID_AVAILABLE:
            raise ImportError("sendgrid package is not installed. Install with: pip install sendgrid==7.0.0")

        self.sg_client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        self.from_email = "nguyenvanphuc10124@gmail.com"

    async def send_job_application_email(
        self,
        to_email: str,
        company_name: Optional[str],
        cv_file_path: Optional[str],
    ) -> tuple[bool, str]:
        """
        Gửi email xin việc đính kèm CV.
        Args:
            to_email: Email người nhận (công ty)
            company_name: Tên công ty
            cv_file_path: Đường dẫn tới file CV
        Returns:
            (success: bool, message: str)
        """
        try:
            if not cv_file_path or not os.path.exists(cv_file_path):
                return False, "CV file not found"

            subject = f"Job Application - {company_name or 'Candidate'}"
            html_content = self._build_email_content(company_name)

            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
            )

            attachment = self._create_attachment(cv_file_path)
            if attachment:
                message.attachment = attachment

            response = self.sg_client.send(message)

            if response.status_code in [200, 201, 202]:
                return True, f"CV đã được gửi thành công đến {to_email}"
            else:
                return False, f"Failed to send email: {response.status_code}"

        except Exception as e:
            return False, f"Error sending email: {str(e)}"

    def _build_email_content(self, company_name: Optional[str]) -> str:
        """Tạo nội dung email xin việc."""
        company_text = f"at {company_name}" if company_name else ""
        return f"""
        <html>
            <body>
                <p>Dear Hiring Team,</p>
                <p>I am writing to express my strong interest in the position {company_text}.</p>
                <p>I have attached my resume for your review. I am confident that my skills and experience make me a strong candidate for this role.</p>
                <p>Thank you for considering my application. I look forward to hearing from you.</p>
                <p>Best regards,<br>
                Candidate</p>
            </body>
        </html>
        """

    def _create_attachment(self, file_path: str) -> "Attachment | None":
        """Tạo attachment từ file path."""
        try:
            with open(file_path, "rb") as attachment_file:
                file_content = base64.b64encode(attachment_file.read()).decode()

            file_name = os.path.basename(file_path)
            attachment = Attachment(
                FileContent(file_content),
                FileName(file_name),
                FileType("application/pdf"),
                Disposition("attachment"),
            )
            return attachment
        except Exception as e:
            print(f"Error creating attachment: {str(e)}")
            return None
