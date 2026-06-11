# BE_InterviewAI

Backend REST API cho InterviewAI với FastAPI, SQLAlchemy (async), JWT auth và Google OAuth.

## 🚀 Quick Start

```bash
# 1. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env theo mục "Cấu hình môi trường"

# 4. Chạy server
python run.py
# hoặc:
uvicorn app.main:app --reload

# tạo file alembic
alembic revision --autogenerate -m "create_users_table"

# chạy tạo quyền
python -m app.scripts.seed_permissions

```

Mở: http://localhost:8000/docs

---

## 📁 Cấu trúc

```
InterviewApi/
├── app/
│   ├── main.py                  # App factory + lifespan
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── security.py          # JWT + bcrypt
│   │   └── dependencies.py      # Shared FastAPI deps (auth guards)
│   └── feature/
│       └── auth/
│           ├── api/
│           │   ├── router.py    # Master APIRouter (auth)
│           │   └── endpoints/
│           │       ├── user.py  # User CRUD + auth endpoints
│           │       └── google_oauth.py  # Google OAuth endpoints
│           ├── models/
│           │   └── user.py      # SQLAlchemy ORM model
│           ├── schemas/
│           │   └── user.py      # Pydantic v2 request/response schemas
│           └── services/
│               ├── user_service.py          # Business logic layer
│               └── google_oauth_service.py  # Google OAuth helpers
├── requirements.txt
├── run.py                       # Uvicorn entry point
├── db_schema_interviewai.csv    # Snapshot schema (tham khảo)
└── logs/
    └── backend-errors.log
```

---

## 🔑 API Endpoints

| Method | URL                                                  | Auth     | Mô tả                                        |
| ------ | ---------------------------------------------------- | -------- | -------------------------------------------- |
| POST   | `/api/v1/users/register`                             | ❌       | Đăng ký tài khoản                            |
| POST   | `/api/v1/users/login`                                | ❌       | Đăng nhập → JWT                              |
| POST   | `/api/v1/users/refresh`                              | ❌       | Làm mới access token                         |
| GET    | `/api/v1/users/me`                                   | ✅       | Thông tin user hiện tại                      |
| PATCH  | `/api/v1/users/me`                                   | ✅       | Cập nhật profile                             |
| PATCH  | `/api/v1/users/me/password`                          | ✅       | Đổi mật khẩu                                 |
| GET    | `/api/v1/users/`                                     | 👑 Admin | Danh sách users (phân trang)                 |
| GET    | `/api/v1/users/{id}`                                 | 👑 Admin | Chi tiết user                                |
| PATCH  | `/api/v1/users/{id}`                                 | 👑 Admin | Cập nhật user                                |
| PATCH  | `/api/v1/users/{id}/deactivate`                      | 👑 Admin | Vô hiệu hoá user                             |
| DELETE | `/api/v1/users/{id}`                                 | 👑 Admin | Xoá user                                     |
| GET    | `/health`                                            | ❌       | Health check                                 |
| GET    | `/api/v1/conversations/analysis-reports`             | ✅       | Danh sách báo cáo phân tích (phân trang)     |
| POST   | `/api/v1/conversations`                              | ✅       | Tạo phiên phỏng vấn; dùng `analysis_session_id` nếu lấy JD/CV từ analysis session |
| POST   | `/api/v1/conversations/{session_id}/retry`           | ✅       | Tạo vòng phỏng vấn mới từ phiên đã có báo cáo, không cần upload lại CV/JD |
| POST   | `/api/v1/conversations/{session_id}/analysis-report` | ✅       | Kết thúc phỏng vấn và tạo báo cáo phân tích  |
| GET    | `/api/v1/conversations/{session_id}/analysis-report` | ✅       | Lấy lại báo cáo phân tích đã tạo             |
| GET    | `/api/v1/conversations/{session_id}/cv-preview`      | ✅       | Preview file CV gốc dạng PDF inline          |
| GET    | `/api/v1/auth/google/login`                          | ❌       | Redirect tới Google OAuth                    |
| GET    | `/api/v1/auth/google/url`                            | ❌       | Lấy Google OAuth consent URL                 |
| GET    | `/api/v1/auth/google/callback`                       | ❌       | Callback exchange code → token + redirect FE |
| POST   | `/api/v1/auth/google/id-token`                       | ❌       | Login với Google ID token                    |
| POST   | `/api/v1/auth/google/code`                           | ❌       | Exchange Google auth code → token            |

