# Logging Guide - Email API

## 📊 Logging Overview

API giờ đã có logging chi tiết ở mỗi layer:

```
API Endpoint → Service → Repository → Utils → SendGrid
    ↓            ↓          ↓          ↓        ↓
  [API]      [Service]  [Repository] [Utils] [SendGrid]
```

## 🎯 Log Levels

| Level | Icon | Usage | Example |
|-------|------|-------|---------|
| **INFO** | ✅ | Important events | Email sent successfully |
| **DEBUG** | 🔍 | Detailed flow | Session data fetched |
| **WARNING** | ⚠️ | Issues but continue | Email not found |
| **ERROR** | ❌ | Failures | Database error |

## 📍 Log Locations

### 1. API Layer (`send_email.py`)
```
📧 [API] Received request to send job application for session_id=1
✓ [API] EmailApplicationService initialized for session_id=1
✅ [API] Successfully sent email for session_id=1: Email sent successfully to hr@company.com
```

### 2. Service Layer (`email_application_service.py`)
```
📬 [Service] Starting email send process for session_id=1
🔍 [Service] Fetching session data for session_id=1
✓ [Service] Session data fetched successfully - session_id=1
🔎 [Service] Extracting company email from JD - session_id=1
✓ [Service] Company email extracted: hr@company.com
📧 [Service] Sending email via SendGrid - To: hr@company.com
✅ [Service] Email sent successfully - Email sent successfully...
```

### 3. Repository Layer (`analysis_session_repository.py`)
```
🔍 [Repository] Querying analysis_sessions table for session_id=1
✓ [Repository] Analysis session found - session_id=1, cv_id=5
🔍 [Repository] Querying cv_profiles table for cv_id=5
✓ [Repository] CV profile found - cv_id=5, file_path=/path/to/cv.pdf
```

### 4. Utils Layer (`email_extractor.py`)
```
🔎 [Utils] Searching for email pattern in JD text
ℹ️  [Utils] Found 2 email(s) in text: ['hr@company.com', 'jobs@company.com']
✓ [Utils] Selected email: hr@company.com
🔎 [Utils] Searching for company name pattern in JD text
✓ [Utils] Company name extracted: TechCorp Inc
```

### 5. SendGrid Layer (`sendgrid_service.py`)
```
✓ [SendGrid] Service initialized - From: nguyenvanphuc10124@gmail.com
📧 [SendGrid] Starting email send - To: hr@company.com, Company: TechCorp Inc
✓ [SendGrid] CV file verified - Path: /path/to/cv.pdf
📎 [SendGrid] Creating attachment from file: /path/to/cv.pdf
✓ [SendGrid] File encoded - Name: cv.pdf, Size: 12345 bytes
📤 [SendGrid] Sending email via SendGrid API...
✅ [SendGrid] Email sent successfully to hr@company.com (Status: 202)
```

## 🚀 How to View Logs

### Option 1: Run Server and View Console Logs
```bash
python3 run.py
```

Console output:
```
INFO:app.feature.email.api.endpoints.send_email:📧 [API] Received request...
DEBUG:app.feature.email.service.email_application_service:🔍 [Service] Fetching...
INFO:app.feature.email.repository.analysis_session_repository:✓ [Repository] Analysis session...
```

### Option 2: Test with Curl
```bash
curl -X POST http://localhost:8000/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}' \
  -v
```

### Option 3: Write Logs to File

Create `logging_config.py`:
```python
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "default",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "logs/email_api.log",
        },
    },
    "loggers": {
        "app.feature.email": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

Then in `main.py`:
```python
from logging_config import LOGGING_CONFIG
import logging.config

logging.config.dictConfig(LOGGING_CONFIG)
```

## 📋 Complete Execution Flow with Logs

```
Request: POST /api/v1/email/send-job-application
Body: {"session_id": 1}

