from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CVProfile(Base):
    __tablename__ = "cv_profiles"

    # ── Primary key ──────────────────────────
    id_cv: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── File URLs ────────────────────────────
    parser_file_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_file_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # ── Content ──────────────────────────────
    text_hashed: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_vector_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Timestamps ───────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
        nullable=False,
    )

    # ── ORM Relationships ────────────────────
    # user = relationship("User", back_populates="cv_profiles")  # Cross-feature relationship

    def __repr__(self) -> str:
        return f"<CVProfile id_cv={self.id_cv} user_id={self.user_id}>"