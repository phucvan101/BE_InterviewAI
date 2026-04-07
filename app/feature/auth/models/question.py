from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Question(Base):
    __tablename__ = "questions"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Question Content ─────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(50))

    tech_tags: Mapped[dict | None] = mapped_column(JSON)
    expected_answer: Mapped[str | None] = mapped_column(Text)

    # ── Status ───────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Relationships ────────────────────────
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    # ── Timestamps ───────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── ORM Relationships ────────────────────
    creator = relationship("User")

    def __repr__(self) -> str:
        return f"<Question id={self.id}>"