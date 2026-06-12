# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InterviewState(Base):
    """Lưu trạng thái interview: flow phase và question tracker."""
    __tablename__ = "interview_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    current_phase_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    question_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    asked_topics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            "min_questions_per_topic": 1,
            "max_questions_per_topic": 3,
            "total_question_limit": 15,
        }
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @classmethod
    def create_default(cls, conversation_id: int) -> "InterviewState":
        """Tạo state mới với giá trị mặc định."""
        default_phases = [
            {"key": "warmup", "name": "Warm-up: Giới thiệu & trải nghiệm gần đây"},
            {"key": "technical", "name": "Technical: Kỹ năng cốt lõi"},
            {"key": "behavioral", "name": "Behavioral: teamwork & problem-solving"},
            {"key": "culture", "name": "Culture Fit: môi trường & giá trị"},
            {"key": "closing", "name": "Closing: câu hỏi của ứng viên"},
        ]
        return cls(
            conversation_id=conversation_id,
            current_phase_index=0,
            phases=default_phases,
            question_counts={},
            asked_topics={},
        )

    def get_current_phase(self) -> dict:
        """Lấy phase hiện tại."""
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return self.phases[-1] if self.phases else {"key": "unknown", "name": "Unknown"}

    def advance_phase(self) -> bool:
        """Chuyển sang phase tiếp theo. Trả về True nếu chuyển thành công."""
        if self.current_phase_index < len(self.phases) - 1:
            self.current_phase_index += 1
            return True
        return False

    def mark_topic_asked(self, topic: str, question: str) -> None:
        """Đánh dấu topic đã được hỏi."""
        if topic not in self.asked_topics:
            self.asked_topics[topic] = []
        if question not in self.asked_topics[topic]:
            self.asked_topics[topic].append(question)
            self.question_counts[topic] = self.question_counts.get(topic, 0) + 1

    def get_topics_summary(self) -> str:
        """Lấy tóm tắt các topic đã hỏi."""
        if not self.asked_topics:
            return "Chưa hỏi topic nào."
        lines = [f"  - {t}: {len(qs)} câu hỏi" for t, qs in self.asked_topics.items()]
        return "Các topic đã hỏi:\n" + "\n".join(lines)

    def __repr__(self) -> str:
        return f"<InterviewState conversation_id={self.conversation_id} phase={self.current_phase_index}>"
