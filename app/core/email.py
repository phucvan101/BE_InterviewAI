import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_email_async(to_email: str, subject: str, html_content: str) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP config is missing, email not sent.")
        return False

    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = subject

    part = MIMEText(html_content, "html")
    message.attach(part)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=getattr(settings, 'SMTP_TLS', True),
        )
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

def generate_forgot_password_html(new_password: str) -> str:
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 8px;">
            <h2 style="color: #2c3e50; text-align: center;">Khôi Phục Mật Khẩu</h2>
            <p>Xin chào,</p>
            <p>Hệ thống đã nhận được yêu cầu cấp lại mật khẩu cho tài khoản của bạn.</p>
            <p>Mật khẩu mới của bạn là: <strong style="font-size: 18px; color: #e74c3c; letter-spacing: 2px;">{new_password}</strong></p>
            <p>Vui lòng đăng nhập bằng mật khẩu này và đổi lại mật khẩu mới ngay khi có thể để đảm bảo an toàn.</p>
            <p>Nếu bạn không yêu cầu đổi mật khẩu, vui lòng bỏ qua email này.</p>
            <hr style="border: none; border-top: 1px solid #eaeaea; margin: 20px 0;" />
            <p style="font-size: 12px; color: #7f8c8d; text-align: center;">
                Đây là email tự động từ hệ thống InterviewAI. Vui lòng không trả lời.
            </p>
        </div>
    </body>
    </html>
    """
