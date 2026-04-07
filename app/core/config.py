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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/postgres"

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

    # ── CORS ─────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── SMTP ─────────────────────────────────
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None

    # ── Frontend ─────────────────────────────
    frontend_url: Optional[str] = None

    # ── Google OAuth ─────────────────────────
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None

    # ── AI / Speech ──────────────────────────
    deepgram_api_key: Optional[str] = None
    deepgram_model: str = "general"

    gemini_api_key: Optional[str] = None
    model_name: str = "models/gemini-2.5-flash"


# Singleton instance
settings = Settings()