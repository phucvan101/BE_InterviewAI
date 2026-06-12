# -*- coding: utf-8 -*-
"""
Experience Scoring Module (0-50).

Scores work experience based on:
- Work years vs JD requirements
- Project relevance (semantic + tech match)
- Seniority level match
- Domain penalty
- Bonus for having both work experience and projects
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from ._shared import (
    SCORING_CONFIG,
    compute_domain_penalty,
    get_sim_calibration,
    qprefix,
    safe_cap,
    is_overqualified,
    compute_overqualified_penalty,
    analyze_career_change,
    compute_career_change_experience_penalty,
    analyze_experience_quality,
    validate_skills_context,
    CareerChangeAnalysis,
)

logger = logging.getLogger(__name__)

# ── Years Parsing ──────────────────────────────────────────────────────────────────
def parse_duration_string(duration: str) -> float:
    """
    Parse duration string like '3 years', '6 months', '2.5 years', '1-2 years', etc.
    Returns years as float.
    """
    if not duration or not isinstance(duration, str):
        return 0.0

    duration = duration.lower().strip()

    # Match patterns like "3 years", "3.5 years", "3 year"
    match = re.search(r'([\d.]+)\s*(?:-\s*[\d.]+)?\s*years?', duration)
    if match:
        return float(match.group(1))

    # Match patterns like "6 months", "6 month"
    match = re.search(r'(\d+)\s*(?:-\s*\d+)?\s*months?', duration)
    if match:
        return float(match.group(1)) / 12.0

    return 0.0


def infer_years_from_title(title: str) -> float:
    """
    Estimate years of experience from job title.
    This is a fallback when dates are not available.
    """
    if not title or not isinstance(title, str):
        return 0.0

    title_lower = title.lower()

    # Intern/Trainee
    if any(k in title_lower for k in ['intern', 'trainee', 'thuc tap', 'fresher']):
        return 0.5

    # Junior
    if any(k in title_lower for k in ['junior', 'jr.', 'jr ', 'mới', 'entry']):
        return 1.5

    # Mid-level
    if any(k in title_lower for k in ['mid', ' ii', 'trung cap', 'standard']):
        return 3.0

    # Senior
    if any(k in title_lower for k in ['senior', ' iii', 'cao cap', 'chinh thuc']):
        return 5.0

    # Lead/Principal/Manager
    if any(k in title_lower for k in ['lead', 'principal', 'manager', 'director', 'head', 'chief', 'trưởng']):
        return 7.0

    # Engineer/Developer without prefix
    if any(k in title_lower for k in ['engineer', 'developer', 'developer', 'specialist', 'analyst']):
        return 2.5

    return 0.0


def compute_certification_bonus(
    cv_data: dict,
    jd_data: dict,
) -> float:
    """
    Calculate bonus points from relevant certifications.
    Max bonus: 5 points.
    """
    certs = cv_data.get("certifications", [])
    if not certs:
        return 0.0

    jd_struct = jd_data.get("structured", jd_data)
    jd_skills = set()
    for skill in jd_struct.get("skills_required", []):
        if isinstance(skill, str):
            jd_skills.add(skill.lower())
    for skill in jd_struct.get("skills_preferred", []):
        if isinstance(skill, str):
            jd_skills.add(skill.lower())

    if not jd_skills:
        return 0.0

    bonus = 0.0
    matched_certs = 0

    for cert in certs:
        cert_text = str(cert).lower()
        # Check if cert name contains any JD skill
        for jd_skill in jd_skills:
            if jd_skill in cert_text or cert_text in jd_skill:
                bonus += 1.5
                matched_certs += 1
                break

        # Bonus for recognized certifications
        recognized_certs = {
            'aws', 'azure', 'gcp', 'google cloud',
            'cka', 'ckad', 'cks',  # Kubernetes
            'oscp', 'ceh', 'cissp',  # Security
            'pmp', 'scrum master', 'pmi',
            'cfa', 'acca', 'acca',
            'deep learning', 'tensorflow', 'pytorch',  # ML
            'google data analytics', ' tableau',
            'oracle', 'sql', 'mysql',
        }
        cert_lower = cert_text.lower()
        for recognized in recognized_certs:
            if recognized in cert_lower:
                bonus += 0.5
                break

    return min(bonus, 5.0)


def parse_years(start: str, end: str) -> float:
    """Parse total years from start/end date strings."""
    try:
        import datetime
        now_dt = datetime.datetime.now()
        now_year = now_dt.year
        now_month = now_dt.month

        month_map = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }

        def _extract_year_month(val):
            if isinstance(val, (int, float)):
                return int(val), 1
            if isinstance(val, str):
                val = val.strip().lower()
                if val in ("present", "nay", "hien tai", "now", "hiện tại", "đến nay", "hiện nay"):
                    return now_year, now_month

                m = re.search(r"\b(\d{1,2})[/-](\d{4})\b", val)
                if m:
                    month = max(1, min(12, int(m.group(1))))
                    return int(m.group(2)), month

                m = re.search(r"\b(\d{4})[/-](\d{1,2})\b", val)
                if m:
                    month = max(1, min(12, int(m.group(2))))
                    return int(m.group(1)), month

                for name, month in month_map.items():
                    if re.search(rf"\b{name}\b", val):
                        y = re.search(r"\d{4}", val)
                        if y:
                            return int(y.group()), month

                m = re.search(r"\d{4}", val)
                if m:
                    return int(m.group()), 12
            return None

        sy = _extract_year_month(start)
        ey = _extract_year_month(end)
        if sy and ey:
            start_month_index = sy[0] * 12 + sy[1]
            end_month_index = ey[0] * 12 + ey[1]
            return max(0.0, round((end_month_index - start_month_index) / 12.0, 2))
        if sy:
            start_month_index = sy[0] * 12 + sy[1]
            now_month_index = now_year * 12 + now_month
            return max(0.0, round((now_month_index - start_month_index) / 12.0, 2))
        return 0.0
    except Exception:
        return 0.0


# ── Seniority Detection ──────────────────────────────────────────────────────────────────
def _semantic_seniority_detection(
    titles: List[str],
    descriptions: List[str],
    embedder: EmbeddingService,
) -> int:
    """Detect CV seniority level (0-4) using embedding similarity."""
    from ._shared import _seniority_anchors_embs, ensure_anchor_embs
    ensure_anchor_embs(embedder)

    if not titles and not descriptions:
        return 0

    cv_text = " ".join(titles + descriptions)
    if not cv_text.strip():
        return 0

    cv_emb = embedder.encode(qprefix(cv_text, embedder), normalize=True)
    best_level = 0
    best_sim = -1.0
    for level, anchor_emb in _seniority_anchors_embs.items():
        sim = float(np.dot(cv_emb, anchor_emb))
        if sim > best_sim:
            best_sim = sim
            best_level = level
    return best_level


# ── Experience Features Builder ──────────────────────────────────────────────────────────────────
def build_experience_features(
    all_exp_years: float,
    years_req: float,
    skill_overlap: float,
    domain_penalty: float,
    seniority_gap: int,
) -> Dict[str, Any]:
    """Return a feature dict summarizing experience signals."""
    return {
        "years_ratio": round(all_exp_years / max(years_req, 1.0), 4),
        "skill_overlap": round(skill_overlap, 4),
        "domain_penalty": round(domain_penalty, 4),
        "seniority_gap": int(seniority_gap),
    }


# ── Main Experience Scoring ──────────────────────────────────────────────────────────────────
def score_experience(
    cv_data: dict,
    jd_data: dict,
    cv_domain: str,
    jd_domain: str,
    skill_overlap: float,
    embedder: EmbeddingService,
) -> Tuple[
    float,          # score
    str,            # rationale
    dict,           # features (for ML/debugging)
    int,            # cv_level
    int,            # req_level
    int,            # seniority_gap
    bool,           # is_entry_level
    float,          # all_exp_years
    float,          # years_req
    int,            # cert_count
    float,          # total_work_years
    float,          # project_years
]:
    """
    Score work experience (0-50).

    Returns: (score, rationale, features_dict)

    Algorithm:
    1. Parse JD seniority requirements
    2. Calculate total work years + project years
    3. Compute years_score (0-40) with domain/overqualification penalties
    4. Compute seniority_score (0-10)
    5. Apply bonus for having both work exp and projects
    6. Apply caps for underqualification/severe gaps
    7. Apply domain penalty
    """
    jd_struct = jd_data.get("structured", jd_data)

    # ── 1. JD seniority requirements ────────────────────────────────
    seniority_req = (jd_struct.get("seniority") or "").lower()
    seniority_parts = [p.strip().lower() for p in seniority_req.split("/")]
    seniority_level_map = {
        "intern": 0, "fresher": 0, "junior": 1,
        "mid": 2, "mid-level": 2, "senior": 3,
        "lead": 4, "principal": 4, "expert": 4, "manager": 4,
    }
    req_level = min(
        (seniority_level_map.get(p, 2) for p in seniority_parts),
        default=2,
    )

    years_req_map = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    years_req_raw = jd_struct.get("years_of_experience", "")
    if years_req_raw:
        numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(years_req_raw))]
        years_req = min(numbers) if numbers else years_req_map.get(req_level, 2.0)
    else:
        years_req = years_req_map.get(req_level, 2.0)

    # ── 2. Work years ──────────────────────────────────────────────
    total_work_years = 0.0
    exp_titles: List[str] = []
    for exp in cv_data.get("work_experience", []):
        start = exp.get("start") or exp.get("start_date") or ""
        end = exp.get("end") or exp.get("end_date") or ""
        duration_str = exp.get("duration") or ""

        # Try standard date parsing first
        parsed_years = parse_years(start, end)

        # If dates didn't work, try duration string
        if parsed_years == 0.0 and duration_str:
            parsed_years = parse_duration_string(duration_str)

        # If still 0, try to infer from job title
        if parsed_years == 0.0 and exp.get("title"):
            parsed_years = infer_years_from_title(exp.get("title", ""))

        total_work_years += parsed_years
        if t := exp.get("title"):
            exp_titles.append(t.lower())

    # ── 3. Project years ───────────────────────────────────────────
    is_entry_level = req_level <= 1
    default_proj_dur = 0.5 if is_entry_level else 0.25

    from .._semantic.project_relevance import compute_project_relevance
    project_years, project_relevance_scores, project_descriptions = \
        compute_project_relevance(
            cv_data.get("projects", []),
            jd_data,
            embedder,
            default_proj_dur,
        )

    all_exp_years = total_work_years + project_years

    # ── 4. Years score (0-45) ────────────────────────────────────
    if is_entry_level and years_req == 0:
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        has_any_project = len(cv_data.get("projects", [])) > 0

        if total_work_years > 0:
            if skill_overlap < 0.1:
                years_score = 10.0
            else:
                years_score = 42.0
        elif avg_rel >= 0.55:
            years_score = 45.0
        elif avg_rel >= 0.20:
            years_score = 20.0 + (avg_rel - 0.20) / 0.35 * 25.0
        elif has_any_project and avg_rel > 0:
            years_score = 15.0 + avg_rel / 0.25 * 5.0
        elif has_any_project:
            years_score = 12.0
        else:
            years_score = 8.0

    elif years_req > 0:
        ratio = min(all_exp_years / years_req, 2.5)
        if all_exp_years < years_req:
            gap_ratio = all_exp_years / years_req
            raw_years_score = min(45.0 * gap_ratio * gap_ratio, 45.0)
        else:
            raw_years_score = min(45.0 * ratio * 0.8, 45.0)

        # Overqualified penalty for entry-level JD
        if is_entry_level and all_exp_years > 0 and years_req >= 0:
            years_req_max_raw = jd_struct.get("years_of_experience", "")
            max_numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(years_req_max_raw))]
            years_req_upper = max(max_numbers) if max_numbers else (years_req + 1.0)
            if all_exp_years > years_req_upper * 2.0:
                overqualified_penalty = min(8.0, (all_exp_years - years_req_upper * 2.0) * 2.0)
                raw_years_score = max(raw_years_score - overqualified_penalty, 20.0)
        years_score = raw_years_score
    else:
        years_score = min(all_exp_years * 20.0, 40.0)

    # ── 5. Experience Quality Multiplier ──────────────────────────
    exp_context = jd_struct.get("experience_context", "").strip()
    if exp_context and total_work_years > 0:
        cv_work_text = " ".join([
            f"{e.get('title', '')} {e.get('company', '')} {' '.join(e.get('highlights', []))}"
            for e in cv_data.get("work_experience", [])
        ]).strip()
        if cv_work_text:
            try:
                cv_emb = embedder.encode(cv_work_text[:1000], normalize=True)
                jd_emb = embedder.encode(exp_context[:500], normalize=True)
                sim = float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0))

                SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
                span = max(SIM_MAX - SIM_MIN, 0.1)
                scaled_sim = np.clip((sim - SIM_MIN) / span, 0.0, 1.0)

                quality_multiplier = 0.6 + (0.4 * scaled_sim)
                years_score = years_score * quality_multiplier
            except Exception as e:
                logger.debug(f"Exp context embedding failed: {e}")

    # ── 6. Domain penalty ──────────────────────────────────────────
    domain_penalty, penalty_reason = compute_domain_penalty(
        cv_domain, jd_domain, skill_overlap
    )

    # ── 7. Seniority score (0-10) ─────────────────────────────────
    cv_level = _semantic_seniority_detection(exp_titles, project_descriptions, embedder)

    seniority_base = 0.0
    if domain_penalty >= 0.7:
        seniority_base = 0.0
    elif is_entry_level:
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        if total_work_years > 0:
            if years_req > 0:
                years_ratio = min(total_work_years / years_req, 1.5)
                seniority_base = round(min(years_ratio * 10.0, 10.0), 1)
            else:
                seniority_base = 10.0
        elif avg_rel >= 0.70:
            seniority_base = 7.0
        elif avg_rel >= 0.45:
            seniority_base = 5.0
        elif avg_rel >= 0.25:
            seniority_base = 3.0
        else:
            seniority_base = 1.0
    elif cv_level >= req_level:
        seniority_base = 10.0
    elif cv_level == req_level - 1:
        seniority_base = 5.0
    elif cv_level > 0:
        seniority_base = 2.0
    else:
        seniority_base = 0.0

    # Apply level-ratio scaling when CV is below required level
    if domain_penalty < 0.7 and req_level > 0 and cv_level < req_level and cv_level > 0:
        level_ratio = cv_level / req_level
        seniority_score = round(min(seniority_base * level_ratio, 10.0), 1)
    else:
        seniority_score = seniority_base

    # Severe seniority gap — hard cap
    if domain_penalty < 0.7 and req_level > 0 and cv_level < req_level:
        level_gap = req_level - cv_level
        if level_gap >= 3:
            seniority_score = 0.0
        elif level_gap >= 2:
            seniority_score = min(seniority_score, 2.0)

    # ── 8. Bonus ──────────────────────────────────────────────────
    bonus = 0.0

    # Certification bonus
    cert_bonus = compute_certification_bonus(cv_data, jd_data)
    bonus += cert_bonus

    if domain_penalty < 0.4:
        if total_work_years > 0 and project_years > 0:
            bonus += 8.0
        elif project_years > 0:
            avg_rel = (
                sum(project_relevance_scores) / len(project_relevance_scores)
                if project_relevance_scores else 0.0
            )
            rel_threshold_high = 0.55 if is_entry_level else 0.65
            rel_threshold_mid = 0.35 if is_entry_level else 0.50
            if avg_rel >= rel_threshold_high:
                bonus += 5.0
            elif avg_rel >= rel_threshold_mid:
                bonus += 3.0

    if is_entry_level and years_req <= 1.0:
        bonus = min(bonus, 3.0)

    raw_total = years_score + seniority_score + bonus

    # ── 9. Domain-mismatch experience penalty ─────────────────────
    if domain_penalty >= 0.5 and total_work_years > 0 and skill_overlap < 0.10:
        years_score = years_score * 0.65

    # ── 10. Severe underqualification cap ─────────────────────────
    if (not is_entry_level and years_req > 0 and all_exp_years > 0
            and all_exp_years <= years_req * 0.5):
        years_gap_ratio = all_exp_years / years_req
        seniority_score = round(min(seniority_score * years_gap_ratio, 10.0), 1)

    if (not is_entry_level and years_req > 0 and all_exp_years > 0
            and all_exp_years <= years_req * 0.86 and domain_penalty < 0.7):
        raw_total = safe_cap(raw_total, SCORING_CONFIG.UNDERQUALIFIED_CAP)

    if (not is_entry_level and years_req > 0 and all_exp_years > 0
            and years_req - all_exp_years >= 2.0):
        raw_total = safe_cap(raw_total, SCORING_CONFIG.SEVERE_GAP_CAP)

    if (domain_penalty < 0.4 and skill_overlap < 0.40 and not is_entry_level
            and years_req > 0 and all_exp_years > 0):
        raw_total = safe_cap(raw_total, SCORING_CONFIG.SPECIALIZATION_MISMATCH_CAP)

    # ── 11. Final score with domain penalty ───────────────────────
    # Apply domain penalty more leniently for good candidates
    penalty_factor = 1.0 - (domain_penalty * 0.6)  # Less aggressive penalty
    total_exp = round(min(raw_total * penalty_factor, 50.0), 2)

    # ── v2: APPLY OVERQUALIFIED DETECTION ────────────────────────────────────────
    # Fix for 90% cases where overqualified candidates get inflated scores
    is_ovq, ovq_severity, ovq_reason = is_overqualified(
        cv_data, jd_data, total_work_years, years_req
    )
    if is_ovq:
        total_exp, ovq_penalty_reason = compute_overqualified_penalty(
            is_ovq, ovq_severity, total_exp
        )
        logger.info(f"[OVERQUALIFIED] {ovq_reason} -> {ovq_penalty_reason}")

    # ── v2: APPLY CAREER CHANGE DETECTION ────────────────────────────────────────
    # Fix for 20% cases where career changers don't get proper penalty
    career_change = analyze_career_change(cv_data, jd_data, skill_overlap)
    if career_change.is_career_change:
        exp_before_cc = total_exp
        total_exp, cc_penalty_reason = compute_career_change_experience_penalty(
            career_change, total_exp, skill_overlap
        )
        logger.info(f"[CAREER_CHANGE] {career_change.reason} -> {cc_penalty_reason}")
        total_exp = max(0, min(total_exp, 50.0))

    # ── v2: APPLY EXPERIENCE QUALITY ANALYSIS ────────────────────────────────────
    # Quality over Quantity - don't just count years
    quality_mult, quality_indicators, quality_concerns = analyze_experience_quality(
        cv_data, jd_data, cv_domain, jd_domain
    )
    if quality_mult < 1.0:
        # Apply quality adjustment
        quality_adjusted = total_exp * (0.5 + 0.5 * quality_mult)
        # Don't reduce too much, but signal the concern
        if quality_concerns and total_exp > 30:
            logger.info(f"[EXP_QUALITY] Concerns: {quality_concerns}")

    # ── 12. Features ───────────────────────────────────────────────
    try:
        features = build_experience_features(
            all_exp_years, years_req, skill_overlap, domain_penalty, int(req_level - cv_level)
        )
        features["project_relevance_scores"] = project_relevance_scores
        features["project_descriptions"] = project_descriptions
        features["project_years"] = project_years
        features["total_work_years"] = total_work_years
        features["cert_count"] = len(cv_data.get("certifications", []))
        features["cert_bonus"] = cert_bonus
        features["cv_level"] = cv_level
        features["req_level"] = req_level
        features["is_entry_level"] = is_entry_level
    except Exception:
        features = {}

    # ── 13. Rationale ──────────────────────────────────────────────
    cert_info = f" (chứng chỉ liên quan: +{cert_bonus:.1f}đ)" if cert_bonus > 0 else ""

    # Build rationale with v2 enhancements
    rationale_parts = []

    # Add overqualified info
    if is_ovq:
        rationale_parts.append(f"⚠️ {ovq_reason}")

    # Add career change info
    if career_change.is_career_change:
        rationale_parts.append(f"⚠️ {career_change.reason}")

    # Original domain/rationale logic
    if domain_penalty >= 0.7:
        rationale_parts.append(
            f"Domain không phù hợp ({cv_domain} vs {jd_domain}). "
            f"Kinh nghiệm bị giảm mạnh ({int(domain_penalty*100)}% penalty). "
            f"{penalty_reason}{cert_info}"
        )
    elif domain_penalty >= 0.4:
        rationale_parts.append(
            f"Domain lệch một phần ({cv_domain} vs {jd_domain}). "
            f"Kinh nghiệm bị giảm {int(domain_penalty*100)}%. "
            f"{penalty_reason}{cert_info}"
        )
    elif domain_penalty > 0:
        rationale_parts.append(f"Domain gần nhau, penalty nhẹ {int(domain_penalty*100)}%. {penalty_reason}{cert_info}")
    elif is_entry_level and project_years > 0:
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        rationale_parts.append(
            f"JD Intern/Fresher — dự án cá nhân là bằng chứng chính "
            f"(relevance trung bình: {avg_rel:.0%}).{cert_info}"
        )
    elif seniority_score >= 10:
        rationale_parts.append(f"Kinh nghiệm và cấp độ đạt yêu cầu.{cert_info}")
    elif seniority_score >= 5:
        rationale_parts.append(f"Kinh nghiệm gần đạt yêu cầu.{cert_info}")
    elif total_work_years > 0 or project_years > 0:
        rationale_parts.append(f"Kinh nghiệm thấp hơn yêu cầu (fresh grad / dự án cá nhân).{cert_info}")
    else:
        rationale_parts.append(f"Chưa có kinh nghiệm làm việc hoặc dự án liên quan.{cert_info}")

    rationale = " | ".join(rationale_parts)

    return (
        total_exp,
        rationale,
        features,
        cv_level,
        req_level,
        int(req_level - cv_level),
        is_entry_level,
        all_exp_years,
        years_req,
        len(cv_data.get("certifications", [])),
        total_work_years,
        project_years,
    )


def build_experience_detail(cv_data: dict) -> str:
    """Build a human-readable summary of CV experience."""
    work = cv_data.get("work_experience", [])
    projects = cv_data.get("projects", [])
    parts = []
    if work:
        work_parts = []
        for e in work:
            if e.get("title"):
                period = e.get("years") or (e.get("start", "") + "-" + e.get("end", ""))
                work_parts.append(f"{e['title']} ({period})")
        if work_parts:
            parts.append("Work: [" + ", ".join(work_parts) + "]")
    if projects:
        proj_parts = [p.get("name", "N/A") for p in projects if p.get("name")]
        if proj_parts:
            parts.append("Projects: [" + ", ".join(proj_parts) + "]")
    return ". ".join(parts) + "." if parts else "Chưa có kinh nghiệm làm việc hoặc dự án cá nhân."
