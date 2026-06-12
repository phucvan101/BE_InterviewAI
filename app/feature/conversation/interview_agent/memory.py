# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from langchain_core.messages import HumanMessage, AIMessage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.feature.conversation.auth.models.conversation_message import ConversationMessage

logger = logging.getLogger(__name__)


class InterviewMemory:
    def __init__(self, conversation_id: int, k: int = 20, db: "AsyncSession" = None):
        self.conversation_id = conversation_id
        self.k = k
        self._db = db
        self._messages: List[Any] = []
        self._question_count = 0
        self._asked_topics: Dict[str, List[int]] = {}

    async def load_from_db(self) -> None:
        """Load messages from database."""
        if not self._db:
            logger.warning(f"[InterviewMemory:{self.conversation_id}] No db session, cannot load from DB")
            return

        try:
            from sqlalchemy import select
            from app.feature.conversation.auth.models.conversation_message import ConversationMessage

            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == self.conversation_id)
                .order_by(ConversationMessage.created_at)
                .limit(self.k * 2)
            )
            result = await self._db.execute(stmt)
            db_messages = result.scalars().all()

            self._messages = []
            for msg in db_messages:
                if msg.role == "interviewer" and msg.question:
                    self._messages.append(HumanMessage(content=msg.question))
                elif msg.role == "candidate" and msg.answer:
                    self._messages.append(AIMessage(content=msg.answer))

            self._question_count = len([m for m in db_messages if m.role == "interviewer"])
            logger.info(f"[InterviewMemory:{self.conversation_id}] Loaded {len(db_messages)} messages from DB")

        except Exception as e:
            logger.error(f"[InterviewMemory:{self.conversation_id}] Failed to load from DB: {e}")

    def save_context(self, question: str, answer: str) -> None:
        """Save Q&A context (messages are already saved to DB in the endpoint)."""
        self._messages.append(HumanMessage(content=question))
        self._messages.append(AIMessage(content=answer))
        if len(self._messages) > self.k * 2:
            self._messages = self._messages[-(self.k * 2):]
        self._question_count += 1
        logger.info(f"[InterviewMemory:{self.conversation_id}] Saved Q&A #{self._question_count}")

    def get_history(self) -> str:
        lines = []
        for msg in self._messages:
            if isinstance(msg, HumanMessage):
                lines.append(f"Interviewer: {msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"Candidate: {msg.content}")
        return "\n".join(lines)

    def get_history_messages(self) -> List[Any]:
        return list(self._messages)

    def mark_topic_asked(self, topic: str, question: str) -> None:
        if topic not in self._asked_topics:
            self._asked_topics[topic] = []
        if question not in self._asked_topics[topic]:
            self._asked_topics[topic].append(question)
        logger.debug(f"[InterviewMemory:{self.conversation_id}] Topic '{topic}' asked ({len(self._asked_topics[topic])} times)")

    def get_asked_topics(self) -> Dict[str, int]:
        return {topic: len(questions) for topic, questions in self._asked_topics.items()}

    @property
    def question_count(self) -> int:
        return self._question_count


async def get_memory(conversation_id: int, k: int = 20, db: "AsyncSession" = None) -> InterviewMemory:
    """Get interview memory for a conversation. Always reads from DB if session provided."""
    memory = InterviewMemory(conversation_id, k, db)
    if db:
        await memory.load_from_db()
    return memory


def clear_memory(conversation_id: int) -> None:
    """Clear memory (no-op now, DB handles persistence)."""
    logger.info(f"[InterviewMemory] Clear called for conversation {conversation_id} (DB handles persistence)")
