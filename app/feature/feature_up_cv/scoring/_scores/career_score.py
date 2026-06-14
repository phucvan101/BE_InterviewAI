# -*- coding: utf-8 -*-
"""
Career Objectives Scoring Module (0-10).

Scores career objectives alignment based on:
- Semantic similarity between CV objectives and JD goals
- Keyword boost when CV objective contains JD job title keywords
- Overqualified penalty when objective targets higher position
- Domain penalty
- Proxy fallback when CV has no stated objectives
"""


import logging
import re
from typing import Tuple

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from ._shared import (
    get_sim_calibration,
    qprefix,
    pprefix,
)

logger = logging.getLogger(__name__)


def score_career_objectives(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float = 0.0,
) -> Tuple[float, str, dict]:
    """
    Score career objectives alignment (0-10).

    Returns: (score, rationale, details)

    Algorithm:
    1. Build CV objective and JD goal text
    2. Compute semantic similarity (with calibration)
    3. Apply keyword boost if CV contains JD title keywords
    4. Penalize overqualified objectives (targeting higher position)
    5. Apply domain penalty for severe mismatches
    6. Fallback to proxy text when CV has no stated objectives
    """
    cv_objective = (cv_data.get("career_objectives") or cv_data.get("objective") or "").strip()
    jd_struct = jd_data.get("structured", jd_data)

    jd_goal_text = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
        jd_struct.get("industry", ""),
        jd_struct.get("career_expectations", ""),
    ]))

    # Fallback when CV has no career objective
    if not cv_objective:
        return _score_proxy_fallback(cv_data, jd_data, embedder, domain_penalty, jd_goal_text)

    if not jd_goal_text:
        return 5.0, "Không có thông tin JD để so sánh mục tiêu.", {}

    return _score_with_objective(
        cv_objective, cv_data, jd_data, jd_struct, embedder, domain_penalty, jd_goal_text
    )


def _score_proxy_fallback(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float,
    jd_goal_text: str,
) -> Tuple[float, str, dict]:
    """Score CV when career objective is missing — use skills + experience as proxy."""
    cv_skills_list = (
        cv_data.get("skills", [])
        + cv_data.get("technical_skills", [])
        + cv_data.get("domain_skills", [])
    )
    cv_exp_titles = [
        exp.get("title", "")
        for exp in cv_data.get("work_experience", [])
        if exp.get("title")
    ]
    cv_proxy_text = " ".join(filter(None, cv_skills_list + cv_exp_titles)).strip()
    cv_objective = (cv_data.get("career_objectives") or cv_data.get("objective") or "").strip()

    if not cv_proxy_text:
        default = 1.0 if domain_penalty >= 0.7 else 3.0
        note = "Domain hoan toan khong lien quan." if domain_penalty >= 0.7 else "Khong du thong tin de danh gia."
        return default, f"CV khong co muc tieu nghe nghiep. {note} (diem mac dinh {default}/10).", {}

    try:
        proxy_emb = embedder.encode(cv_proxy_text, normalize=True)
        jd_emb_fb = embedder.encode(jd_goal_text, normalize=True)
        sim_fb = float(np.clip(np.dot(proxy_emb, jd_emb_fb), 0.0, 1.0))
        SIM_MIN_FB, SIM_MAX_FB = 0.25, 0.65
        proxy_score = float(
            np.clip((sim_fb - SIM_MIN_FB) / (SIM_MAX_FB - SIM_MIN_FB) * 6.0, 0.0, 6.0)
        )
        max_score = 2.0 if domain_penalty >= 0.7 else 6.0
        final_score = round(min(proxy_score, max_score), 2)
        rationale = (
            f"CV khong co muc tieu nghe nghiep. "
            f"Diem proxy tu skills + kinh nghiem (max {max_score}/10): {proxy_score:.1f}/10."
            f" {'Domain khong lien quan.' if domain_penalty >= 0.7 else ''}"
        )
        return final_score, rationale, {"used_proxy": True, "has_objective": False}
    except Exception:
        default = 1.0 if domain_penalty >= 0.7 else 3.0
        rationale = (
            f"CV khong co muc tieu nghe nghiep. Khong the tinh diem proxy "
            f"(diem mac dinh {default}/10)."
            f" {'Domain khong lien quan.' if domain_penalty >= 0.7 else ''}"
        )
        return round(min(default, 3.0), 2), rationale, {"used_proxy": True, "has_objective": False}


