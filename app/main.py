# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.feature.auth.api.router import api_router
from app.feature.admin.roles.api.router import api_router as admin_roles_router
from app.feature.admin.users.api.router import api_router as admin_users_router
from app.feature.admin.sessions.api.router import api_router as admin_sessions_router
from app.feature.admin.dashboard.api.router import api_router as admin_dashboard_router
from app.feature.feature_up_cv.auth.api.router import router as cv_router
from app.feature.conversation.router import api_router as conversation_router
from app.feature.email.api.endpoints import router as email_router
from app.core.config import settings
from app.core.database import init_db

from app.scripts.ensure_admin import ensure_admin


import logging
logging.basicConfig(level=logging.INFO)
# Disable all SQLAlchemy logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
# Ensure all ORM models are registered with Base.metadata before init_db()
import app.feature.auth.models  # noqa: F401
import app.feature.audit.models  # noqa: F401
import app.feature.admin.roles.models  # noqa: F401
import app.feature.feature_up_cv.auth.models  # noqa: F401
import app.feature.conversation.model  # noqa: F401



# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    print(f"🚀  Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()          # create tables + apply Alembic migrations
    await ensure_admin()
    yield
    # ── Shutdown ──
    print("👋  Shutting down...")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Routes ───────────────────────────────
    app.include_router(api_router, prefix=settings.API_PREFIX)
    app.include_router(admin_roles_router, prefix=settings.API_PREFIX)
    app.include_router(admin_users_router, prefix=settings.API_PREFIX)
    app.include_router(admin_sessions_router, prefix=settings.API_PREFIX)
    app.include_router(admin_dashboard_router, prefix=settings.API_PREFIX)
    app.include_router(cv_router, prefix=settings.API_PREFIX)
    app.include_router(conversation_router, prefix=settings.API_PREFIX)
    app.include_router(email_router, prefix=settings.API_PREFIX)

    # ── Health check ─────────────────────────
    @app.get("/health", tags=["Health"])
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    return app


app = create_app()
