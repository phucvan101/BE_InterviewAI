import asyncpg
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────
    APP_NAME: str = "FastAPI Project"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── Server ───────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Database ─────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://admin:123456@localhost:5433/mydb"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)

        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        return value

    # ── Security ─────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ── Default Admin (seeded via Alembic) ───
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_ADMIN_FULL_NAME: str = "Administrator"

    # ── Google OAuth ─────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_TOKENINFO_URI: str = "https://oauth2.googleapis.com/tokeninfo"
    GOOGLE_ALLOWED_ISSUERS: List[str] = ["https://accounts.google.com", "accounts.google.com"]
    GOOGLE_SCOPES: List[str] = ["openid", "email", "profile"]

    # ── CORS ─────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── SMTP ─────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = None

    # ── Frontend ─────────────────────────────
    FRONTEND_URL: Optional[str] = None

    # ── Google OAuth ─────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # ── AI / Speech ──────────────────────────
    DEEPGRAM_API_KEY: Optional[str] = None
    DEEPGRAM_MODEL: str = "general"

    GEMINI_API_KEY: Optional[str] = None
    MODEL_NAME: str = "models/gemini-2.5-flash"

    # ── Embedding / Vector Search ─────────────
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    FAISS_INDEX_DIR: Optional[str] = None
    EMBEDDING_CACHE_DIR: Optional[str] = None


# Singleton instance
settings = Settings()