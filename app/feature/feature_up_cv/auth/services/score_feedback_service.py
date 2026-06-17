"""
Score Feedback Service — orchestrates the Feedback Agent flow.

MVP scope:
  - load CV/JD text (from AnalysisSession snapshot, or from the live
    CV/JD parser files)
  - ask the agent to evaluate the complaint
  - if valid: apply synonyms (MVP) and persist a FeedbackLog row
  - always return a ``FeedbackResponse`` with the LLM's rationale

Phase 2 (not implemented yet):
  - apply ``proposed_overrides`` by re-scoring the session
  - persist ``ScoreOverride`` rows
  - record ``learned_rule`` into FAISS memory for future scoring runs
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# The CV/JD parser result files live under the feature-specific
# ``file_storage`` module, not ``app.core.file_storage``.
from app.feature.feature_up_cv.core.file_storage import (  # type: ignore
    load_parser_result,
)
from app.feature.auth.models.user import User
from app.feature.feature_up_cv.auth.models.analysis_session import AnalysisSession
from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile
from app.feature.feature_up_cv.auth.models.feedback_log import FeedbackLog
from app.feature.feature_up_cv.auth.models.job_description import JobDescription
from app.feature.feature_up_cv.auth.models.score_override import ScoreOverride
from app.feature.feature_up_cv.auth.schemas.score_feedback import (
    FeedbackRequest,
    FeedbackResponse,
    SynonymAdded,
)
from app.feature.feature_up_cv.feedback_agent.agent_v2 import get_feedback_agent

logger = logging.getLogger(__name__)


# ── Text loading helpers ──────────────────────────────────────────────────
def _extract_text_from_cv(cv_data: Dict[str, Any]) -> str:
    """Return a single concatenated text blob for the CV."""
    parts: list[str] = []
    personal = cv_data.get("personal_info", {}) or {}
    if personal:
        parts.append(" ".join(str(v) for v in personal.values() if v))
    skills = cv_data.get("skills", []) or []
    if skills:
        parts.append("Skills: " + ", ".join(str(s) for s in skills))
    for exp in cv_data.get("work_experience", []) or []:
        if isinstance(exp, dict):
            parts.append(" ".join(str(v) for v in exp.values() if v))
        else:
            parts.append(str(exp))
    for proj in cv_data.get("projects", []) or []:
        if isinstance(proj, dict):
            parts.append(" ".join(str(v) for v in proj.values() if v))
        else:
            parts.append(str(proj))
    edu = cv_data.get("education", []) or []
    for e in edu:
        if isinstance(e, dict):
            parts.append(" ".join(str(v) for v in e.values() if v))
        else:
            parts.append(str(e))
    return "\n".join(p for p in parts if p)[:8000]  # cap length for LLM


def _extract_text_from_jd(jd_data: Dict[str, Any]) -> str:
    """Return a single concatenated text blob for the JD."""
    if isinstance(jd_data, dict) and "structured" in jd_data:
        jd_struct = jd_data["structured"]
    else:
        jd_struct = jd_data or {}
    parts: list[str] = []
    for k in (
        "job_title",
        "summary",
        "description",
        "responsibilities",
        "requirements",
    ):
        v = jd_struct.get(k)
        if v:
            parts.append(f"{k}: {v}")
    skills = jd_struct.get("skills_required", []) or []
    if skills:
        parts.append("Required skills: " + ", ".join(str(s) for s in skills))
    return "\n".join(parts)[:8000]


# ── DB loading helpers ────────────────────────────────────────────────────
async def _load_session(
    db: AsyncSession,
    user: User,
    id_session: int,
) -> Optional[AnalysisSession]:
    stmt = select(AnalysisSession).where(AnalysisSession.id_session == id_session)
    rec = (await db.execute(stmt)).scalar_one_or_none()
    if rec is None:
        return None
    if rec.user_id != user.id and not getattr(user, "is_superuser", False):
        raise PermissionError("Bạn không có quyền với analysis session này.")
    return rec


async def _load_cv_jd(
    db: AsyncSession,
    user: User,
    cv_id: int,
    jd_id: int,
) -> tuple[str, str]:
    """Load CV and JD text from parser files. Returns (cv_text, jd_text)."""

    cv_rec = (
        await db.execute(select(CVProfile).where(CVProfile.id_cv == cv_id))
    ).scalar_one_or_none()
    jd_rec = (
        await db.execute(select(JobDescription).where(JobDescription.id_jd == jd_id))
    ).scalar_one_or_none()

    if not cv_rec or not jd_rec:
        raise ValueError("Không tìm thấy CV hoặc JD.")
    if cv_rec.user_id != user.id or jd_rec.user_id != user.id:
        if not getattr(user, "is_superuser", False):
            raise PermissionError("CV hoặc JD không thuộc sở hữu của bạn.")

    cv_data = load_parser_result(cv_rec.parser_file_url) if cv_rec.parser_file_url else {}
    jd_data = load_parser_result(jd_rec.parser_file_url) if jd_rec.parser_file_url else {}
    return _extract_text_from_cv(cv_data), _extract_text_from_jd(jd_data)


# ── Main entry point ──────────────────────────────────────────────────────
async def handle_feedback(
    request: FeedbackRequest,
    db: AsyncSession,
    current_user: User,
) -> FeedbackResponse:
    """
    Top-level orchestrator. Returns a ``FeedbackResponse`` describing
    what the agent decided and did.

    Raises
    ------
    PermissionError
        If the user is not the owner of the underlying CV/JD/session.
    ValueError
        If the request is malformed or the records are missing.
    """
    request.validate_targets()

    cv_text = jd_text = ""
    current_scores = request.current_scores or {}
    session_rec: Optional[AnalysisSession] = None

    # ── 1. Load CV/JD text ──────────────────────────────────────────────
    if request.id_session:
        session_rec = await _load_session(db, current_user, request.id_session)
        if session_rec is None:
            raise ValueError("Không tìm thấy analysis session.")
        cv_text = session_rec.cv_raw_text or ""
        jd_text = session_rec.jd_raw_text or ""
        if not cv_text or not jd_text:
            # Fallback: load from parser files
            cv_text, jd_text = await _load_cv_jd(
                db, current_user, session_rec.id_cv, session_rec.id_jd
            )
        if not current_scores:
            current_scores = {
                "overall": float(session_rec.score or 0),
                "experience_score": float(session_rec.experience_score or 0),
                "skills_score": float(session_rec.skills_score or 0),
                "education_score": float(session_rec.education_score or 0),
                "career_objectives_score": float(session_rec.career_objectives_score or 0),
                "company_fit_score": float(session_rec.companyfit_score or 0),
            }
    else:
        cv_text, jd_text = await _load_cv_jd(
            db, current_user, request.cv_id, request.jd_id  # type: ignore[arg-type]
        )

    if not cv_text and not jd_text:
        raise ValueError("Không tìm thấy nội dung CV/JD để phân tích.")

    # ── 2. Ask the agent ────────────────────────────────────────────────
    agent = get_feedback_agent()
    evaluation = await agent.evaluate(
        cv_text=cv_text,
        jd_text=jd_text,
        feedback_text=request.feedback_text,
        current_scores=current_scores or None,
    )

    # ── 3. Apply the learning (MVP: only synonyms) ─────────────────────
    learning_result: Dict[str, Any] = {"synonyms_added": []}
    if evaluation.is_valid_complaint:
        learning_result = agent.apply_learning(evaluation)

    # ── 4. Persist a FeedbackLog row ────────────────────────────────────
    log = FeedbackLog(
        user_id=current_user.id,
        id_session=session_rec.id_session if session_rec else None,
        id_cv=request.cv_id or (session_rec.id_cv if session_rec else None),
        id_jd=request.jd_id or (session_rec.id_jd if session_rec else None),
        cv_text=(cv_text or "")[:8000],
        jd_text=(jd_text or "")[:8000],
        feedback_text=request.feedback_text,
        agent_evaluation=evaluation.model_dump(),
        applied_overrides={
            "synonyms_added": learning_result.get("synonyms_added", []),
        },
        is_valid=evaluation.is_valid_complaint,
        learned_rule=evaluation.learned_rule,
    )
    db.add(log)
    await db.flush()  # populate log.id without committing yet

    # ── 5. Phase 2: apply proposed_overrides ────────────────────────────
    override_result: Dict[str, Any] = {
        "applied": [],
        "errors": [],
    }
    if (
        evaluation.is_valid_complaint
        and evaluation.proposed_overrides
        and session_rec is not None
    ):
        override_result = await _apply_overrides_to_sessions(
            db=db,
            user=current_user,
            session=session_rec,
            overrides=evaluation.proposed_overrides,
            rationale=evaluation.rationale,
        )
        log.applied_overrides = {
            "synonyms_added": learning_result.get("synonyms_added", []),
            "score_overrides": override_result.get("applied", []),
        }

    await db.commit()
    await db.refresh(log)

    return FeedbackResponse(
        success=True,
        is_valid_complaint=evaluation.is_valid_complaint,
        rationale=evaluation.rationale,
        synonyms_added=[
            SynonymAdded(**p) for p in learning_result.get("synonyms_added", [])
        ],
        learned_rule=evaluation.learned_rule,
        proposed_overrides=evaluation.proposed_overrides,
        feedback_log_id=log.id,
    )


# ── Phase 2: apply proposed_overrides ─────────────────────────────────────
async def _apply_overrides_to_sessions(
    db: AsyncSession,
    user: User,
    session: AnalysisSession,
    overrides: Dict[str, float],
    rationale: str,
) -> Dict[str, Any]:
    """
    Re-score the given AnalysisSession with the LLM's proposed
    overrides and persist:

      - one ``ScoreOverride`` row per section
      - updated AnalysisSession numeric fields
      - the new result-analysis JSON file on disk
    """
    result: Dict[str, Any] = {"applied": [], "errors": []}

    try:
        # Lazy import to avoid pulling the heavy scoring engine on every
        # feedback call when overrides are not requested.
        from app.feature.feature_up_cv.scoring.hybrid_scoring import (
            calculate_hybrid_score,
        )
        from app.feature.feature_up_cv.core.file_storage import (
            save_result_analysis,
        )
        from app.feature.feature_up_cv.auth.services.analysis_session_service import (
            AnalysisSessionService,
        )
        from app.feature.feature_up_cv.auth.schemas.analysis_session import (
            AnalysisSessionUpdate,
        )

        # Load parser results for the CV/JD
        cv_data = load_parser_result(_cv_parser_url(db, session.id_cv)) or {}
        jd_data = load_parser_result(_jd_parser_url(db, session.id_jd)) or {}

        # Run hybrid scoring with overrides + learned rules
        learned_knowledge = _fetch_learned_knowledge()
        new_result = calculate_hybrid_score(
            cv_data=cv_data,
            jd_data=jd_data,
            company_data=None,
            score_overrides=overrides,
            learned_knowledge=learned_knowledge,
        )
        detailed = new_result.get("detailed_scores", {}) or {}

        # Build the section -> score map that hybrid_scoring returns
        section_map = {
            "experience_score": detailed.get("experience_score"),
            "skills_score": detailed.get(
                "skills_total_score", detailed.get("skills_score")
            ),
            "education_score": detailed.get("education_score"),
            "career_objectives_score": detailed.get("career_objectives_score"),
            "company_fit_score": detailed.get("company_fit_score"),
        }

        # Record one ScoreOverride per section
        for section, new_value in overrides.items():
            if section not in section_map:
                continue
            original_value = section_map[section]
            try:
                db.add(
                    ScoreOverride(
                        user_id=user.id,
                        id_cv=session.id_cv,
                        id_jd=session.id_jd,
                        id_session=session.id_session,
                        section=section,
                        original_value=original_value,
                        override_value=float(new_value),
                        rationale=rationale,
                        source="agent_auto",
                    )
                )
                result["applied"].append(
                    {
                        "section": section,
                        "original": original_value,
                        "override": new_value,
                    }
                )
            except Exception as e:
                result["errors"].append({"section": section, "error": str(e)})

        # Update the AnalysisSession row with the new numbers
        try:
            new_overall = new_result.get("overall_score", session.score or 0)
            update_data = AnalysisSessionUpdate(
                score=float(new_overall),
                experience_score=section_map["experience_score"],
                skills_score=section_map["skills_score"],
                education_score=section_map["education_score"],
                career_objectives_score=section_map["career_objectives_score"],
                companyfit_score=section_map["company_fit_score"],
            )
            svc = AnalysisSessionService(db)
            await svc.update(id_session=session.id_session, data=update_data)
        except Exception as e:
            result["errors"].append({"update_session": str(e)})

        # Rewrite the result_analysis file with the new numbers
        try:
            result_path = save_result_analysis(
                new_result,
                user_id=user.id,
                id_cv=session.id_cv,
                id_jd=session.id_jd,
                id_ci=session.id_ci,
            )
            session.result_analysis_file_url = str(result_path)
            await db.flush()
        except Exception as e:
            result["errors"].append({"save_file": str(e)})

    except Exception as e:
        result["errors"].append({"global": str(e)})

    return result


def _cv_parser_url(db: AsyncSession, id_cv: int) -> Optional[str]:
    from app.feature.feature_up_cv.auth.models.cv_profile import CVProfile

    rec = db.get(CVProfile, id_cv)
    return rec.parser_file_url if rec else None


def _jd_parser_url(db: AsyncSession, id_jd: int) -> Optional[str]:
    from app.feature.feature_up_cv.auth.models.job_description import JobDescription

    rec = db.get(JobDescription, id_jd)
    return rec.parser_file_url if rec else None


def _fetch_learned_knowledge() -> Dict[str, Any]:
    """Pull the agent's learned rules from FAISS memory."""
    try:
        from app.feature.feature_up_cv.feedback_agent.memory_faiss import (
            get_agent_memory,
        )

        # Phase 4: prefer the structured view so that any
        # ``structured_rule`` payloads (Hướng 3) are still parsed by
        # ``apply_learned_rules``; the rules engine unwraps them.
        knowledge = get_agent_memory().get_learned_knowledge_structured()
    except Exception:
        knowledge = {"rules": []}

    # Phase 7: also include operator-approved pending rules so the
    # rules engine can apply them on the next scoring call.
    try:
        from app.feature.feature_up_cv.feedback_agent.pending_rules import (
            get_pending_rule_store,
        )

        approved = get_pending_rule_store().approved_rules()
        for payload in approved:
            knowledge["rules"].append(
                {
                    "rule": (
                        f"[APPROVED] type={payload.get('rule_type', 'CUSTOM_PROPOSED')}"
                    ),
                    "structured_rule": payload,
                    "context": {"source": "approved_pending_rule"},
                }
            )
    except Exception:
        pass

    return knowledge
