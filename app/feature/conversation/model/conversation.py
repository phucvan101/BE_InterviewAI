import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.feature.auth.models.user import User


class ConversationStatus(str, Enum):
    """Status của conversation"""
    ACTIVE = "active"          # Đang diễn ra
    COMPLETED = "completed"    # Hoàn thành
    PAUSED = "paused"          # Tạm dừng


class MessageRole(str, Enum):
    """Role của message"""
    INTERVIEWER = "interviewer"  # Từ AI
    CANDIDATE = "candidate"      # Từ ứng viên
    SYSTEM = "system"            # System message


class Conversation(Base):
    """Model lưu trữ phiên phỏng vấn"""
    __tablename__ = "conversations"

    # ── Primary key ──────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # ── Session ID (UUID) ────────────────────
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # ── Foreign key ──────────────────────────
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ── Interview Info ──────────────────────
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    cv_profile: Mapped[str] = mapped_column(Text, nullable=False)
    
    # ── Status ──────────────────────────────
    status: Mapped[str] = mapped_column(String(20), default=ConversationStatus.ACTIVE, nullable=False)
    
    # ── Interview result ────────────────────
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON result
    score: Mapped[Optional[float]] = mapped_column(nullable=True)  # Overall score

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
    user: Mapped["User"] = relationship(
        back_populates="conversations"
    )
    
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Conversation session_id={self.session_id} user_id={self.user_id} status={self.status}>"


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
