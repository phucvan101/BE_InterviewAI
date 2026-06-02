from pydantic import BaseModel
from typing import Optional, Dict

class FeedbackRequest(BaseModel):
    cv_id: str
    jd_id: str
    feedback_text: str

class FeedbackResponse(BaseModel):
    success: bool
    is_overridden: bool
    rationale: str
    new_scores: Optional[Dict[str, int]] = None
    learned_rule: Optional[str] = None