def _score_with_objective(
    cv_objective: str,
    cv_data: dict,
    jd_data: dict,
    jd_struct: dict,
    embedder: EmbeddingService,
    domain_penalty: float,
    jd_goal_text: str,
) -> Tuple[float, str, dict]:
    """Score when CV has an explicit career objective."""
    SIM_MIN, SIM_MAX = get_sim_calibration(embedder)

    jd_focused_text = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("responsibilities", [])),
        jd_struct.get("industry", ""),
        jd_struct.get("career_expectations", ""),
    ]))

    score = 0.0
    sim = 0.0
    rationale_parts: list = []
    keyword_matches = 0

    try:
        cv_emb = embedder.encode(qprefix(cv_objective, embedder), normalize=True)
        jd_emb = embedder.encode(pprefix(jd_focused_text, embedder), normalize=True)
        sim = float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0))
        score = float(np.clip((sim - SIM_MIN) / (SIM_MAX - SIM_MIN) * 10.0, 0.0, 10.0))

        # Keyword Boost: CV objective contains JD job title keywords
        jd_title_lower = str(jd_data.get("job_title", "")).lower()
        title_kws = [w for w in re.split(r'\W+', jd_title_lower) if len(w) > 2]
        obj_lower = cv_objective.lower()
        keyword_matches = sum(1 for kw in title_kws if kw in obj_lower)

        if keyword_matches >= 2:
            score = max(score, 8.5)
        elif keyword_matches == 1:
            score = max(score, 6.0)

    except Exception as e:
        logger.warning(f"Embedding failed in career objectives scoring: {e}")
        sim = 0.0
        score = 0.0

    # Overqualified penalty: objective targets higher position than JD
    obj_lower = cv_objective.lower()
    senior_kws = ["manager", "senior", "lead", "director", "head", "chief", "principal"]
    jd_lower = jd_focused_text.lower()
    cv_targets_senior = any(kw in obj_lower for kw in senior_kws)
    jd_is_junior = any(kw in jd_lower for kw in ["intern", "fresher", "junior", "entry"])
    is_overqualified = cv_targets_senior and jd_is_junior
    if is_overqualified:
        score = max(score - 2.0, 0.0)
        rationale_parts.append("Mục tiêu vị trí cao hơn JD (overqualified).")

    # Rationale based on score
    if score >= 8.0:
        rationale_parts.append("Mục tiêu nghề nghiệp phù hợp cao với JD.")
    elif score >= 5.0:
        rationale_parts.append("Mục tiêu nghề nghiệp phù hợp với JD.")
    elif score >= 2.5:
        rationale_parts.append("Mục tiêu nghề nghiệp có liên quan một phần.")
    else:
        rationale_parts.append("Mục tiêu nghề nghiệp chưa phù hợp với JD.")

    rationale = " ".join(rationale_parts) if rationale_parts else "Mục tiêu nghề nghiệp chưa rõ ràng."

    # Severe domain mismatch — cap career score at 1.0
    if domain_penalty >= 0.7:
        score = min(score, 1.0)
        rationale = "Domain hoàn toàn không liên quan — mục tiêu nghề nghiệp không có giá trị cho JD này."

    final_score = round(min(score, 10.0), 2)
    details = {
        "has_objective": True,
        "used_proxy": False,
        "keyword_matches": keyword_matches,
        "is_overqualified": is_overqualified,
        "objective_preview": cv_objective[:100] if cv_objective else "",
    }
    return final_score, rationale, details
