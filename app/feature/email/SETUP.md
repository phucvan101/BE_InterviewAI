# Email Feature - Setup Guide

## ✅ Status
- **API Endpoint:** ✓ Created (`/api/v1/email/send-job-application`)
- **Service Layer:** ✓ Created
- **Repository Layer:** ✓ Created
- **Database Integration:** ✓ Ready (uses existing `analysis_sessions` & `cv_profiles` tables)

## 🚀 Installation

### Step 1: Install SendGrid Package

```bash
pip install sendgrid==7.0.0
```

Or update requirements:
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Add to your `.env` file:

```env
# SendGrid Configuration
SENDGRID_API_KEY=your_sendgrid_api_key_here
```

**How to get SendGrid API Key:**
1. Sign up at [https://sendgrid.com](https://sendgrid.com)
2. Go to Settings → API Keys
3. Create a new API key (Full Access)
4. Copy the key and add to `.env`

### Step 3: Verify Setup

Run the app:
```bash
python3 run.py
```

Check if endpoint is registered:
```bash
curl http://localhost:8000/docs
```

Look for `/api/v1/email/send-job-application` in Swagger UI.

## 📖 API Usage

### Endpoint
```
POST /api/v1/email/send-job-application
```

### Request Example
```bash
curl -X POST http://localhost:8000/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1
  }'
```

### Request Body
```json
{
  "session_id": 1
}
```

**Parameters:**
- `session_id` (integer, required): ID of the analysis session

### Response Example (Success)
```json
{
  "success": true,
  "message": "Email sent successfully to hr@techcompany.com"
}
```

### Response Example (Error)
```json
{
  "success": false,
  "message": "Company email not found in job description"
}
```

## 🔄 How It Works

```
1. Client sends session_id
        ↓
2. API validates request
        ↓
3. Service retrieves:
   - Job description text from analysis_sessions table
   - CV file path from cv_profiles table
        ↓
4. Service extracts company email from job description
        ↓
5. Service sends email with CV attachment via SendGrid
        ↓
6. Response: success status + message
```

## 📋 Database Requirements

### Tables Used
1. **analysis_sessions**
   - `id_session` (PK)
   - `jd_raw_text` - Job description text
   - `id_cv` - FK to cv_profiles

2. **cv_profiles**
   - `id_cv` (PK)
   - `raw_file_url` - Path to CV file
   - `user_id`

Both tables already exist in your database (created by migrations).

## 🧪 Testing

### Unit Tests
```bash
pytest app/feature/email/test_email_api.py -v
```

### Manual Testing

#### Test 1: Extract Email
```python
from app.feature.email.utils import extract_company_email

jd_text = "Contact us at jobs@company.com for more info"
email = extract_company_email(jd_text)
print(email)  # Output: jobs@company.com
```

#### Test 2: Extract Company Name
```python
from app.feature.email.utils import extract_company_name_from_jd

jd_text = "Company: TechCorp Inc\nLocation: NYC"
company = extract_company_name_from_jd(jd_text)
print(company)  # Output: TechCorp Inc
```

#### Test 3: API Call
```bash
# With valid session_id that exists in database
curl -X POST http://localhost:8000/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
```

## ⚠️ Error Handling

The API handles these error cases:

1. **Session Not Found**
   ```json
   {"success": false, "message": "Analysis session not found"}
   ```

2. **No Job Description**
   ```json
   {"success": false, "message": "Job description text not found"}
   ```

3. **No Company Email**
   ```json
   {"success": false, "message": "Company email not found in job description"}
   ```

4. **CV File Missing**
   ```json
   {"success": false, "message": "CV file not found"}
   ```

5. **SendGrid Not Installed**
   ```json
   {"success": false, "message": "SendGrid service not available. Install sendgrid package: pip install sendgrid==7.0.0"}
   ```

6. **SendGrid API Error**
   ```json
   {"success": false, "message": "Failed to send email: <error details>"}
   ```

## 🎯 Email Content

The email is sent from: `nguyenvanphuc10124@gmail.com`

Subject format:
```
Job Application - {Company Name}
```

Email body:
```html
Dear Hiring Team,

I am writing to express my strong interest in the position at {Company Name}.

I have attached my resume for your review. I am confident that my skills and experience make me a strong candidate for this role.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
Candidate
```

## 📁 File Structure

```
app/feature/email/
├── api/
│   └── endpoints/
│       ├── __init__.py
│       └── send_email.py           # Main API endpoint
├── repository/
│   ├── __init__.py
│   └── analysis_session_repository.py  # Database queries
├── schema/
│   ├── __init__.py
│   └── send_email_schema.py        # Request/Response schemas
├── service/
│   ├── __init__.py
│   ├── email_application_service.py # Business logic
│   └── sendgrid_service.py         # SendGrid integration
├── utils/
│   ├── __init__.py
│   └── email_extractor.py          # Email & company extraction
├── test_email_api.py               # Unit tests
├── README.md                       # Feature documentation
└── SETUP.md                        # This file
```

## 🔧 Configuration Reference

### config.py
```python
# SendGrid configuration
SENDGRID_API_KEY: Optional[str] = None
```

### Example .env
```env
DATABASE_URL=postgresql+asyncpg://admin:123456@localhost:5433/mydb
SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
```

## 🐛 Troubleshooting

### Issue: "sendgrid package not installed"
**Solution:** 
```bash
pip install sendgrid==7.0.0
```

### Issue: "SENDGRID_API_KEY not configured"
**Solution:**
1. Get API key from SendGrid dashboard
2. Add to `.env` file
3. Restart the app

### Issue: "CV file not found"
**Solution:**
- Check that `raw_file_url` in `cv_profiles` table is correct
- Ensure file exists at the specified path
- Verify file permissions

### Issue: "Company email not found"
**Solution:**
- Job description must contain a valid email address
- Check email pattern in `jd_raw_text`
- Update `extract_company_email()` in `email_extractor.py` if needed

## 📞 Support

For issues or feature requests, check:
- Email Feature README: `app/feature/email/README.md`
- API Documentation: `/api/v1/docs` (Swagger UI)
- Test file: `app/feature/email/test_email_api.py`
