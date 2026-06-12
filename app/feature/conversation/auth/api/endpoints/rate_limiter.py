# -*- coding: utf-8 -*-
"""
Rate limiting for interview endpoints.
Prevents abuse by limiting the number of LLM calls per user.
"""
import time
import logging
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class InterviewRateLimiter:
    """
    Simple in-memory rate limiter for interview endpoints.
    In production, consider using Redis for distributed rate limiting.
    """

    def __init__(
        self,
        max_questions_per_minute: int = 5,
        max_questions_per_hour: int = 50,
        max_conversations_per_user: int = 10,
    ):
        self.max_questions_per_minute = max_questions_per_minute
        self.max_questions_per_hour = max_questions_per_hour
        self.max_conversations_per_user = max_conversations_per_user

        self._minute_counts: dict[int, list[float]] = defaultdict(list)
        self._hour_counts: dict[int, list[float]] = defaultdict(list)
        self._conversation_counts: dict[int, list[float]] = defaultdict(list)

    def _cleanup_old_entries(self, user_id: int, timestamp: float) -> None:
        """Remove entries older than their time window."""
        cutoff_minute = timestamp - 60
        cutoff_hour = timestamp - 3600

        self._minute_counts[user_id] = [
            t for t in self._minute_counts[user_id] if t > cutoff_minute
        ]
        self._hour_counts[user_id] = [
            t for t in self._hour_counts[user_id] if t > cutoff_hour
        ]
        self._conversation_counts[user_id] = [
            t for t in self._conversation_counts[user_id] if t > cutoff_hour
        ]

    def check_question_rate(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Check if user can ask another question.
        Returns (allowed, error_message).
        """
        timestamp = time.time()
        self._cleanup_old_entries(user_id, timestamp)

        minute_count = len(self._minute_counts[user_id])
        hour_count = len(self._hour_counts[user_id])

        if minute_count >= self.max_questions_per_minute:
            retry_after = int(60 - (timestamp - self._minute_counts[user_id][0])) + 1
            return False, f"Quá nhiều câu hỏi. Thử lại sau {retry_after} giây."

        if hour_count >= self.max_questions_per_hour:
            return False, "Đã đạt giới hạn câu hỏi trong giờ. Thử lại sau."

        return True, None

    def record_question(self, user_id: int) -> None:
        """Record that user asked a question."""
        timestamp = time.time()
        self._minute_counts[user_id].append(timestamp)
        self._hour_counts[user_id].append(timestamp)

    def check_conversation_rate(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Check if user can create another conversation.
        Returns (allowed, error_message).
        """
        timestamp = time.time()
        self._cleanup_old_entries(user_id, timestamp)

        conversation_count = len(self._conversation_counts[user_id])
        if conversation_count >= self.max_conversations_per_user:
            return False, f"Đã đạt giới hạn {self.max_conversations_per_user} phiên phỏng vấn."

        return True, None

    def record_conversation(self, user_id: int) -> None:
        """Record that user created a conversation."""
        timestamp = time.time()
        self._conversation_counts[user_id].append(timestamp)

    def get_status(self, user_id: int) -> dict:
        """Get current rate limit status for user."""
        timestamp = time.time()
        self._cleanup_old_entries(user_id, timestamp)

        return {
            "questions_this_minute": len(self._minute_counts[user_id]),
            "questions_this_hour": len(self._hour_counts[user_id]),
            "conversations_this_hour": len(self._conversation_counts[user_id]),
            "limits": {
                "questions_per_minute": self.max_questions_per_minute,
                "questions_per_hour": self.max_questions_per_hour,
                "conversations_per_hour": self.max_conversations_per_user,
            },
        }


rate_limiter = InterviewRateLimiter()


def require_question_rate_limit(user_id: int) -> None:
    """
    Dependency that enforces rate limit for asking questions.
    Raises HTTPException if rate limit exceeded.
    """
    allowed, error = rate_limiter.check_question_rate(user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error,
        )
    rate_limiter.record_question(user_id)


def require_conversation_rate_limit(user_id: int) -> None:
    """
    Dependency that enforces rate limit for creating conversations.
    Raises HTTPException if rate limit exceeded.
    """
    allowed, error = rate_limiter.check_conversation_rate(user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error,
        )
    rate_limiter.record_conversation(user_id)
