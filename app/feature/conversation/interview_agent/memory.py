# -*- coding: utf-8 -*-
from typing import Dict, Any, List, Optional
import logging

from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class InterviewMemory:
    def __init__(self, conversation_id: int, k: int = 20):
        self.conversation_id = conversation_id
        self.k = k
        self._messages: List[Any] = []
        self._question_count = 0
        self._asked_topics: Dict[str, List[int]] = {}

    def save_context(self, question: str, answer: str) -> None:
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


_memory_store: Dict[int, InterviewMemory] = {}


def get_memory(conversation_id: int, k: int = 20) -> InterviewMemory:
    if conversation_id not in _memory_store:
        _memory_store[conversation_id] = InterviewMemory(conversation_id, k)
    return _memory_store[conversation_id]


def clear_memory(conversation_id: int) -> None:
    _memory_store.pop(conversation_id, None)
    logger.info(f"[InterviewMemory] Cleared memory for conversation {conversation_id}")
