from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


class FeedbackRequest(BaseModel):
    cv_id: str
    jd_id: str
    feedback_text: str = Field(..., min_length=1)


class AgentBrainAnalysis(BaseModel):
    """Thông tin phân tích từ Agent Brain"""
    root_cause: Optional[str] = None
    reasons: List[str] = []
    patterns_detected: List[str] = []
    suggested_rules: List[Dict[str, Any]] = []
    auto_applied: bool = False


class FeedbackResponse(BaseModel):
    success: bool
    is_overridden: bool
    rationale: str
    new_scores: Optional[Dict[str, float]] = None
    learned_rule: Optional[str] = None
    agent_brain: Optional[AgentBrainAnalysis] = None
