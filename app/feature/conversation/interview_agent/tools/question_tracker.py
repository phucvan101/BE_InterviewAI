# -*- coding: utf-8 -*-
import logging
from typing import Dict, List, TYPE_CHECKING

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

COMMON_TOPICS = [
    "python", "sql", "system_design", "api", "database",
    "testing", "git", "docker", "cloud", "agile",
    "teamwork", "leadership", "communication",
    "problem_solving", "project_management",
    "security", "performance", "debugging",
]


class QuestionTrackerTool(BaseTool):
    name: str = "question_tracker"
    description: str = (
        "Theo dõi các chủ đề đã hỏi. "
        "Actions: mark_asked (đánh dấu đã hỏi), get_topics (lấy ds topic), get_next_topic (gợi ý topic tiếp)"
    )

    def __init__(self, conversation_id: int, jd_text: str = "", db: "AsyncSession" = None):
        super().__init__()
        self._conversation_id = conversation_id
        self._jd_text = jd_text
        self._db = db
        self._state = None

    async def _get_state(self):
        """Lấy state từ database."""
        if self._state is None and self._db:
            from app.feature.conversation.auth.services.interview_state_service import InterviewStateService
            service = InterviewStateService(self._db)
            self._state = await service.get_or_create(self._conversation_id)
        return self._state

    async def _run_async(self, action: str, topic: str = "", question: str = "") -> str:
        """Async version of run with DB support."""
        state = await self._get_state()

        if action == "mark_asked":
            if topic and state:
                state.mark_topic_asked(topic, question)
                count = state.question_counts.get(topic, 1)
                return f"Đã đánh dấu topic '{topic}' với {count} câu hỏi"
            return f"Đã đánh dấu topic '{topic}' với 1 câu hỏi"

        if action == "get_topics":
            if state:
                return state.get_topics_summary()
            return "Chưa hỏi topic nào."

        if action == "get_next_topic":
            if not self._jd_text:
                return "Không có JD text để gợi ý topic."

            jd_lower = self._jd_text.lower()
            if state:
                asked = set(state.asked_topics.keys())
            else:
                asked = set()

            suggestions = []
            for t in COMMON_TOPICS:
                if t not in asked and t.replace("_", " ") in jd_lower:
                    suggestions.append(t)
                elif t not in asked and any(w in jd_lower for w in t.split("_")):
                    suggestions.append(t)

            if suggestions:
                return f"Gợi ý topic tiếp theo: {', '.join(suggestions[:3])}"
            return "Đã hỏi hết các topic phổ biến. Có thể đi sâu hơn vào topic đã hỏi hoặc chuyển giai đoạn behavioral."

        return f"Action '{action}' không hợp lệ. Dùng: mark_asked, get_topics, get_next_topic"

    def _run(self, action: str, topic: str = "", question: str = "") -> str:
        """Sync wrapper."""
        return f"QuestionTracker[conv={self._conversation_id}] action={action} (async mode)"
