# -*- coding: utf-8 -*-
import json
import logging
from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.conversation.auth.models.conversation import Conversation, ConversationStatus
from app.feature.conversation.auth.models.conversation_message import ConversationMessage, MessageRole

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Conversation CRUD ──────────────────────────────────────────────────────

    async def create_conversation(
        self,
        user_id: int,
        job_description: str,
        cv_profile: str,
        job_position: str | None = None,
        analysis_session_id: int | None = None,
        session_id: str | None = None,
        analysis_data: dict | None = None,
    ) -> Conversation:
        if session_id:
            existing = await self.get_conversation_by_session_id(session_id)
            if existing:
                return existing

        conversation_kwargs = {
            "user_id": user_id,
            "analysis_session_id": analysis_session_id,
            "job_position": (job_position or "").strip() or "General Interview",
            "job_description": job_description,
            "cv_profile": cv_profile,
            "status": ConversationStatus.ACTIVE,
            "analysis_data": analysis_data,
        }
        if session_id:
            conversation_kwargs["session_id"] = session_id

        conversation = Conversation(**conversation_kwargs)
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        logger.info(f"Created conversation: session_id={conversation.session_id}, user_id={user_id}")
        return conversation

    async def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_session_id(self, session_id: str) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_user_conversations(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> tuple[list[Conversation], int]:
        offset = (page - 1) * page_size

        count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        if status:
            count_stmt = count_stmt.where(Conversation.status == status)

        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        stmt = select(Conversation).where(Conversation.user_id == user_id).order_by(desc(Conversation.created_at))
        if status:
            stmt = stmt.where(Conversation.status == status)

        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        return conversations, total

    async def end_conversation(
        self,
        conversation_id: int,
        result: Optional[dict] = None,
        score: Optional[float] = None,
    ) -> Conversation:
        conversation = await self.get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.status = ConversationStatus.COMPLETED
        if result:
            conversation.result = json.dumps(result, ensure_ascii=False)
        if score is not None:
            conversation.score = score

        await self.db.flush()
        await self.db.refresh(conversation)
        logger.info(f"Ended conversation: id={conversation_id}, score={score}")
        return conversation

    # ── Message Management ────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            question=question,
            answer=answer,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        logger.info(f"Added message: id={message.id}, role={role}, conversation_id={conversation_id}")
        return message

    async def get_conversation_messages(
        self,
        conversation_id: int,
        limit: Optional[int] = None,
    ) -> list[ConversationMessage]:
        stmt = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.created_at)

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_last_message(self, conversation_id: int) -> Optional[ConversationMessage]:
        result = await self.db.execute(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id
            ).order_by(desc(ConversationMessage.id)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_messages_by_role(
        self,
        conversation_id: int,
        role: str,
    ) -> list[ConversationMessage]:
        result = await self.db.execute(
            select(ConversationMessage).where(
                and_(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role == role,
                )
            ).order_by(ConversationMessage.created_at)
        )
        return result.scalars().all()
