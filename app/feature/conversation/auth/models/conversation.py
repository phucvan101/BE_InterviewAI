# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

<<<<<<< HEAD:app/feature/conversation/model/conversation.py
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
=======
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
>>>>>>> 7a94a79 (thay đổi workflow conversation):app/feature/conversation/auth/models/conversation.py
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.feature.auth.models.user import User
    from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
<<<<<<< HEAD:app/feature/conversation/model/conversation.py
=======
    from app.feature.conversation.auth.models.conversation_message import ConversationMessage
    from app.feature.conversation.auth.models.conversation_analysis_report import ConversationAnalysisReport
>>>>>>> 7a94a79 (thay đổi workflow conversation):app/feature/conversation/auth/models/conversation.py


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class Conversation(Base):
    __tablename__ = "conversations"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
<<<<<<< HEAD:app/feature/conversation/model/conversation.py
    
    
=======

>>>>>>> 7a94a79 (thay đổi workflow conversation):app/feature/conversation/auth/models/conversation.py
    # ── Session ID (UUID) ────────────────────
    session_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    # ── Foreign key ──────────────────────────
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    analysis_session_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("analysis_sessions.id_session", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
<<<<<<< HEAD:app/feature/conversation/model/conversation.py
    
    user: Mapped["User"] = relationship(
        back_populates="conversations"
    )
=======
>>>>>>> 7a94a79 (thay đổi workflow conversation):app/feature/conversation/auth/models/conversation.py

    # ── Interview Info ──────────────────────
    job_position: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    cv_profile: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Status ──────────────────────────────
    status: Mapped[str] = mapped_column(String(20), default=ConversationStatus.ACTIVE, nullable=False)

    # ── Interview result ────────────────────
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(nullable=True)

    # ── Interview timing ────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    interview_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ── Interview timing ────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    interview_duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ── Timestamps ──────────────────────────
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

    # ── ORM Relationships ────────────────────
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    analysis_report: Mapped[Optional["ConversationAnalysisReport"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    analysis_session: Mapped[Optional["AnalysisSession"]] = relationship(
        lazy="selectin",
    )

    analysis_report: Mapped[Optional["ConversationAnalysisReport"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )

    analysis_session: Mapped[Optional["AnalysisSession"]] = relationship(
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Conversation session_id={self.session_id} user_id={self.user_id} status={self.status}>"
<<<<<<< HEAD:app/feature/conversation/model/conversation.py


class ConversationMessage(Base):
    """Model lưu trữ messages trong phiên phỏng vấn"""
    __tablename__ = "conversation_messages"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    # ── Foreign key ──────────────────────────
    conversation_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # ── Message content ─────────────────────
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "interviewer", "candidate", "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Actual message content
    
    # ── Question & Answer (optional) ────────
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # If role is interviewer
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # If role is candidate

    # ── Timestamps ──────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── ORM Relationships ────────────────────
    conversation: Mapped[Conversation] = relationship(
        back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage id={self.id} role={self.role} conversation_id={self.conversation_id}>"


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

    conversation: Mapped[Conversation] = relationship(
        back_populates="analysis_report"
    )

    def __repr__(self) -> str:
        return f"<ConversationAnalysisReport conversation_id={self.conversation_id} score={self.overall_score}>"
=======
>>>>>>> 7a94a79 (thay đổi workflow conversation):app/feature/conversation/auth/models/conversation.py
