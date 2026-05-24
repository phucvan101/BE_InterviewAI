from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompanyInfo(Base):
    __tablename__ = "company_infos"

    # ── Primary key ──────────────────────────
    id_ci: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Relationships ────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ── File URLs ────────────────────────────
    parser_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # ── Content ──────────────────────────────
    text_content: Mapped[str | None] = mapped_column(String, nullable=True)
    text_hashed: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Timestamps ───────────────────────────
    upload_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CompanyInfo id_ci={self.id_ci} user_id={self.user_id}>"
