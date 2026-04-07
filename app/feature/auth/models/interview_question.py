from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── Question Data ────────────────────────
    question_content: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int | None] = mapped_column(Integer)

    # ── Answer & Evaluation ──────────────────
    user_answer: Mapped[str | None] = mapped_column(Text)
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)

    # ── Timestamps ───────────────────────────
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── ORM Relationships ────────────────────
    session = relationship("InterviewSession", back_populates="questions")

    def __repr__(self) -> str:
        return f"<InterviewQuestion id={self.id} session_id={self.session_id}>"