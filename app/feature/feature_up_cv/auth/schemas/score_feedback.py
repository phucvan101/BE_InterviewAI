from pydantic import BaseModel, Field
from typing import Optional, Dict

class FeedbackRequest(BaseModel):
    cv_id: str
    jd_id: str
    feedback_text: str = Field(..., min_length=1)

class FeedbackResponse(BaseModel):
    success: bool
    is_overridden: bool
    rationale: str
    new_scores: Optional[Dict[str, float]] = None
    learned_rule: Optional[str] = None
