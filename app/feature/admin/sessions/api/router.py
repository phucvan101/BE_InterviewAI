from fastapi import APIRouter

from app.feature.admin.sessions.api.endpoints.session import router as admin_session_router

api_router = APIRouter()
api_router.include_router(admin_session_router)
