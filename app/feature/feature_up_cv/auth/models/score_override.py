from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class ScoreOverride(Base):
    __tablename__ = "cv_score_overrides"

    id = Column(Integer, primary_key=True, index=True)
    cv_id = Column(String, index=True, nullable=False)
    jd_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=True)
    
    overridden_scores = Column(JSON, nullable=False)
    rationale = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
