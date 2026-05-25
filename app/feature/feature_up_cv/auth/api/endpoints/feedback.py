# -*- coding: utf-8 -*-
"""
Feedback endpoints for skill matching user corrections.
Used by the agent loop to learn from user feedback and improve matching quality.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User


router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ── Request Models ────────────────────────────────────────────────────────────

class SkillFeedbackItem(BaseModel):
    criterion_id: str
    skill_name: str
    system_verdict: str  # PERFECT_MATCH / RELEVANCE_MATCH / MISS_MATCH
    user_verdict: str  # "correct" / "should_be_higher" / "should_be_lower" / "missing_skill" / "extra_skill"
    user_reason: Optional[str] = None
    severity: Optional[str] = None  # "minor" / "major" / "critical"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SubmitFeedbackRequest(BaseModel):
    session_id: str
    overall_verdict: str  # "accepted" / "rejected" / "partial"
    skill_feedbacks: List[SkillFeedbackItem]
    missing_skill_suggestions: List[str] = []
    extra_skill_suggestions: List[str] = []
    comment: Optional[str] = None


class SubmitFeedbackResponse(BaseModel):
    success: bool
    rules_created: int = 0
    message: str


class RuleInfo(BaseModel):
    rule_id: str
    pattern_type: str
    pattern_description: str
    target: str
    action: str
    confidence: float
    use_count: int
    status: str
    created_at: str


class GetRulesResponse(BaseModel):
    rules: List[RuleInfo]
    total: int


class GetSkillStatsResponse(BaseModel):
    skill_name: str
    total_predictions: int
    accuracy: float
    confidence_label: str
    updated_at: str


# ── Helper: import scoring modules safely ────────────────────────────────────

_feedback_impl_available = False
_skill_feedback_model = None
_global_rules_model = None
_confidence_tracker = None
_rules_engine = None
_feedback_impl_error: Optional[str] = None

try:
    from app.feature.feature_up_cv.scoring.feedback_models import SkillFeedback as _SkillFeedbackModel
    from app.feature.feature_up_cv.scoring.skill_confidence_tracker import get_confidence_tracker
    from app.feature.feature_up_cv.scoring.global_rules_engine import get_rules_engine
    _skill_feedback_model = _SkillFeedbackModel
    _confidence_tracker = get_confidence_tracker
    _rules_engine = get_rules_engine
    _feedback_impl_available = True
except ImportError as e:
    _feedback_impl_error = str(e)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/skill-match", response_model=SubmitFeedbackResponse)
async def submit_skill_feedback(
    request: SubmitFeedbackRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Submit user feedback cho kết quả skill matching.

    Agent loop sẽ:
    1. Ghi nhận feedback vào confidence tracker
    2. Tạo global rules nếu feedback có giá trị tổng quát
    3. Cập nhật rules engine
    """
    if not _feedback_impl_available:
        return SubmitFeedbackResponse(
            success=False,
            rules_created=0,
            message=f"Feedback module not available: {_feedback_impl_error}",
        )

    try:
        tracker = _confidence_tracker()
        engine = _rules_engine()

        rules_created = 0
        overall_verdict = request.overall_verdict

        for item in request.skill_feedbacks:
            fb = _skill_feedback_model(
                session_id=request.session_id,
                criterion_id=item.criterion_id,
                skill_name=item.skill_name,
                system_verdict=item.system_verdict,
                user_verdict=item.user_verdict,
                user_reason=item.user_reason,
                severity=item.severity,
                confidence=item.confidence,
            )

            # Record into confidence tracker
            tracker.record_feedback(
                criterion_name=item.skill_name,
                semantic_sim=0.0,  # Not available here, tracker handles gracefully
                system_verdict=item.system_verdict,
                user_verdict=item.user_verdict,
            )

            # Generate global rules if applicable
            rule = engine.generate_rules_from_feedback(
                feedback=fb,
                cv_domain="",  # Not available in this context
                jd_domain="",
                semantic_sim=0.0,
            )
            if rule:
                rules_created += 1

        return SubmitFeedbackResponse(
            success=True,
            rules_created=rules_created,
            message=f"Feedback recorded. {rules_created} global rule(s) created.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}",
        )


@router.get("/rules", response_model=GetRulesResponse)
async def get_global_rules(
    pattern_type: Optional[str] = None,
    target: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy danh sách global rules hiện tại.
    Dùng để inspect/debug rules đang active.
    """
    if not _feedback_impl_available:
        return GetRulesResponse(rules=[], total=0)

    try:
        engine = _rules_engine()
        if pattern_type or target:
            rules = engine.get_rules_for_pattern(pattern_type, target)
        else:
            rules = engine.get_active_rules()

        rule_infos = [
            RuleInfo(
                rule_id=r.rule_id,
                pattern_type=r.pattern_type,
                pattern_description=r.pattern_description,
                target=r.target,
                action=r.action,
                confidence=r.confidence,
                use_count=r.use_count,
                status=r.status,
                created_at=r.created_at.isoformat(),
            )
            for r in rules
        ]

        return GetRulesResponse(rules=rule_infos, total=len(rule_infos))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch rules: {str(e)}",
        )


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Deactivate a global rule."""
    if not _feedback_impl_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback module not available",
        )

    try:
        engine = _rules_engine()
        engine.deactivate_rule(rule_id)
        return {"success": True, "message": f"Rule {rule_id} deactivated."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate rule: {str(e)}",
        )


@router.get("/skill-stats/{skill_name}", response_model=GetSkillStatsResponse)
async def get_skill_stats(
    skill_name: str,
    current_user: User = Depends(get_current_active_user),
):
    """Lấy confidence stats cho một skill cụ thể."""
    if not _feedback_impl_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback module not available",
        )

    try:
        tracker = _confidence_tracker()
        stats = tracker.get_skill_stats(skill_name)
        accuracy, conf_label = tracker.get_confidence(skill_name)

        return GetSkillStatsResponse(
            skill_name=skill_name,
            total_predictions=stats.get("total_predictions", 0),
            accuracy=stats.get("accuracy", 0.0),
            confidence_label=conf_label,
            updated_at=stats.get("updated_at", ""),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skill stats: {str(e)}",
        )
