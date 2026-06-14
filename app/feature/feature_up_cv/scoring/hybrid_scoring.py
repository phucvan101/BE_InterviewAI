# -*- coding: utf-8 -*-
"""
Hybrid CV-JD Scoring Engine — v6 (enhanced response).

Orchestrator that coordinates individual scoring modules and builds
a rich, structured response for FE display.

Changes from v5:
- Added response_builder.py for rich, structured output
- Strengths, areas, recommendation are now detailed objects
- Each scoring section has its own detail block
"""


import logging
from datetime import datetime
from typing import Any, Dict, List

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import (
    get_embedding_service,
)

logger = logging.getLogger(__name__)

# ── Import scoring modules ─────────────────────────────────────────────────────────
from ._scores._shared import (
    _SOFT_SKILL_KEYS,
    build_cv_text,
    compute_domain_penalty,
    build_skill_groups,
    qprefix,
    pprefix,
    normalize_skill_key,
)

from ._scores.experience_score import score_experience, build_experience_detail as _build_exp_detail
from ._scores.skills_score import (
    score_skills,
    compute_skill_overlap_ratio,
    collect_cv_evidence,
)
from ._scores.education_score import score_education
from ._scores.career_score import score_career_objectives
from ._scores.company_fit_score import score_company_fit

from ._semantic.domain import detect_cv_domain, detect_jd_domain
from .response_builder import (
    build_main_strengths,
    build_areas_for_improvement,
    build_recommendation,
    build_experience_detail,
    build_education_detail,
    build_career_detail,
    build_company_fit_detail,
    build_summary_text,
    get_score_badge,
    StrengthItem,
    AreaItem,
    RecommendationItem,
)
from ._rules_engine import apply_learned_rules


