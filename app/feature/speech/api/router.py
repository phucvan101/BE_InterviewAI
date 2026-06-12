from fastapi import APIRouter

from app.feature.speech.api.endpoints.speech import router as speech_router

api_router = APIRouter(prefix="/speech", tags=["Speech"])
api_router.include_router(speech_router)

__all__ = ["api_router"]
