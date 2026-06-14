# Example Logs Output

## 🚀 Complete Flow Example

### Call API
```bash
curl -X POST http://localhost:8000/api/v1/email/send-job-application \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
```

### Expected Logs

```
2026-06-04 10:30:45,123 - app.feature.email.api.endpoints.send_email - INFO - 📧 [API] Received request to send job application for session_id=1
2026-06-04 10:30:45,124 - app.feature.email.api.endpoints.send_email - DEBUG - ✓ [API] EmailApplicationService initialized for session_id=1
2026-06-04 10:30:45,125 - app.feature.email.service.email_application_service - INFO - 📬 [Service] Starting email send process for session_id=1
2026-06-04 10:30:45,126 - app.feature.email.service.email_application_service - DEBUG - 🔍 [Service] Fetching session data for session_id=1
2026-06-04 10:30:45,127 - app.feature.email.repository.analysis_session_repository - DEBUG - 🔍 [Repository] Querying analysis_sessions table for session_id=1
2026-06-04 10:30:45,150 - app.feature.email.repository.analysis_session_repository - DEBUG - ✓ [Repository] Analysis session found - session_id=1, cv_id=5, jd_length=2845
2026-06-04 10:30:45,151 - app.feature.email.repository.analysis_session_repository - DEBUG - 🔍 [Repository] Querying cv_profiles table for cv_id=5
2026-06-04 10:30:45,165 - app.feature.email.repository.analysis_session_repository - INFO - ✓ [Repository] CV profile found - cv_id=5, file_path=/uploads/cv/cv_5.pdf
2026-06-04 10:30:45,166 - app.feature.email.service.email_application_service - DEBUG - ✓ [Service] Session data fetched successfully - session_id=1
2026-06-04 10:30:45,167 - app.feature.email.service.email_application_service - DEBUG - 🔎 [Service] Extracting company email from JD - session_id=1
2026-06-04 10:30:45,168 - app.feature.email.utils.email_extractor - DEBUG - 🔎 [Utils] Searching for email pattern in JD text
2026-06-04 10:30:45,169 - app.feature.email.utils.email_extractor - DEBUG - ℹ️  [Utils] Found 2 email(s) in text: ['contact@techcorp.com', 'jobs@techcorp.com']
2026-06-04 10:30:45,170 - app.feature.email.utils.email_extractor - INFO - ✓ [Utils] Selected email: contact@techcorp.com
2026-06-04 10:30:45,171 - app.feature.email.service.email_application_service - INFO - ✓ [Service] Company email extracted: contact@techcorp.com
2026-06-04 10:30:45,172 - app.feature.email.service.email_application_service - DEBUG - 🔎 [Service] Extracting company name from JD - session_id=1
2026-06-04 10:30:45,173 - app.feature.email.utils.email_extractor - DEBUG - 🔎 [Utils] Searching for company name pattern in JD text
2026-06-04 10:30:45,174 - app.feature.email.utils.email_extractor - INFO - ✓ [Utils] Company name extracted: TechCorp Inc
2026-06-04 10:30:45,175 - app.feature.email.service.email_application_service - INFO - ✓ [Service] Company name extracted: TechCorp Inc
2026-06-04 10:30:45,176 - app.feature.email.service.email_application_service - INFO - 📧 [Service] Sending email via SendGrid - To: contact@techcorp.com, Company: TechCorp Inc
2026-06-04 10:30:45,177 - app.feature.email.service.sendgrid_service - INFO - ✓ [SendGrid] Service initialized - From: nguyenvanphuc10124@gmail.com
2026-06-04 10:30:45,178 - app.feature.email.service.sendgrid_service - INFO - 📧 [SendGrid] Starting email send - To: contact@techcorp.com, Company: TechCorp Inc
2026-06-04 10:30:45,179 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] CV file verified - Path: /uploads/cv/cv_5.pdf
2026-06-04 10:30:45,180 - app.feature.email.service.sendgrid_service - DEBUG - 📝 [SendGrid] Email subject: Job Application - TechCorp Inc
2026-06-04 10:30:45,181 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] Mail object created
2026-06-04 10:30:45,182 - app.feature.email.service.sendgrid_service - DEBUG - 📎 [SendGrid] Creating attachment from file: /uploads/cv/cv_5.pdf
2026-06-04 10:30:45,185 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] File encoded - Name: cv_5.pdf, Size: 45678 bytes
2026-06-04 10:30:45,186 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] Attachment object created
2026-06-04 10:30:45,187 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] CV attachment added - File: cv_5.pdf
2026-06-04 10:30:45,188 - app.feature.email.service.sendgrid_service - DEBUG - 📤 [SendGrid] Sending email via SendGrid API...
2026-06-04 10:30:46,245 - app.feature.email.service.sendgrid_service - INFO - ✅ [SendGrid] Email sent successfully to contact@techcorp.com (Status: 202)
2026-06-04 10:30:46,246 - app.feature.email.service.email_application_service - INFO - ✅ [Service] Email sent successfully - Email sent successfully to contact@techcorp.com
2026-06-04 10:30:46,247 - app.feature.email.api.endpoints.send_email - INFO - ✅ [API] Successfully sent email for session_id=1: Email sent successfully to contact@techcorp.com

Response: {"success": true, "message": "Email sent successfully to contact@techcorp.com"}
```

## ❌ Error Example 1: Email Not Found

