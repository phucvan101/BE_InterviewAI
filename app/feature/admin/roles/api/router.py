from fastapi import APIRouter

from app.feature.admin.roles.api.endpoints.role import router as role_router

api_router = APIRouter()
api_router.include_router(role_router)
