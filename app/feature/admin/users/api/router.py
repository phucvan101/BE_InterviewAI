from fastapi import APIRouter

from app.feature.admin.users.api.endpoints.user import router as admin_user_router

api_router = APIRouter()
api_router.include_router(admin_user_router)

