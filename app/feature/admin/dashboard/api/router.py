from fastapi import APIRouter

from app.feature.admin.dashboard.api.endpoints.dashboard import router as dashboard_router

api_router = APIRouter()
api_router.include_router(dashboard_router)
