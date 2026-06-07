# Email Feature - Send Job Application

## Mô tả
Feature này cung cấp API để gửi email xin việc với đính kèm file CV.

## Kiến trúc

```
email/
├── api/
│   └── endpoints/
│       └── send_email.py       # API Endpoint
├── model/
│   └── analysis_session.py     # Database Model
├── repository/
│   └── analysis_session_repository.py  # Database Query
├── schema/
│   └── send_email_schema.py    # Request/Response Schema
├── service/
│   ├── email_application_service.py   # Business Logic
│   └── sendgrid_service.py     # SendGrid Integration
└── utils/
    └── email_extractor.py      # Email & Company Extraction
```

## Flow

```
API Request (session_id)
        ↓
Service (EmailApplicationService)
        ↓
Repository (lấy JD text + CV file path)
        ↓
Utils (trích xuất email công ty từ JD)
        ↓
SendGrid Service (gửi email)
        ↓
API Response (success, message)
```

## API Endpoint

### POST `/api/v1/email/send-job-application`

**Request Body:**
```json
{
  "session_id": 1
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Email sent successfully to company@example.com"
}
```

**Response (Error):**
```json
{
  "success": false,
  "message": "Company email not found in job description"
}
```

## Setup

### 1. Cài đặt SendGrid Package

```bash
pip install sendgrid==7.0.0
```

### 2. Cấu hình Environment

Thêm vào `.env` file:
```env
SENDGRID_API_KEY=your_sendgrid_api_key
```

### 3. Database

API sử dụng 2 tables:
- `analysis_sessions` - chứa job description text (`jd_raw_text`)
- `cv_profiles` - chứa đường dẫn file CV (`raw_file_url`)

## Functionality Details

### 1. Email Extraction (`email_extractor.py`)

Hàm `extract_company_email()`:
- Trích xuất email từ JD text sử dụng regex pattern
- Return: email hoặc None nếu không tìm thấy

Hàm `extract_company_name_from_jd()`:
- Tìm tên công ty từ patterns như "Company:", "Công ty:"
- Return: company name hoặc None

### 2. SendGrid Service (`sendgrid_service.py`)

Hàm `send_job_application_email()`:
- Gửi email xin việc từ: `nguyenvanphuc10124@gmail.com`
- Đính kèm file CV (PDF)
- Return: (success: bool, message: str)

### 3. Email Application Service (`email_application_service.py`)

Hàm `send_job_application()`:
- Orchestrate giữa repository, extractor, và sendgrid service
- Lấy data từ database
- Trích xuất email từ JD
- Gửi email qua SendGrid
- Return: (success: bool, message: str)

## Error Handling

Các error cases được xử lý:
- Analysis session không tồn tại
- Job description text không tìm thấy
- Email công ty không tìm thấy trong JD
- CV file không tồn tại
- SendGrid API error

## Example Usage

```python
# Using the API
curl -X POST http://localhost:8080/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
```

## Notes

- Email gửi từ: `nguyenvanphuc10124@gmail.com`
- Email nhận từ: được trích xuất từ job description text
- CV được đính kèm dưới dạng PDF attachment
- Hỗ trợ trích xuất email và tên công ty từ JD text
