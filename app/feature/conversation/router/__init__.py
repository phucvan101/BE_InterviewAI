from fastapi import APIRouter

from app.feature.conversation.router.endpoints.conversation import router as conversation_router

api_router = APIRouter(prefix="/conversations", tags=["Conversations"])
api_router.include_router(conversation_router)

__all__ = ["api_router"]
