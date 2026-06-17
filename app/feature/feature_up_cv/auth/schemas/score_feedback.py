"""
Score Feedback schemas — request/response models for the Feedback Agent
HTTP endpoint.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    """Body of ``POST /scoring-feedback/``."""

    id_session: Optional[int] = Field(
        None,
        description=(
            "Optional. If supplied, the agent uses the CV/JD text "
            "snapshots stored on this AnalysisSession."
        ),
    )
    cv_id: Optional[int] = Field(
        None, description="CV record id (used if id_session is not provided)."
    )
    jd_id: Optional[int] = Field(
        None, description="JD record id (used if id_session is not provided)."
    )
    feedback_text: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural-language complaint / suggestion from the user.",
    )
    current_scores: Optional[Dict[str, float]] = Field(
        None,
        description=(
            "Optional map of section -> score so the agent knows the "
            "current breakdown. If omitted, the latest session scores are "
            "used."
        ),
    )

    def validate_targets(self) -> None:
        """Both (id_session) and (cv_id + jd_id) cannot be empty."""
        if not self.id_session and not (self.cv_id and self.jd_id):
            raise ValueError(
                "Cần cung cấp id_session hoặc (cv_id và jd_id)."
            )


# ── Response ───────────────────────────────────────────────────────────────
class SynonymAdded(BaseModel):
    base_skill: str
    synonym: str


class FeedbackResponse(BaseModel):
    success: bool
    is_valid_complaint: bool
    rationale: str
    synonyms_added: List[SynonymAdded] = []
    learned_rule: Optional[str] = None
    proposed_overrides: Optional[Dict[str, float]] = None
    feedback_log_id: Optional[int] = None