# ── Main Entry Point ──────────────────────────────────────────────────────────────────
def calculate_hybrid_score(
    cv_data: dict,
    jd_data: dict,
    company_data: dict = None,
    cv_embedding: np.ndarray = None,
    jd_embedding: np.ndarray = None,
    score_overrides: dict = None, # [AGENT OVERRIDE] Thêm tham số nhận điểm ghi đè từ DB
    learned_knowledge: dict = None, # [AGENT KNOWLEDGE] Thêm tham số nhận bài học từ RAG
) -> dict:
    """
    Hybrid CV-JD scoring v6 — rich structured response.

    Scoring formula (max = 100):
        experience_score        : 0-50
        skills_score           : 0-30
        education_score        : 0-10
        career_objectives_score: 0-10

    company_fit_score (0-10) is returned separately.

    Response structure (rich for FE):
        - summary: overview text
        - detailed_scores: numeric breakdown
        - score_badges: visual labels per section
        - experience_detail: rich experience analysis
        - skills_detail: rich skills analysis
        - education_detail: rich education analysis
        - career_detail: rich career objectives analysis
        - company_fit_detail: rich company fit analysis
        - domain_analysis: domain match analysis
        - main_strengths: list of StrengthItem
        - areas_for_improvement: list of AreaItem
        - recommendation: RecommendationItem
        - matched_skills / related_skills / missing_skills: structured lists
        - criteria_match_results: full criteria detail
    """
    try:
        embedder = get_embedding_service()

        # ── 1. Domain Detection ──────────────────────────────────────────
        cv_domain = detect_cv_domain(cv_data, embedder, threshold=0.40)
        jd_domain = detect_jd_domain(jd_data, embedder, threshold=0.40)

        jd_struct = jd_data.get("structured", jd_data)

        # ── 2. Skill Overlap for Domain Penalty ──────────────────────────
        jd_skills_for_overlap = [
            s for s in jd_struct.get("skills_required", [])
            if isinstance(s, str) and s.strip()
            and normalize_skill_key(s) not in _SOFT_SKILL_KEYS
        ]
        if not jd_skills_for_overlap:
            jd_skills_for_overlap = [
                s for s in jd_struct.get("skills_preferred", [])
                if isinstance(s, str) and s.strip()
                and normalize_skill_key(s) not in _SOFT_SKILL_KEYS
            ]

        cv_skills_flat, _ = collect_cv_evidence(cv_data)
        skill_overlap = compute_skill_overlap_ratio(
            cv_skills_flat, jd_skills_for_overlap, embedder, threshold=0.72
        )

        domain_penalty, domain_penalty_reason = compute_domain_penalty(
            cv_domain, jd_domain, skill_overlap
        )

        # ── 3. Individual Score Components ──────────────────────────────
        (
            exp_score, exp_rationale, exp_features,
            cv_level, req_level, seniority_gap,
            is_entry_level, all_exp_years, years_req,
            cert_count, total_work_years, project_years,
        ) = score_experience(
            cv_data, jd_data, cv_domain, jd_domain, skill_overlap, embedder
        )

        (
            skills_score,
            perfect_requirements,
            missing_requirements,
            sim,
            relevant_requirements,
            skills_breakdown,
            criteria_match_results,
        ) = score_skills(
            cv_data, jd_data, embedder, domain_penalty,
            cv_embedding=cv_embedding, jd_embedding=jd_embedding
        )

        edu_score, edu_rationale = score_education(
            cv_data, jd_data, embedder, domain_penalty
        )

        career_obj_score, career_obj_rationale, career_details = score_career_objectives(
            cv_data, jd_data, embedder, domain_penalty
        )

        try:
            company_score, company_rationale = score_company_fit(
                cv_data, company_data, jd_data, embedder
            )
        except Exception as _ce:
            import logging as _lg
            _lg.getLogger(__name__).error(
                f"[COMPANY_FIT] Isolated exception: {_ce}", exc_info=True
            )
            company_score, company_rationale = 0.0, f"Loi tinh company fit: {_ce}"

        # ── [AGENT INJECTION] Áp dụng bài học (Learned Rules từ FAISS) ──
        if learned_knowledge and "rules" in learned_knowledge and learned_knowledge["rules"]:
            # Áp dụng learned rules để điều chỉnh scores
            (
                exp_score,
                skills_score,
                domain_penalty,
                domain_penalty_reason,
                rules_applied,
            ) = apply_learned_rules(
                cv_data=cv_data,
                jd_data=jd_data,
                learned_knowledge=learned_knowledge,
                exp_score=exp_score,
                skills_score=skills_score,
                domain_penalty=domain_penalty,
                domain_penalty_reason=domain_penalty_reason,
                total_work_years=total_work_years,
                project_years=project_years,
            )
            if rules_applied:
                exp_rationale += f"\n[Hệ thống AI đã tự động điều chỉnh theo bài học: {rules_applied}]"

        # ── [AGENT INJECTION] Áp dụng điểm ghi đè (Score Override) ──
        if score_overrides:
            override_limits = {
                "experience_score": 50.0,
                "skills_score": 30.0,
                "education_score": 10.0,
                "career_objectives_score": 10.0,
                "company_fit_score": 10.0,
            }

            def _safe_override(key: str, current_score: float) -> float:
                if key not in score_overrides:
                    return current_score
                try:
                    value = float(score_overrides[key])
                except (TypeError, ValueError):
                    logger.warning("Ignoring invalid score override %s=%r", key, score_overrides[key])
                    return current_score
                return min(max(value, 0.0), override_limits[key])

            if "experience_score" in score_overrides:
                exp_score = _safe_override("experience_score", exp_score)
                exp_rationale = score_overrides.get("rationale", exp_rationale + " (Đã được cập nhật bởi Agent)")
            if "skills_score" in score_overrides:
                skills_score = _safe_override("skills_score", skills_score)
            if "education_score" in score_overrides:
                edu_score = _safe_override("education_score", edu_score)
            if "career_objectives_score" in score_overrides:
                career_obj_score = _safe_override("career_objectives_score", career_obj_score)
            if "company_fit_score" in score_overrides:
                company_score = _safe_override("company_fit_score", company_score)

        overall = round(
            min(exp_score + skills_score + edu_score + career_obj_score, 100.0)
        )

    except Exception as e:
        logger.error(f"Scoring failed, using fallback: {e}")
        embedder = get_embedding_service()
        sim = 0.0
        try:
            cv_emb = embedder.encode(qprefix(embedder.encode_structured_cv(cv_data), embedder))
            jd_emb = embedder.encode(pprefix(embedder.encode_structured_jd(jd_data), embedder))
            sim = round(float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0)), 4)
        except Exception as inner_e:
            logger.error(f"Fallback embedding also failed: {inner_e}")
            sim = 0.0

        exp_score = skills_score = edu_score = career_obj_score = company_score = overall = 0
        exp_rationale = "Không thể tính điểm kinh nghiệm."
        exp_features = {}
        cv_level = req_level = seniority_gap = 0
        is_entry_level = False
        all_exp_years = years_req = cert_count = total_work_years = project_years = 0.0
        perfect_requirements = []
        relevant_requirements = []
        missing_requirements = []
        skills_breakdown = {
            "raw_score": 0.0, "coverage_ratio": 0.0,
            "perfect_score": 0.0, "relevant_score": 0.0,
            "criteria_count": 0, "domain_cap_applied": False,
        }
        criteria_match_results = []
        edu_rationale = "Không thể tính điểm học vấn."
        career_obj_rationale = "Không thể tính điểm mục tiêu nghề nghiệp."
        career_details = {}
        company_rationale = "Không có dữ liệu công ty."
        cv_domain = jd_domain = "unknown"
        domain_penalty = 0.0
        domain_penalty_reason = ""

    # ── 4. Build Rich Response ─────────────────────────────────────────
    cv_is_student = cv_data.get("is_student", False)

    # Experience detail
    exp_detail = build_experience_detail(
        exp_score, exp_rationale, exp_features,
        cv_level, req_level, seniority_gap, is_entry_level, cv_data,
    )

    # Education detail
    edu_detail = build_education_detail(edu_score, edu_rationale, cv_data)

    # Career detail
    career_detail = build_career_detail(career_obj_score, career_obj_rationale)

    # Company fit detail
    company_detail = build_company_fit_detail(company_score, company_rationale)

    # Strengths
    strengths: List[Dict[str, Any]] = build_main_strengths(
        exp_score, skills_score, edu_score, career_obj_score, company_score,
        exp_features, skills_breakdown, criteria_match_results,
        cv_domain, jd_domain,
    )

    # Areas for improvement
    areas_raw: List[AreaItem] = build_areas_for_improvement(
        exp_score, skills_score, edu_score, career_obj_score,
        exp_features, skills_breakdown,
        missing_requirements, criteria_match_results,
        cv_domain, jd_domain, domain_penalty,
        seniority_gap, years_req, all_exp_years, is_entry_level, cv_is_student,
    )
    areas_for_improvement: List[Dict[str, Any]] = [
        {
            "type": a.type,
            "title": a.title,
            "description": a.description,
            "priority": a.priority,
            "suggestions": a.suggestions,
        }
        for a in areas_raw
    ]

    # Recommendation
    critical_missing = [
        r for r in missing_requirements if r.get("importance") == "CRITICAL"
    ]
    rec_raw: RecommendationItem = build_recommendation(
        overall, exp_score, skills_score, edu_score, career_obj_score,
        company_score, domain_penalty, critical_missing, areas_raw,
    )
    recommendation: Dict[str, Any] = {
        "level": rec_raw.level,
        "summary": rec_raw.summary,
        "summary_detail": rec_raw.summary_detail,
        "action_items": rec_raw.action_items,
        "interview_tips": rec_raw.interview_tips,
        "score_range": rec_raw.score_range,
    }

    # Summary text
    summary_text = build_summary_text(
        overall, exp_score, skills_score, edu_score,
        career_obj_score, company_score, domain_penalty,
    )

    # Score badges
    score_badges = {
        "overall": get_score_badge(overall, 100.0),
        "experience": get_score_badge(exp_score, 50.0),
        "skills": get_score_badge(skills_score, 30.0),
        "education": get_score_badge(edu_score, 10.0),
        "career_objectives": get_score_badge(career_obj_score, 10.0),
        "company_fit": get_score_badge(company_score, 10.0),
    }

    # Domain labels
    domain_label_map = {
        "tech_ai": "AI/Machine Learning",
        "tech_software": "Software Engineering",
        "tech_data": "Data Engineering",
        "tech_devops": "DevOps",
        "tech_security": "Security",
        "sales": "Sales",
        "marketing": "Marketing",
        "finance": "Finance",
        "hr": "Human Resources",
        "operations": "Operations",
        "healthcare": "Healthcare",
        "education": "Education",
        "design": "Design",
        "unknown": "Không xác định",
    }

    # Skills detail
    skills_detail = {
        "score": round(skills_score, 1),
        "perfect_score": round(skills_breakdown.get("perfect_score", 0.0), 1),
        "relevant_score": round(skills_breakdown.get("relevant_score", 0.0), 1),
        "coverage_ratio": round(skills_breakdown.get("coverage_ratio", 0.0), 3),
        "criteria_count": skills_breakdown.get("criteria_count", 0),
        "critical_matched": skills_breakdown.get("critical_matched", 0),
        "critical_total": skills_breakdown.get("critical_total", 0),
        "important_matched": skills_breakdown.get("important_matched", 0),
        "important_total": skills_breakdown.get("important_total", 0),
        "domain_cap_applied": skills_breakdown.get("domain_cap_applied", False),
        "perfect_count": len(perfect_requirements),
        "relevant_count": len(relevant_requirements),
        "missing_count": len(missing_requirements),
        # v2: Skills context validation info
        "context_validation": skills_breakdown.get("context_validation", {}),
    }

    # ── 5. Build Final Response ──────────────────────────────────────────
    cv_name = cv_data.get("personal_info", {}).get("name", "Unknown")
    job_title = (
        jd_data.get("job_title")
        or (jd_data.get("structured", {}) or {}).get("job_title")
        or "Unknown"
    )

    return {
        # ── Top-level overview ──────────────────────────────
        "summary": summary_text,
        "overall_score": overall,
        "score_badges": score_badges,

        # ── Detailed scores ───────────────────────────────
        "detailed_scores": {
            "experience_score": round(exp_score),
            "skills_total_score": round(skills_score),
            "skills_perfect_score": round(skills_breakdown.get("perfect_score", 0.0)),
            "skills_relevant_score": round(skills_breakdown.get("relevant_score", 0.0)),
            "education_score": round(edu_score),
            "career_objectives_score": round(career_obj_score),
            "company_fit_score": round(company_score),
            # Legacy compat
            "skills_keyword_score": round(skills_breakdown.get("rule_score", 0.0)),
            "skills_embedding_score": round(skills_breakdown.get("semantic_score", 0.0)),
        },

        # ── Score breakdowns per section ─────────────────
        "experience_detail": exp_detail,
        "skills_detail": skills_detail,
        "education_detail": edu_detail,
        "career_detail": career_detail,
        "company_fit_detail": company_detail,

        # ── Domain analysis ────────────────────────────────
        "domain_analysis": {
            "cv_domain": cv_domain,
            "cv_domain_label": domain_label_map.get(cv_domain, cv_domain),
            "jd_domain": jd_domain,
            "jd_domain_label": domain_label_map.get(jd_domain, jd_domain),
            "domain_penalty": round(domain_penalty, 2),
            "domain_penalty_reason": domain_penalty_reason,
            "skill_overlap": round(skill_overlap, 3),
            "domain_match": cv_domain == jd_domain or domain_penalty < 0.3,
        },

        # ── Skills detailed ──────────────────────────────
        "matched_skills": [
            {
                "skill": r.get("requirement", ""),
                "reason": r.get("reason", ""),
                "importance": r.get("importance", ""),
                "confidence": r.get("confidence", 1.0),
            }
            for r in perfect_requirements
        ] if perfect_requirements else [],

        "related_skills": [
            {
                "skill": r.get("requirement", ""),
                "reason": r.get("reason", ""),
                "importance": r.get("importance", ""),
                "confidence": r.get("confidence", 0.0),
            }
            for r in relevant_requirements
        ] if relevant_requirements else [],

        "missing_skills": [
            {
                "skill": r.get("requirement", ""),
                "reason": r.get("reason", ""),
                "importance": r.get("importance", ""),
            }
            for r in missing_requirements
        ][:15] if missing_requirements else [],

        "criteria_match_results": criteria_match_results,
        "skills_criteria_breakdown": skills_breakdown,

        # ── Main strengths ────────────────────────────────
        "main_strengths": [
            {
                "type": s.type,
                "title": s.title,
                "description": s.description,
                "score_impact": s.score_impact,
                "icon": s.icon,
            }
            for s in strengths
        ] if strengths else [],

        # ── Areas for improvement ─────────────────────────
        "areas_for_improvement": areas_for_improvement,

        # ── Recommendation ───────────────────────────────
        "recommendation": recommendation,

        # ── Legacy fields (backward compat) ──────────────
        "score_rationale": (
            f"Kinh nghiệm: {exp_score}/50, Kỹ năng: {skills_score}/30, "
            f"Học vấn: {edu_score}/10, Mục tiêu nghề nghiệp: {career_obj_score}/10. "
            f"Tổng: {overall}/100. "
            f"Độ phù hợp công ty: {company_score}/10 (đánh giá riêng)."
        ),
        "experience_assessment": exp_rationale,
        "experience_detail_legacy": _build_exp_detail(cv_data),
        "education_rationale": edu_rationale,
        "career_objectives_rationale": career_obj_rationale,
        "company_fit_rationale": company_rationale,

        # ── Metadata ──────────────────────────────────────
        "cv_candidate": cv_name,
        "job_position": job_title,
        "matched_at": datetime.now().isoformat(),
        "features": {
            "experience": exp_features,
        },
        "evidence": {
            "cv_skills": list(build_skill_groups(cv_data.get("skills", []))),
            "jd_skills_required": list(build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_required", [])
            )),
            "jd_skills_preferred": list(build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_preferred", [])
            )),
        },
        "embedding_similarity": round(sim, 4) if sim else 0.0,
        "embedding_status": "ok" if sim > 0 else "failed_or_zero",
    }


# ── Backward-compat wrapper ─────────────────────────────────────────────────────────
def _normalize_skill_key(skill: str) -> str:
    """Backward-compat alias."""
    from ._scores._shared import normalize_skill_key as _nsk
    return _nsk(skill)
