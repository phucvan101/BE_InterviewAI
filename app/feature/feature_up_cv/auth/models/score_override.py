"""
ScoreOverride model — audit trail of section-level score overrides.

The Feedback Agent can override one or more sections of the hybrid score
(experience / skills / education / career / company_fit) when a user's
complaint is judged to be valid. Every override is recorded here so that
we can re-score, audit, and roll back changes if needed.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScoreOverride(Base):
    __tablename__ = "score_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_cv: Mapped[int] = mapped_column(
        ForeignKey("cv_profiles.id_cv", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_jd: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id_jd", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_session: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_sessions.id_session", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Override details ──────────────────────────────────────────────────
    # One of: experience_score, skills_score, education_score,
    # career_objectives_score, company_fit_score
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    original_value: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    override_value: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="agent_auto"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ScoreOverride id={self.id} user={self.user_id} "
            f"section={self.section} {self.original_value}->{self.override_value}>"
        )
