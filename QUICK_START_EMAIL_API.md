# Quick Start - Email API

## ⚡ 3-Step Setup

### 1. Install SendGrid
```bash
pip install sendgrid==7.0.0
```

### 2. Configure `.env`
```env
SENDGRID_API_KEY=your_key_here
```

### 3. Test API
```bash
# Start server
python3 run.py

# Call API (in another terminal)
curl -X POST http://localhost:8000/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
```

## 📖 What This API Does

Takes `session_id` → Sends job application email with CV attachment

**Flow:**
```
session_id → Load JD text + CV path → Extract company email → Send email via SendGrid
```

## 📍 API Endpoint

```
POST /api/v1/email/send-job-application
```

**Request:**
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

## 🗂️ File Structure Created

```
app/feature/email/
├── api/endpoints/send_email.py       # API endpoint
├── service/
│   ├── email_application_service.py  # Business logic
│   └── sendgrid_service.py          # SendGrid wrapper
├── repository/
│   └── analysis_session_repository.py # Database query
├── schema/send_email_schema.py       # Request/Response
├── utils/email_extractor.py          # Extract email from JD
├── test_email_api.py                 # Unit tests
├── README.md                         # Full documentation
└── SETUP.md                          # Detailed setup
```

## 📝 Implementation Details

### Database Tables Used
- `analysis_sessions` - Contains JD text (`jd_raw_text`) and CV ID (`id_cv`)
- `cv_profiles` - Contains CV file path (`raw_file_url`)

### Email Features
- **From:** `nguyenvanphuc10124@gmail.com`
- **To:** Extracted from job description
- **Attachment:** CV file from `cv_profiles.raw_file_url`
- **Subject:** `Job Application - {Company Name}`

### Error Handling
- Validates session exists
- Checks JD text exists
- Extracts company email from JD
- Verifies CV file exists
- Handles SendGrid API errors

## 🧪 Test Examples

### Extract Email from Job Description
```python
from app.feature.email.utils import extract_company_email

text = "Contact: jobs@company.com"
email = extract_company_email(text)
# Returns: "jobs@company.com"
```

### Extract Company Name
```python
from app.feature.email.utils import extract_company_name_from_jd

text = "Company: TechCorp Inc"
company = extract_company_name_from_jd(text)
# Returns: "TechCorp Inc"
```

## ✨ Features

✅ Send job application email with CV attachment
✅ Extract company email from job description
✅ Extract company name from job description
✅ Proper error handling for all edge cases
✅ SendGrid API integration
✅ Unit tests included
✅ API documentation

## 📚 More Info

- Full details: `app/feature/email/SETUP.md`
- API docs: `app/feature/email/README.md`
- Tests: `app/feature/email/test_email_api.py`

## 🚨 Common Issues

**SendGrid not installed?**
```bash
pip install sendgrid==7.0.0
```

**SENDGRID_API_KEY not set?**
- Get key from SendGrid dashboard
- Add to `.env` file
- Restart server

**Company email not found?**
- Ensure JD text contains email address
- Check email pattern in `extract_company_email()`

## 🎯 Next Steps

1. ✅ Install sendgrid
2. ✅ Set SENDGRID_API_KEY in `.env`
3. ✅ Start server: `python3 run.py`
4. ✅ Call API with valid session_id
5. ✅ Check email was sent!