### Logs
```
2026-06-04 10:31:10,123 - app.feature.email.api.endpoints.send_email - INFO - 📧 [API] Received request to send job application for session_id=2
2026-06-04 10:31:10,124 - app.feature.email.api.endpoints.send_email - DEBUG - ✓ [API] EmailApplicationService initialized for session_id=2
2026-06-04 10:31:10,125 - app.feature.email.service.email_application_service - INFO - 📬 [Service] Starting email send process for session_id=2
2026-06-04 10:31:10,126 - app.feature.email.service.email_application_service - DEBUG - 🔍 [Service] Fetching session data for session_id=2
...
2026-06-04 10:31:10,170 - app.feature.email.service.email_application_service - DEBUG - 🔎 [Service] Extracting company email from JD - session_id=2
2026-06-04 10:31:10,171 - app.feature.email.utils.email_extractor - DEBUG - 🔎 [Utils] Searching for email pattern in JD text
2026-06-04 10:31:10,172 - app.feature.email.utils.email_extractor - DEBUG - ℹ️  [Utils] Found 0 email(s) in text: []
2026-06-04 10:31:10,173 - app.feature.email.utils.email_extractor - WARNING - ⚠️  [Utils] No valid email found in JD text
2026-06-04 10:31:10,174 - app.feature.email.service.email_application_service - WARNING - ⚠️  [Service] Company email not found in job description - session_id=2
2026-06-04 10:31:10,175 - app.feature.email.api.endpoints.send_email - WARNING - ⚠️  [API] Failed to send email for session_id=2: Company email not found in job description

Response: {"success": false, "message": "Company email not found in job description"}
```

## ❌ Error Example 2: Session Not Found

### Logs
```
2026-06-04 10:32:00,123 - app.feature.email.api.endpoints.send_email - INFO - 📧 [API] Received request to send job application for session_id=999
2026-06-04 10:32:00,124 - app.feature.email.api.endpoints.send_email - DEBUG - ✓ [API] EmailApplicationService initialized for session_id=999
2026-06-04 10:32:00,125 - app.feature.email.service.email_application_service - INFO - 📬 [Service] Starting email send process for session_id=999
2026-06-04 10:32:00,126 - app.feature.email.service.email_application_service - DEBUG - 🔍 [Service] Fetching session data for session_id=999
2026-06-04 10:32:00,127 - app.feature.email.repository.analysis_session_repository - DEBUG - 🔍 [Repository] Querying analysis_sessions table for session_id=999
2026-06-04 10:32:00,150 - app.feature.email.repository.analysis_session_repository - WARNING - ⚠️  [Repository] Analysis session not found - session_id=999
2026-06-04 10:32:00,151 - app.feature.email.service.email_application_service - ERROR - ❌ [Service] Analysis session not found - session_id=999
2026-06-04 10:32:00,152 - app.feature.email.api.endpoints.send_email - WARNING - ⚠️  [API] Failed to send email for session_id=999: Analysis session not found

Response: {"success": false, "message": "Analysis session not found"}
```

## ❌ Error Example 3: CV File Missing

### Logs
```
...
2026-06-04 10:33:15,190 - app.feature.email.service.sendgrid_service - INFO - 📧 [SendGrid] Starting email send - To: contact@company.com, Company: Company Inc
2026-06-04 10:33:15,191 - app.feature.email.service.sendgrid_service - DEBUG - ✓ [SendGrid] CV file verified - Path: /uploads/cv/cv_999.pdf
2026-06-04 10:33:15,192 - app.feature.email.service.sendgrid_service - ERROR - ❌ [SendGrid] CV file not found at: /uploads/cv/cv_999.pdf
2026-06-04 10:33:15,193 - app.feature.email.service.email_application_service - ERROR - ❌ [Service] Failed to send email - CV file not found at: /uploads/cv/cv_999.pdf
2026-06-04 10:33:15,194 - app.feature.email.api.endpoints.send_email - WARNING - ⚠️  [API] Failed to send email for session_id=3: CV file not found at: /uploads/cv/cv_999.pdf

Response: {"success": false, "message": "CV file not found at: /uploads/cv/cv_999.pdf"}
```

## 🔍 Log Analysis Tips

### Quick Scan
1. Look for ✅ to confirm success
2. Look for ❌ to find errors
3. Look for ⚠️ to see warnings

### Detailed Analysis
1. Find the session_id in question
2. Follow the flow: API → Service → Repository
3. Check timestamps to see durations
4. Look for the actual error message

### Common Patterns

**Successful Flow:**
```
📧 [API] Received ... → 📬 [Service] Starting ... → 🔍 [Repository] Querying ... → 📧 [SendGrid] Starting ... → ✅ [SendGrid] Success
```

**Failed at Email Extraction:**
```
📧 [API] Received ... → 📬 [Service] Starting ... → 🔎 [Utils] Searching ... → ⚠️ [Utils] No valid email ... → ❌ [Service] ... not found
```

**Failed at Database:**
```
📧 [API] Received ... → 📬 [Service] Starting ... → 🔍 [Repository] Querying ... → ❌ [Repository] not found
```

## 📊 Monitoring Commands

```bash
# Real-time email API logs
tail -f logs/email_api.log | grep "email"

# Only show errors
grep "❌" logs/email_api.log

# Show a specific session
grep "session_id=1" logs/email_api.log

# Show SendGrid operations
grep "\[SendGrid\]" logs/email_api.log

# Count successful emails
grep "✅.*Email sent successfully" logs/email_api.log | wc -l

# Show last 50 lines
tail -50 logs/email_api.log
```

## 📈 Performance Metrics from Logs

By analyzing timestamps, you can calculate:

1. **Total duration:**
   ```
   Start: 2026-06-04 10:30:45,123
   End: 2026-06-04 10:30:46,247
   Duration: ~1.1 seconds
   ```

2. **Component durations:**
   - API → Service: 2ms
   - Service → Repository: 26ms
   - Repository query: 23ms
   - Email extraction: 4ms
   - SendGrid send: 1057ms

3. **Bottlenecks:** SendGrid API call is the slowest (1057ms)
