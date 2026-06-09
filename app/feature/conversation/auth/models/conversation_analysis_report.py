# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.feature.conversation.auth.models.conversation import Conversation


class ConversationAnalysisReport(Base):
    """Model lưu báo cáo phân tích sau phỏng vấn"""
    __tablename__ = "conversation_analysis_reports"
    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_conversation_analysis_reports_conversation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_grade: Mapped[str] = mapped_column(String(10), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_coach_insights: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    knowledge_gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    study_plan: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_ai_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    conversation: Mapped["Conversation"] = relationship(back_populates="analysis_report")

    def __repr__(self) -> str:
        return f"<ConversationAnalysisReport conversation_id={self.conversation_id} score={self.overall_score}>"
