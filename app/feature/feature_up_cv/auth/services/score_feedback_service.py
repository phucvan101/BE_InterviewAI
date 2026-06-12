import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.feature.auth.models.user import User
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.models.company_info import CompanyInfo
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.feature_up_cv.auth.models.score_override import ScoreOverride
from app.feature.feature_up_cv.auth.schemas.score_feedback import FeedbackRequest, FeedbackResponse
from app.feature.feature_up_cv.core.file_storage import load_parser_result, save_result_analysis
from app.feature.feature_up_cv.feedback_agent.agent import feedback_agent
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score

logger = logging.getLogger(__name__)

_SCORE_LIMITS = {
    "experience_score": 50.0,
    "skills_score": 30.0,
    "education_score": 10.0,
    "career_objectives_score": 10.0,
    "company_fit_score": 10.0,
}


def _parse_positive_id(raw_id: str, field_name: str) -> int:
    try:
        value = int(raw_id)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer")

    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _sanitize_score_overrides(raw_overrides: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Keep only known score keys and clamp values to each section's scale."""
    if not isinstance(raw_overrides, dict):
        return {}

    clean: Dict[str, float] = {}
    for key, value in raw_overrides.items():
        if key not in _SCORE_LIMITS:
            logger.warning("[FEEDBACK_AGENT] Ignoring unsupported override key: %s", key)
            continue

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            logger.warning("[FEEDBACK_AGENT] Ignoring non-numeric override %s=%r", key, value)
            continue

        max_value = _SCORE_LIMITS[key]
        clean[key] = round(min(max(numeric_value, 0.0), max_value), 2)

    return clean


async def _load_owned_documents(
    cv_id: int,
    jd_id: int,
    db: AsyncSession,
    current_user: Optional[User],
) -> Tuple[CVProfile, JobDescription]:
    cv_record = (
        await db.execute(select(CVProfile).where(CVProfile.id_cv == cv_id))
    ).scalar_one_or_none()
    jd_record = (
        await db.execute(select(JobDescription).where(JobDescription.id_jd == jd_id))
    ).scalar_one_or_none()

    if not cv_record:
        raise ValueError("CV not found")
    if not jd_record:
        raise ValueError("Job description not found")

    if current_user and not getattr(current_user, "is_superuser", False):
        if cv_record.user_id != current_user.id or jd_record.user_id != current_user.id:
            raise PermissionError("You do not have permission to submit feedback for this CV/JD pair")

    return cv_record, jd_record


def _extract_text_from_record(record: Any) -> str:
    raw_file_url = getattr(record, "raw_file_url", None)
    if not raw_file_url:
        return ""

    try:
        if not Path(raw_file_url).exists():
            return ""

        from app.feature.feature_up_cv.core.text_extract import extract_text_auto

        return extract_text_auto(raw_file_url) or ""
    except Exception as exc:
        logger.warning("[FEEDBACK_AGENT] Could not extract text from %s: %s", raw_file_url, exc)
        return ""


async def _get_cv_text(cv_id: str, db: AsyncSession, current_user: Optional[User] = None) -> str:
    parsed_id = _parse_positive_id(cv_id, "cv_id")
    record = (
        await db.execute(select(CVProfile).where(CVProfile.id_cv == parsed_id))
    ).scalar_one_or_none()
    if not record:
        return ""
    if current_user and not getattr(current_user, "is_superuser", False) and record.user_id != current_user.id:
        raise PermissionError("You do not have permission to read this CV")
    return _extract_text_from_record(record)


async def _get_jd_text(jd_id: str, db: AsyncSession, current_user: Optional[User] = None) -> str:
    parsed_id = _parse_positive_id(jd_id, "jd_id")
    record = (
        await db.execute(select(JobDescription).where(JobDescription.id_jd == parsed_id))
    ).scalar_one_or_none()
    if not record:
        return ""
    if current_user and not getattr(current_user, "is_superuser", False) and record.user_id != current_user.id:
        raise PermissionError("You do not have permission to read this job description")
    return _extract_text_from_record(record)


async def _load_company_data(session: AnalysisSession, db: AsyncSession) -> dict:
    if not session.id_ci:
        return {}

    company_record = (
        await db.execute(select(CompanyInfo).where(CompanyInfo.id_ci == session.id_ci))
    ).scalar_one_or_none()
    if not company_record or not company_record.parser_file_url:
        return {}

    return load_parser_result(company_record.parser_file_url) or {}


def _build_response_data(analysis_result: dict) -> dict:
    from app.feature.feature_up_cv.auth.api.endpoints.analysis import (
        _build_areas_for_development,
        _build_experience_detail_response,
        _build_main_strengths,
        _build_recommendation_response,
        _build_skills_detail,
    )

    return {
        "overall_score": analysis_result.get("overall_score", 0),
        "summary": analysis_result.get("summary", ""),
        "detailed_scores": analysis_result.get("detailed_scores", {}),
        "embedding_similarity": analysis_result.get("embedding_similarity", 0.0),
        "score_rationale": analysis_result.get("score_rationale", ""),
        "career_objectives_rationale": analysis_result.get("career_objectives_rationale", ""),
        "company_fit_rationale": analysis_result.get("company_fit_rationale", ""),
        "matched_skills": analysis_result.get("matched_skills", []),
        "related_skills": analysis_result.get("related_skills", []),
        "missing_skills": analysis_result.get("missing_skills", []),
        "skills_detail": _build_skills_detail(analysis_result),
        "experience_assessment": analysis_result.get("experience_assessment", ""),
        "experience_detail": _build_experience_detail_response(analysis_result),
        "main_strengths": _build_main_strengths(analysis_result),
        "areas_for_development": _build_areas_for_development(analysis_result),
        "recommendation": _build_recommendation_response(analysis_result),
        "cv_candidate": analysis_result.get("cv_candidate", ""),
        "job_position": analysis_result.get("job_position", ""),
    }


async def _apply_overrides_to_sessions(
    cv_id: int,
    jd_id: int,
    user_id: Optional[int],
    clean_overrides: Dict[str, float],
    rationale: str,
    db: AsyncSession,
) -> int:
    session_stmt = select(AnalysisSession).where(
        AnalysisSession.id_cv == cv_id,
        AnalysisSession.id_jd == jd_id,
    )
    if user_id is not None:
        session_stmt = session_stmt.where(AnalysisSession.user_id == user_id)

    sessions = (await db.execute(session_stmt)).scalars().all()
    for session in sessions:
        cv_rec = (
            await db.execute(select(CVProfile).where(CVProfile.id_cv == session.id_cv))
        ).scalar_one_or_none()
        jd_rec = (
            await db.execute(select(JobDescription).where(JobDescription.id_jd == session.id_jd))
        ).scalar_one_or_none()

        cv_data = load_parser_result(cv_rec.parser_file_url) if cv_rec and cv_rec.parser_file_url else {}
        jd_data = load_parser_result(jd_rec.parser_file_url) if jd_rec and jd_rec.parser_file_url else {}
        company_data = await _load_company_data(session, db)

        analysis_result = calculate_hybrid_score(
            cv_data=cv_data,
            jd_data=jd_data,
            company_data=company_data,
            score_overrides={**clean_overrides, "rationale": rationale},
        )
        response_data = _build_response_data(analysis_result)
        result_file_path = save_result_analysis(
            response_data,
            user_id=session.user_id,
            id_cv=session.id_cv,
            id_jd=session.id_jd,
            id_ci=session.id_ci,
        )

        detailed_scores = response_data.get("detailed_scores", {})
        session.score = response_data["overall_score"]
        session.experience_score = detailed_scores.get(
            "experience_score",
            clean_overrides.get("experience_score", session.experience_score),
        )
        session.skills_score = detailed_scores.get(
            "skills_total_score",
            detailed_scores.get(
                "skills_score",
                clean_overrides.get("skills_score", session.skills_score),
            ),
        )
        session.education_score = detailed_scores.get(
            "education_score",
            clean_overrides.get("education_score", session.education_score),
        )
        session.career_objectives_score = detailed_scores.get(
            "career_objectives_score",
            clean_overrides.get("career_objectives_score", session.career_objectives_score),
        )
        session.companyfit_score = detailed_scores.get(
            "company_fit_score",
            clean_overrides.get("company_fit_score", session.companyfit_score),
        )
        session.result_analysis_file_url = str(result_file_path)

    return len(sessions)


async def handle_feedback(
    request: FeedbackRequest,
    db: AsyncSession,
    current_user: Optional[User] = None,
) -> FeedbackResponse:
    """
    Evaluate scoring feedback, persist safe overrides, and re-score owned sessions.
    """
    cv_id = _parse_positive_id(request.cv_id, "cv_id")
    jd_id = _parse_positive_id(request.jd_id, "jd_id")
    user_id = getattr(current_user, "id", None)
    is_superuser = bool(getattr(current_user, "is_superuser", False))

    logger.info("[FEEDBACK_AGENT] Feedback received: cv_id=%s, jd_id=%s", cv_id, jd_id)

    cv_record, jd_record = await _load_owned_documents(cv_id, jd_id, db, current_user)

    raw_cv_text = _extract_text_from_record(cv_record) or "(CV text was not found in the system)"
    jd_text = _extract_text_from_record(jd_record) or "(JD text was not found in the system)"

    try:
        agent_result = await feedback_agent.run(
            cv_text=raw_cv_text,
            jd_text=jd_text,
            feedback_text=request.feedback_text,
            apply_learning=False,
        )
    except Exception as exc:
        logger.error("[FEEDBACK_AGENT] Agent failed: %s", exc, exc_info=True)
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale=f"Agent system error: {str(exc)[:100]}",
        )

    if not agent_result.is_valid_complaint:
        return FeedbackResponse(
            success=True,
            is_overridden=False,
            rationale=agent_result.rationale,
            learned_rule=None,
        )

    clean_overrides = _sanitize_score_overrides(agent_result.proposed_overrides)
    if not clean_overrides:
        feedback_agent.apply_learning(agent_result, request.feedback_text)
        return FeedbackResponse(
            success=True,
            is_overridden=False,
            rationale=agent_result.rationale,
            learned_rule=agent_result.learned_rule,
        )

    try:
        override_stmt = select(ScoreOverride).where(
            ScoreOverride.cv_id == str(cv_id),
            ScoreOverride.jd_id == str(jd_id),
        )
        if not is_superuser and user_id is not None:
            override_stmt = override_stmt.where(ScoreOverride.user_id == str(user_id))
        override_stmt = override_stmt.order_by(ScoreOverride.id.desc()).limit(1)

        existing_override = (await db.execute(override_stmt)).scalar_one_or_none()
        if existing_override:
            existing_override.overridden_scores = clean_overrides
            existing_override.rationale = agent_result.rationale
            if user_id is not None:
                existing_override.user_id = str(user_id)
        else:
            db.add(
                ScoreOverride(
                    cv_id=str(cv_id),
                    jd_id=str(jd_id),
                    user_id=str(user_id) if user_id is not None else None,
                    overridden_scores=clean_overrides,
                    rationale=agent_result.rationale,
                )
            )

        await db.flush()
        session_user_id = None if is_superuser else user_id
        updated_sessions = await _apply_overrides_to_sessions(
            cv_id=cv_id,
            jd_id=jd_id,
            user_id=session_user_id,
            clean_overrides=clean_overrides,
            rationale=agent_result.rationale,
            db=db,
        )
        await db.commit()
        logger.info(
            "[FEEDBACK_AGENT] Override saved and %s analysis session(s) re-scored.",
            updated_sessions,
        )
    except Exception as exc:
        logger.error("[FEEDBACK_AGENT] Could not save override or re-score: %s", exc, exc_info=True)
        await db.rollback()
        return FeedbackResponse(
            success=False,
            is_overridden=False,
            rationale=f"Could not save override or re-score: {str(exc)[:160]}",
            learned_rule=agent_result.learned_rule,
        )

    feedback_agent.apply_learning(agent_result, request.feedback_text)
    return FeedbackResponse(
        success=True,
        is_overridden=True,
        rationale=agent_result.rationale,
        new_scores=clean_overrides,
        learned_rule=agent_result.learned_rule,
    )
