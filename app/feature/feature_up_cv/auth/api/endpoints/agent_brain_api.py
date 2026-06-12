# -*- coding: utf-8 -*-
"""
Agent Brain API Endpoints

Các endpoints để:
1. Trigger Agent Brain analysis cho một session
2. Xem patterns đã phát hiện
3. Xem rules đã học
4. Xem analysis report
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.feature_up_cv.core.file_storage import load_parser_result
from app.feature.feature_up_cv.feedback_agent.agent_brain_service import agent_brain_service


router = APIRouter(prefix="/agent-brain", tags=["Agent Brain"])


class TriggerAnalysisRequest(BaseModel):
    """Request để trigger Agent Brain analysis"""
    session_id: Optional[int] = None
    cv_id: Optional[str] = None
    jd_id: Optional[str] = None
    expected_score_min: Optional[float] = None
    expected_score_max: Optional[float] = None
    auto_apply_rules: bool = False


class ApplyRulesRequest(BaseModel):
    """Request để apply rules đã học vào memory"""
    pass


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_with_agent_brain(
    request: TriggerAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Agent Brain analysis cho một case cụ thể.

    Agent Brain sẽ:
    1. Phân tích kết quả scoring
    2. Tìm root cause nếu score không như mong đợi
    3. Sinh rules từ phân tích (nếu có)
    4. Trả về báo cáo chi tiết

    Nếu auto_apply_rules=True, rules sẽ được lưu vào memory tự động.
    """
    try:
        # Load session data
        session = None
        cv_data = None
        jd_data = None
        scoring_result = None

        if request.session_id:
            from sqlalchemy import select
            session_stmt = select(AnalysisSession).where(AnalysisSession.id_session == request.session_id)
            session = (await db.execute(session_stmt)).scalar_one_or_none()

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {request.session_id}"
                )

            # Load CV and JD data
            cv_stmt = select(CVProfile).where(CVProfile.id_cv == session.id_cv)
            cv_record = (await db.execute(cv_stmt)).scalar_one_or_none()

            jd_stmt = select(JobDescription).where(JobDescription.id_jd == session.id_jd)
            jd_record = (await db.execute(jd_stmt)).scalar_one_or_none()

            if cv_record and cv_record.parser_file_url:
                cv_data = load_parser_result(cv_record.parser_file_url)

            if jd_record and jd_record.parser_file_url:
                jd_data = load_parser_result(jd_record.parser_file_url)

            # Load scoring result
            if session.result_analysis_file_url:
                scoring_result = load_parser_result(session.result_analysis_file_url)

            # Use session score as actual
            actual_score = session.score if session.score is not None else 0

        else:
            # Load by CV/JD IDs
            if request.cv_id and request.jd_id:
                from sqlalchemy import select

                cv_stmt = select(CVProfile).where(CVProfile.id_cv == int(request.cv_id))
                cv_record = (await db.execute(cv_stmt)).scalar_one_or_none()

                jd_stmt = select(JobDescription).where(JobDescription.id_jd == int(request.jd_id))
                jd_record = (await db.execute(jd_stmt)).scalar_one_or_none()

                if cv_record and cv_record.parser_file_url:
                    cv_data = load_parser_result(cv_record.parser_file_url)

                if jd_record and jd_record.parser_file_url:
                    jd_data = load_parser_result(jd_record.parser_file_url)

        if not cv_data or not jd_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CV or JD data not found"
            )

        if not scoring_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scoring result not found. Please run analysis first."
            )

        # Determine expected range
        if request.expected_score_min is not None and request.expected_score_max is not None:
            expected_range = (request.expected_score_min, request.expected_score_max)
        else:
            # Use JD's experience requirement to estimate
            jd_exp = jd_data.get("structured", {}).get("experience_years", 3)
            if jd_exp >= 5:
                expected_range = (60, 85)  # Senior
            elif jd_exp >= 2:
                expected_range = (45, 70)  # Mid
            else:
                expected_range = (30, 60)  # Junior/Entry

        # Generate case ID
        case_id = f"session_{request.session_id}" if request.session_id else f"cv_{request.cv_id}_jd_{request.jd_id}"

        # Run Agent Brain analysis
        analysis_result = agent_brain_service.analyze_feedback(
            cv_data=cv_data,
            jd_data=jd_data,
            scoring_result=scoring_result,
            expected_range=expected_range,
            case_id=case_id,
        )

        # Auto-apply rules if requested
        rules_added = []
        if request.auto_apply_rules and analysis_result.suggested_rules:
            apply_result = agent_brain_service.apply_learning()
            rules_added = apply_result.get("rule_ids", [])

        return {
            "success": True,
            "case_id": case_id,
            "actual_score": analysis_result.actual_score,
            "expected_range": analysis_result.expected_range,
            "root_cause": analysis_result.root_cause,
            "reasons": analysis_result.reasons,
            "patterns_detected": analysis_result.patterns_detected,
            "suggested_rules": analysis_result.suggested_rules,
            "rules_applied": rules_added,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent Brain analysis failed: {str(e)}"
        )


