# -*- coding: utf-8 -*-
from fastapi import APIRouter

# ── Import routers ─────────────────────────
from app.feature.auth.api.endpoints.google_oauth import router as google_oauth_router
from app.feature.auth.api.endpoints.user import router as user_router
from app.feature.auth.api.endpoints.cv_profile import router as cv_router
from app.feature.auth.api.endpoints.upload_cv import router as upload_cv_router
from app.feature.auth.api.endpoints.job_description import router as job_description_router
from app.feature.auth.api.endpoints.company_research import router as company_research_router
from app.feature.auth.api.endpoints.question import router as question_router
from app.feature.auth.api.endpoints.interview_session import router as interview_router
from app.feature.auth.api.endpoints.interview_question import router as iq_router
from app.feature.auth.api.endpoints.analysis import router as analysis_router

# ── Main API router ────────────────────────
api_router = APIRouter()

# ── Register all endpoint routers ──────────
api_router.include_router(user_router)
api_router.include_router(cv_router)
api_router.include_router(upload_cv_router)
api_router.include_router(job_description_router)
api_router.include_router(company_research_router)
api_router.include_router(question_router)
api_router.include_router(interview_router)
api_router.include_router(iq_router)
api_router.include_router(analysis_router)
api_router.include_router(google_oauth_router)

# Example: add more routers as the project grows
# from app.api.endpoints.auth import router as auth_router
# from app.api.endpoints.interview import router as interview_router
# api_router.include_router(auth_router)
# api_router.include_router(interview_router)
