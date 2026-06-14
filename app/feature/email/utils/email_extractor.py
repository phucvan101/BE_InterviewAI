from typing import Optional
import re


def extract_company_email(jd_text: str) -> Optional[str]:
    """
    Trích xuất email công ty từ job description text.
    Tìm kiếm các email patterns như: company@domain.com
    """
    if not jd_text:
        return None

    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(email_pattern, jd_text)

    if matches:
        for email in matches:
            if not email.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return email

    return None


def extract_company_name_from_jd(jd_text: str) -> Optional[str]:
    """
    Trích xuất tên công ty từ job description text.
    Tìm kiếm patterns như "Company:", "Công ty:" hoặc tên công ty ở đầu văn bản.
    """
    if not jd_text:
        return None

    patterns = [
        r'(?:Company|Công ty|Công Ty):\s*([^\n]+)',
        r'(?:Employer|Nhà tuyển dụng):\s*([^\n]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, jd_text, re.IGNORECASE)
        if match:
            company_name = match.group(1).strip()
            if company_name:
                return company_name

    return None