@router.post("/apply-rules", status_code=status.HTTP_200_OK)
async def apply_learned_rules(
    current_user: User = Depends(get_current_active_user),
):
    """
    Áp dụng các rules đã học vào FAISS memory.
    """
    try:
        result = agent_brain_service.apply_learning()
        return {
            "success": True,
            "rules_added": result["rules_added"],
            "rule_ids": result["rule_ids"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply rules: {str(e)}"
        )


@router.get("/report", status_code=status.HTTP_200_OK)
async def get_analysis_report(
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy báo cáo phân tích tổng hợp từ Agent Brain.

    Bao gồm:
    - Summary: tổng số cases, accuracy rate
    - Patterns: các patterns đã phát hiện
    - Suggested Rules: rules được đề xuất
    """
    try:
        report = agent_brain_service.get_analysis_report()
        return {
            "success": True,
            "report": report,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get report: {str(e)}"
        )


@router.get("/patterns", status_code=status.HTTP_200_OK)
async def get_detected_patterns(
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy danh sách patterns đã được phát hiện.
    """
    try:
        report = agent_brain_service.get_analysis_report()
        return {
            "success": True,
            "patterns": report.get("patterns", []),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get patterns: {str(e)}"
        )


@router.get("/memory-stats", status_code=status.HTTP_200_OK)
async def get_memory_stats(
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy thống kê FAISS memory hiện tại.
    """
    try:
        stats = agent_brain_service.get_memory_stats()
        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory stats: {str(e)}"
        )


@router.get("/rules", status_code=status.HTTP_200_OK)
async def get_learned_rules(
    query: Optional[str] = None,
    top_k: int = 10,
    current_user: User = Depends(get_current_active_user),
):
    """
    Lấy danh sách rules đã học từ memory.

    Args:
        query: Text để search rules liên quan (tùy chọn)
        top_k: Số lượng rules tối đa trả về
    """
    try:
        from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory

        if query:
            rules = agent_memory.get_relevant_rules(query=query, top_k=top_k, threshold=0.3)
            return {
                "success": True,
                "rules": [
                    {
                        "text": r[0],
                        "metadata": r[1] if len(r) > 1 else {}
                    }
                    for r in rules
                ],
                "total": len(rules),
            }
        else:
            stats = agent_brain_service.get_memory_stats()
            return {
                "success": True,
                "total_rules": stats.get("total_rules", 0),
                "active_rules": stats.get("active_rules", 0),
                "by_type": stats.get("by_type", {}),
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rules: {str(e)}"
        )


@router.delete("/history", status_code=status.HTTP_200_OK)
async def clear_analysis_history(
    current_user: User = Depends(get_current_active_user),
):
    """
    Xóa lịch sử phân tích (không xóa memory).
    """
    try:
        agent_brain_service.clear_analysis_history()
        return {
            "success": True,
            "message": "Analysis history cleared",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear history: {str(e)}"
        )


@router.get("/test-pattern-matching", status_code=status.HTTP_200_OK)
async def test_pattern_matching(
    cv_domain: str,
    jd_domain: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Test xem Agent Brain nhận diện career change như thế nào.

    Args:
        cv_domain: Domain của CV (e.g., "marketing", "tech_backend")
        jd_domain: Domain của JD (e.g., "tech_backend")
    """
    try:
        non_tech = ["marketing", "sales", "finance", "hr", "operations"]
        tech = ["tech_ai", "tech_backend", "tech_frontend", "tech_data", "tech_devops"]

        is_career_change = False
        change_type = "none"

        if cv_domain in non_tech and jd_domain in tech:
            is_career_change = True
            change_type = "non_tech_to_tech"
        elif cv_domain in tech and jd_domain in non_tech:
            is_career_change = True
            change_type = "tech_to_non_tech"
        elif cv_domain == jd_domain:
            change_type = "same_domain"
        else:
            change_type = "different_domain_same_category"

        return {
            "success": True,
            "cv_domain": cv_domain,
            "jd_domain": jd_domain,
            "is_career_change": is_career_change,
            "change_type": change_type,
            "recommended_action": _get_recommended_action(change_type),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test failed: {str(e)}"
        )


def _get_recommended_action(change_type: str) -> str:
    """Get recommended action based on change type"""
    recommendations = {
        "non_tech_to_tech": "Apply CAREER_CHANGE_PENALTY 55-65% and SEVERE_DOMAIN_MISMATCH rules",
        "tech_to_non_tech": "Apply moderate career change penalty (40-50%)",
        "same_domain": "No special action needed - same domain",
        "different_domain_same_category": "Apply DOMAIN_EXPERIENCE_PENALTY (40-60%)",
    }
    return recommendations.get(change_type, "No specific action recommended")
