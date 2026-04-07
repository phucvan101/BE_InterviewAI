from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── Interview Info ───────────────────────
    title: Mapped[str | None] = mapped_column(String(255))
    job_position: Mapped[str | None] = mapped_column(String(255))
    job_level: Mapped[str | None] = mapped_column(String(100))
    tech_stack: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str | None] = mapped_column(String(50))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    # ── Results ──────────────────────────────
    overall_score: Mapped[float | None] = mapped_column(Float)
    feedback_summary: Mapped[str | None] = mapped_column(Text)

    # ── Timestamps ───────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── ORM Relationships ────────────────────
    user = relationship("User", back_populates="interview_sessions")
    questions = relationship("InterviewQuestion", back_populates="session")

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} user_id={self.user_id}>"