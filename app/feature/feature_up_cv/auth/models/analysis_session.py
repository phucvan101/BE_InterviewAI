from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    # ── Primary key ──────────────────────────
    id_session: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    id_cv: Mapped[int] = mapped_column(
        ForeignKey("cv_profiles.id_cv", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    id_jd: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id_jd", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    id_ci: Mapped[int | None] = mapped_column(
        ForeignKey("company_infos.id_ci", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # ── Raw Text Snapshots (per session) ─────
    cv_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ci_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Scores ───────────────────────────────
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    experience_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    skills_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    education_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    career_objectives_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    companyfit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    result_analysis_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Timestamps ───────────────────────────
    create_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AnalysisSession id_session={self.id_session} user_id={self.user_id}>"