---

## 🗄️ Database

- Mặc định dùng **PostgreSQL async** (`asyncpg`).
- `DATABASE_URL` sẽ được tự động normalize từ `postgres://` hoặc `postgresql://`.
- Khi chạy local, bạn cần có PostgreSQL hoặc thay `DATABASE_URL` về database phù hợp với async SQLAlchemy.

```env
DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5432/postgres
```

Khi app start, `init_db()` sẽ `create_all` tự động. Dùng Alembic cho production.

---

## ⚙️ Cấu hình môi trường (.env)

Các biến quan trọng đang dùng trong code:

- `APP_NAME`, `APP_VERSION`, `DEBUG`
- `API_PREFIX`, `HOST`, `PORT`
- `DATABASE_URL`
- `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_USERNAME`, `DEFAULT_ADMIN_PASSWORD`, `DEFAULT_ADMIN_FULL_NAME`
- `ALLOWED_ORIGINS`, `FRONTEND_URL`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
- `GOOGLE_AUTH_URI`, `GOOGLE_TOKEN_URI`, `GOOGLE_TOKENINFO_URI`
- `GOOGLE_ALLOWED_ISSUERS`, `GOOGLE_SCOPES`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` (đã có cấu hình, chưa dùng trong code hiện tại)
- `GEMINI_API_KEY`, `MODEL_NAME`
- `GEMINI_REPORT_API_KEY`, `AI_REPORT_API_KEY`, `REPORT_MODEL_NAME` (tuỳ chọn, dùng riêng cho báo cáo phân tích phỏng vấn)

Ví dụ tối thiểu:

```env
APP_NAME=InterviewAI API
APP_VERSION=1.0.0
DEBUG=true
API_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5432/postgres

SECRET_KEY=change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
FRONTEND_URL=http://localhost:3000

DEFAULT_ADMIN_EMAIL=admin2@example.com
DEFAULT_ADMIN_USERNAME=admin2
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_ADMIN_FULL_NAME=Admin 2

GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

Tạo hoặc khôi phục tài khoản admin từ cấu hình `.env`:

```bash
python -m app.scripts.ensure_admin
```

Script này dùng bcrypt giống hệ thống đăng nhập. Nếu admin đã tồn tại, script sẽ cập nhật mật khẩu và bật lại các cờ `is_active`, `is_verified`, `is_superuser`.

## 🔒 Security

- Password hash: **bcrypt** (tối đa 72 bytes UTF-8)
- Password rule khi register: tối thiểu 8 ký tự, có ít nhất 1 chữ hoa, có ít nhất 1 chữ số
- Token: **HS256 JWT** (python-jose)
- Access token: 30 phút (configurable)
- Refresh token: 7 ngày (configurable)

## 🔑 Google OAuth Flow

Có 2 cách đăng nhập Google:

1. Browser redirect flow: gọi `GET /api/v1/auth/google/login` hoặc `/google/url` để lấy consent URL, Google redirect về `GOOGLE_REDIRECT_URI`, backend đổi code → JWT và redirect về `FRONTEND_URL/auth/callback` (query trả về `access_token` và `refresh_token`).
2. Token-based flow: gọi `POST /api/v1/auth/google/id-token` (FE gửi `id_token`) hoặc `POST /api/v1/auth/google/code` (FE gửi `code`).

## 🏗️ Thêm module mới

1. Tạo model: `app/feature/<module>/models/*.py`
2. Tạo schema: `app/feature/<module>/schemas/*.py`
3. Tạo service: `app/feature/<module>/services/*.py`
4. Tạo endpoint: `app/feature/<module>/api/endpoints/*.py`
5. Đăng ký router trong `app/feature/<module>/api/router.py` và include vào `app/feature/auth/api/router.py` (hoặc router tổng khác nếu có)

---

## 🌐 CORS

`ALLOWED_ORIGINS` mặc định cho phép:

- `http://localhost:3000`
- `http://localhost:5173`
