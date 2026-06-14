# -*- coding: utf-8 -*-
"""
Education Scoring Module (0-10).

Scores education based on:
- Degree level (PhD → Trung cấp)
- Major relevance to JD (semantic embedding)
- Certifications
- Domain penalty
- Student/intern status
"""


from typing import List, Tuple

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService


def _major_relevance_score(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
) -> float:
    """
    Semantic-based major relevance scoring.

    Returns float 0.0-1.0:
        1.0 = strong major-domain match
        0.5 = partial/adjacent match
        0.0 = no relevance
    """
    if not cv_education:
        return 0.0

    jd_struct = jd_data.get("structured", jd_data)

    # Build JD context text
    jd_context_parts = [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
        " ".join(jd_struct.get("skills_required", [])),
        " ".join(jd_struct.get("skills_preferred", [])),
    ]
    jd_context = " ".join(filter(None, jd_context_parts)).strip()

    # Build education texts
    edu_texts: List[str] = []
    for edu in cv_education:
        edu_parts = [
            edu.get("major", ""),
            edu.get("degree", ""),
            edu.get("school", ""),
            edu.get("description", ""),
        ]
        filtered = [p.strip() for p in edu_parts if p.strip()]
        edu_text = " ".join(filtered)
        if edu_text:
            edu_texts.append(edu_text)

    if not edu_texts or not jd_context:
        return 0.0

    try:
        from app.feature.feature_up_cv.scoring._scores._shared import (
            get_sim_calibration,
            pprefix_batch,
            qprefix,
        )
        SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
        span = max(SIM_MAX - SIM_MIN, 0.05)

        jd_emb = embedder.encode(qprefix(jd_context, embedder), normalize=True)
        edu_embs = embedder.encode_batch(
            pprefix_batch(edu_texts, embedder), normalize=True
        )

        best_sim = 0.0
        for i in range(len(edu_texts)):
            raw_sim = float(edu_embs[i] @ jd_emb)
            normalized_sim = max(0.0, min(1.0, (raw_sim - SIM_MIN) / span))
            if normalized_sim > best_sim:
                best_sim = normalized_sim

        return round(best_sim, 3)

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Major relevance embedding failed: {e}")
        return 0.0


def _semantic_major_relevance(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> bool:
    """Legacy wrapper — returns True if _major_relevance_score >= threshold."""
    score = _major_relevance_score(cv_education, jd_data, embedder)
    return score >= threshold


def score_education(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float = 0.0,
) -> Tuple[float, str]:
    """
    Score education (0-10).

    Returns: (score, rationale)

    Algorithm:
    1. Parse JD required degree level
    2. Extract CV degree level
    3. Compute base score based on degree match
    4. Apply major relevance (semantic embedding)
    5. Add certification bonus
    6. Apply domain penalty caps
    """
    jd_struct = jd_data.get("structured", jd_data)
    req_text = " ".join(jd_struct.get("requirements", []))

    degree_map = {
        "phd": 5, "tiến sĩ": 5, "doctor": 5,
        "thạc sĩ": 4, "master": 4, "m.sc": 4,
        "cử nhân": 3, "bachelor": 3, "b.sc": 3, "đại học": 3,
        "cao đẳng": 2, "college": 2,
        "trung cấp": 1,
    }

    req_degree = 0
    for kw, val in degree_map.items():
        if kw in req_text.lower():
            req_degree = max(req_degree, val)

    cv_degree = 0
    for edu in cv_data.get("education", []):
        text = f"{edu.get('degree', '')} {edu.get('major', '')} {edu.get('school', '')}".lower()
        for kw, val in degree_map.items():
            if kw in text:
                cv_degree = max(cv_degree, val)
        if edu.get("degree") or edu.get("major"):
            cv_degree = max(cv_degree, 2)

    cv_is_student = cv_data.get("is_student", False)
    if cv_is_student:
        cv_degree = max(cv_degree, 3)

    # Severe domain mismatch — major relevance forced to False
    if domain_penalty >= 0.7:
        cv_major_match = False
        is_severe_domain_mismatch = True
    else:
        cv_major_match = _semantic_major_relevance(
            cv_data.get("education", []), jd_data, embedder, threshold=0.40
        )
        is_severe_domain_mismatch = False

    cert_count = len(cv_data.get("certifications", []))
    jd_is_intern_student = jd_struct.get("is_entry_level", False)

    effective_req_degree = req_degree
    if req_degree == 0 and jd_is_intern_student:
        effective_req_degree = 3

    if effective_req_degree > 0:
        if cv_degree >= effective_req_degree:
            base = 8.0 if cv_major_match else 5.0
        elif cv_is_student and cv_degree >= effective_req_degree - 1:
            base = 7.5 if cv_major_match else 4.5
        else:
            base = max(0.0, (cv_degree / max(effective_req_degree, 1)) * 5.0)
            if cv_major_match:
                base += 1.5
    else:
        base = 6.0 if cv_major_match else 4.0

    # Severe domain mismatch — hard cap on base
    if is_severe_domain_mismatch:
        base = min(base, 2.0)
        cert_bonus_max = 1.0
    elif domain_penalty >= 0.5:
        base = min(base, 4.0)
        cert_bonus_max = 1.0
    else:
        cert_bonus_max = 2.0

    # Bonus for students in relevant major
    if cv_is_student and cv_major_match:
        base = min(base + 1.0, 9.0)

    # Certifications: +0.5 each (max 4 = 2.0 bonus)
    score = min(base + min(cert_count, 4) * 0.5, 10.0)
    score = min(score, base + cert_bonus_max)

    major_note = "Ngành học phù hợp." if cv_major_match else "Ngành học không liên quan trực tiếp."
    student_note = " Đang học (chưa tốt nghiệp)." if cv_is_student else ""
    if is_severe_domain_mismatch:
        major_note = "Domain hoàn toàn không liên quan — ngành học không có giá trị cho JD này."
        student_note = " Đang học (chưa tốt nghiệp)." if cv_is_student else ""

    rationale = f"Trình độ: {cv_degree}/5.{student_note} {major_note}"
    if cert_count > 0:
        rationale += f" Có {cert_count} chứng chỉ liên quan."

    return round(min(score, 10.0), 2), rationale
