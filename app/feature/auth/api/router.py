from fastapi import APIRouter

from app.feature.auth.api.endpoints.user import router as user_router

api_router = APIRouter()

# Register all endpoint routers here
api_router.include_router(user_router)

# Example: add more routers as the project grows
# from app.api.endpoints.auth import router as auth_router
# from app.api.endpoints.interview import router as interview_router
# api_router.include_router(auth_router)
# api_router.include_router(interview_router)
