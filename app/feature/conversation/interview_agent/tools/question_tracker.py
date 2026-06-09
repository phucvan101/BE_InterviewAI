# -*- coding: utf-8 -*-
import json
import logging
from pathlib import Path
from typing import Dict, List

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

TRACKER_DIR = Path("app/feature/conversation/storage/question_trackers")
TRACKER_DIR.mkdir(parents=True, exist_ok=True)


class QuestionTrackerTool(BaseTool):
    name: str = "question_tracker"
    description: str = (
        "Theo dõi các chủ đề đã hỏi. "
        "Actions: mark_asked (đánh dấu đã hỏi), get_topics (lấy ds topic), get_next_topic (gợi ý topic tiếp)"
    )

    def __init__(self, conversation_id: int, jd_text: str = ""):
        super().__init__()
        self._conversation_id = conversation_id
        self._jd_text = jd_text
        self._tracker_path = TRACKER_DIR / f"{conversation_id}.json"
        self._data: Dict[str, List[str]] = {}
        self._load()

    def _load(self) -> None:
        if self._tracker_path.exists():
            try:
                with open(self._tracker_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.error(f"[QuestionTracker] Failed to load: {e}")
                self._data = {}

    def _save(self) -> None:
        try:
            with open(self._tracker_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[QuestionTracker] Failed to save: {e}")

    def _run(self, action: str, topic: str = "", question: str = "") -> str:
        if action == "mark_asked":
            if topic not in self._data:
                self._data[topic] = []
            if question and question not in self._data[topic]:
                self._data[topic].append(question)
                self._save()
            return f"Đã đánh dấu topic '{topic}' với {len(self._data[topic])} câu hỏi"

        if action == "get_topics":
            if not self._data:
                return "Chưa hỏi topic nào."
            lines = [f"  - {t}: {len(qs)} câu hỏi" for t, qs in self._data.items()]
            return "Các topic đã hỏi:\n" + "\n".join(lines)

        if action == "get_next_topic":
            if not self._jd_text:
                return "Không có JD text để gợi ý topic."

            jd_lower = self._jd_text.lower()
            common_topics = [
                "python", "sql", "system_design", "api", "database",
                "testing", "git", "docker", "cloud", "agile",
                "teamwork", "leadership", "communication",
                "problem_solving", "project_management",
                "security", "performance", "debugging",
            ]

            asked = set(self._data.keys())
            suggestions = []
            for t in common_topics:
                if t not in asked and t.replace("_", " ") in jd_lower:
                    suggestions.append(t)
                elif t not in asked and any(w in jd_lower for w in t.split("_")):
                    suggestions.append(t)

            if suggestions:
                return f"Gợi ý topic tiếp theo: {', '.join(suggestions[:3])}"
            return "Đã hỏi hết các topic phổ biến. Có thể đi sâu hơn vào topic đã hỏi hoặc chuyển giai đoạn behavioral."

        return f"Action '{action}' không hợp lệ. Dùng: mark_asked, get_topics, get_next_topic"
