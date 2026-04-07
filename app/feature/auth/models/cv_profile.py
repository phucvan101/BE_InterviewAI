from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CVProfile(Base):
    __tablename__ = "cv_profiles"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── CV Content ───────────────────────────
    summary: Mapped[str | None] = mapped_column(Text)
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[str | None] = mapped_column(Text)
    education: Mapped[str | None] = mapped_column(Text)
    work_experience: Mapped[str | None] = mapped_column(Text)
    cv_file_url: Mapped[str | None] = mapped_column(String(255))

    # ── Timestamps ───────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # ── ORM Relationships ────────────────────
    user = relationship("User", back_populates="cv_profiles")

    def __repr__(self) -> str:
        return f"<CVProfile id={self.id} user_id={self.user_id}>"