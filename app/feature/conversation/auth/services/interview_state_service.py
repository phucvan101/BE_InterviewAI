# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.auth.models.interview_state import InterviewState


class InterviewStateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, conversation_id: int) -> InterviewState:
        """Lấy hoặc tạo state mới cho conversation."""
        stmt = select(InterviewState).where(
            InterviewState.conversation_id == conversation_id
        )
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()

        if not state:
            state = InterviewState.create_default(conversation_id)
            self.db.add(state)
            await self.db.flush()
            await self.db.refresh(state)

        return state

    async def get(self, conversation_id: int) -> InterviewState | None:
        """Lấy state hiện tại."""
        stmt = select(InterviewState).where(
            InterviewState.conversation_id == conversation_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, conversation_id: int) -> bool:
        """Xóa state của conversation."""
        state = await self.get(conversation_id)
        if state:
            await self.db.delete(state)
            await self.db.flush()
            return True
        return False
