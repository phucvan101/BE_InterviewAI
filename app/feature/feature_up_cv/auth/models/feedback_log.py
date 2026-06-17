"""
FeedbackLog model — full audit trail for every user feedback processed by
the Feedback Agent.

The agent receives natural-language complaints about the score ("Tôi đã
làm Next.js 3 năm mà chỉ được 10 điểm skills"), asks the LLM to evaluate
the complaint, and then applies (or rejects) the suggested learning.
Every step is recorded here so the system can:

- reproduce a decision
- measure how often agent overrides are accepted/rejected
- debug hallucination in the LLM evaluator
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_session: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_sessions.id_session", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    id_cv: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id_cv", ondelete="SET NULL"),
        nullable=True,
    )
    id_jd: Mapped[int | None] = mapped_column(
        ForeignKey("job_descriptions.id_jd", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Snapshots (for offline analysis) ──────────────────────────────────
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Agent output ──────────────────────────────────────────────────────
    # Full FeedbackEvaluation pydantic dump (is_valid_complaint, rationale,
    # learned_rule, new_synonyms, proposed_overrides). JSONB on Postgres,
    # JSON on SQLite for local tests.
    agent_evaluation: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    applied_overrides: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    learned_rule: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<FeedbackLog id={self.id} user={self.user_id} "
            f"valid={self.is_valid}>"
        )