┌─────────────────────────────────────────────────────────────────┐
│ 📧 [API] Received request to send job application for session_id=1
│ ✓ [API] EmailApplicationService initialized for session_id=1
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 📬 [Service] Starting email send process for session_id=1
│ 🔍 [Service] Fetching session data for session_id=1
│     │
│     └─ 🔍 [Repository] Querying analysis_sessions table
│        ✓ [Repository] Analysis session found - cv_id=5
│        🔍 [Repository] Querying cv_profiles table for cv_id=5
│        ✓ [Repository] CV profile found - file_path=/path/to/cv.pdf
│
│ ✓ [Service] Session data fetched successfully
│ 🔎 [Service] Extracting company email from JD
│     │
│     └─ 🔎 [Utils] Searching for email pattern in JD text
│        ℹ️  [Utils] Found 2 email(s)
│        ✓ [Utils] Selected email: hr@company.com
│
│ ✓ [Service] Company email extracted: hr@company.com
│ 🔎 [Service] Extracting company name from JD
│     │
│     └─ 🔎 [Utils] Searching for company name pattern
│        ✓ [Utils] Company name extracted: TechCorp Inc
│
│ 📧 [Service] Sending email via SendGrid
│     │
│     └─ 📧 [SendGrid] Starting email send - To: hr@company.com
│        ✓ [SendGrid] CV file verified
│        📎 [SendGrid] Creating attachment
│        ✓ [SendGrid] File encoded - Size: 12345 bytes
│        📤 [SendGrid] Sending email via SendGrid API...
│        ✅ [SendGrid] Email sent successfully (Status: 202)
│
│ ✅ [Service] Email sent successfully
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ ✅ [API] Successfully sent email for session_id=1
│ Response: {"success": true, "message": "Email sent successfully..."}
└─────────────────────────────────────────────────────────────────┘
```

## 🔍 Debugging with Logs

### Scenario 1: Email Not Found
```
🔎 [Utils] Searching for email pattern in JD text
ℹ️  [Utils] Found 0 email(s) in text: []
⚠️  [Utils] No valid email found in JD text
⚠️  [Service] Company email not found in job description
```
**Fix:** Update JD text to include company email

### Scenario 2: CV File Missing
```
✓ [Service] Session data fetched successfully
✓ [Service] CV file path: /nonexistent/cv.pdf
📧 [SendGrid] Starting email send - To: hr@company.com
❌ [SendGrid] CV file not found at: /nonexistent/cv.pdf
```
**Fix:** Check `raw_file_url` in `cv_profiles` table

### Scenario 3: Database Error
```
🔍 [Repository] Querying analysis_sessions table for session_id=999
❌ [Repository] Database query error: Connection refused
```
**Fix:** Ensure database is running and accessible

## 📊 Log Format

Each log message includes:
- **Timestamp** - When it happened
- **Logger Name** - `app.feature.email.*`
- **Level** - INFO, DEBUG, WARNING, ERROR
- **Icon** - Visual indicator (📧, ✓, ❌, etc.)
- **Context** - [Layer] message
- **Details** - Relevant data (session_id, email, etc.)

Example:
```
2026-06-04 10:30:45,123 - app.feature.email.api.endpoints.send_email - INFO - 📧 [API] Received request to send job application for session_id=1
```

## 🎓 Best Practices

1. **Check logs in order** - Follow the flow from API → Service → Repository
2. **Look for errors** - Search for ❌ or ERROR
3. **Track session_id** - All logs include session_id for correlation
4. **Monitor success** - Look for ✅ messages
5. **Inspect details** - DEBUG logs show intermediate values

## 📞 Troubleshooting Commands

```bash
# View live logs
python3 run.py 2>&1 | grep "email"

# Filter errors only
python3 run.py 2>&1 | grep "❌"

# Track specific session
python3 run.py 2>&1 | grep "session_id=1"

# View SendGrid operations
python3 run.py 2>&1 | grep "\[SendGrid\]"
```
