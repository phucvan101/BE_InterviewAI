# FastAPI Project Template

Backend REST API với FastAPI, SQLAlchemy (async), JWT auth.

## 🚀 Quick Start

```bash
# 1. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cấu hình .env (copy từ .env.example nếu có)
cp .env .env.local               # chỉnh sửa theo môi trường

# 4. Chạy server
python run.py
# hoặc:
uvicorn app.main:app --reload
```

Mở: http://localhost:8000/docs

---

## 📁 Cấu trúc

```
fastapi-project/
├── app/
│   ├── main.py                  # App factory + lifespan
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── security.py          # JWT + bcrypt
│   │   └── dependencies.py      # Shared FastAPI deps (auth guards)
│   ├── api/
│   │   ├── router.py            # Master APIRouter
│   │   └── endpoints/
│   │       └── user.py          # User CRUD + auth endpoints
│   ├── models/
│   │   └── user.py              # SQLAlchemy ORM model
│   ├── schemas/
│   │   └── user.py              # Pydantic v2 request/response schemas
│   └── services/
│       └── user_service.py      # Business logic layer
├── .env                         # Environment variables
├── requirements.txt
└── run.py                       # Uvicorn entry point
```

---

## 🔑 API Endpoints

| Method | URL | Auth | Mô tả |
|--------|-----|------|-------|
| POST | `/api/v1/users/register` | ❌ | Đăng ký tài khoản |
| POST | `/api/v1/users/login` | ❌ | Đăng nhập → JWT |
| POST | `/api/v1/users/refresh` | ❌ | Làm mới access token |
| GET | `/api/v1/users/me` | ✅ | Thông tin user hiện tại |
| PATCH | `/api/v1/users/me` | ✅ | Cập nhật profile |
| PATCH | `/api/v1/users/me/password` | ✅ | Đổi mật khẩu |
| GET | `/api/v1/users/` | 👑 Admin | Danh sách users (phân trang) |
| GET | `/api/v1/users/{id}` | 👑 Admin | Chi tiết user |
| PATCH | `/api/v1/users/{id}` | 👑 Admin | Cập nhật user |
| PATCH | `/api/v1/users/{id}/deactivate` | 👑 Admin | Vô hiệu hoá user |
| DELETE | `/api/v1/users/{id}` | 👑 Admin | Xoá user |
| GET | `/health` | ❌ | Health check |

---

## 🗄️ Database

- **Development:** SQLite (mặc định, không cần cài thêm)
- **Production:** PostgreSQL (thay `DATABASE_URL` trong `.env`)

```env
# SQLite
DATABASE_URL=sqlite+aiosqlite:///./fastapi.db

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
```

---

## 🏗️ Thêm module mới

1. Tạo model: `app/models/interview.py`
2. Tạo schema: `app/schemas/interview.py`
3. Tạo service: `app/services/interview_service.py`
4. Tạo endpoint: `app/api/endpoints/interview.py`
5. Đăng ký router trong `app/api/router.py`

---

## 🔒 Security

- Password hash: **bcrypt** (passlib)
- Token: **HS256 JWT** (python-jose)
- Access token: 30 phút (configurable)
- Refresh token: 7 ngày (configurable)
# BE_InterviewAI
