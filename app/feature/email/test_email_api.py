"""
Test script để test email API.
Run với: python -m pytest app/feature/email/test_email_api.py -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.feature.email.schema import SendEmailRequest, SendEmailResponse
from app.feature.email.utils import extract_company_email, extract_company_name_from_jd


class TestEmailExtractor:
    """Test email extraction utilities."""

    def test_extract_company_email_valid(self):
        """Test trích xuất email hợp lệ từ JD."""
        jd_text = """
        Job Description
        Contact: hr@techcompany.com
        Email us at jobs@techcompany.com
        """
        email = extract_company_email(jd_text)
        assert email is not None
        assert "@" in email

    def test_extract_company_email_empty(self):
        """Test với empty text."""
        email = extract_company_email("")
        assert email is None

    def test_extract_company_email_none(self):
        """Test với None."""
        email = extract_company_email(None)
        assert email is None

    def test_extract_company_name_valid(self):
        """Test trích xuất tên công ty."""
        jd_text = "Company: TechCorp Inc\nLocation: Ho Chi Minh City"
        company_name = extract_company_name_from_jd(jd_text)
        assert company_name == "TechCorp Inc"

    def test_extract_company_name_empty(self):
        """Test với empty text."""
        company_name = extract_company_name_from_jd("")
        assert company_name is None


class TestSendEmailSchema:
    """Test request/response schemas."""

    def test_send_email_request_valid(self):
        """Test valid request."""
        request = SendEmailRequest(session_id=1)
        assert request.session_id == 1

    def test_send_email_response_success(self):
        """Test success response."""
        response = SendEmailResponse(
            success=True,
            message="Email sent successfully"
        )
        assert response.success is True
        assert "successfully" in response.message

    def test_send_email_response_failure(self):
        """Test failure response."""
        response = SendEmailResponse(
            success=False,
            message="Email not found"
        )
        assert response.success is False


# Integration tests (require database setup)
@pytest.mark.asyncio
async def test_email_application_service_mock():
    """Test EmailApplicationService with mocks."""
    from app.feature.email.service import EmailApplicationService

    mock_db = AsyncMock()
    service = EmailApplicationService(mock_db)

    with patch.object(service.repository, 'get_session_with_cv') as mock_get:
        mock_get.return_value = {
            "jd_raw_text": "Job at Company: TechCorp\nContact: hr@techcorp.com",
            "cv_file_path": "/path/to/cv.pdf",
            "session_id": 1,
        }

        with patch.object(service.sendgrid_service, 'send_job_application_email') as mock_send:
            mock_send.return_value = (True, "Email sent successfully")

            success, message = await service.send_job_application(1)

            assert success is True
            assert "successfully" in message
            mock_get.assert_called_once_with(1)
            mock_send.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
