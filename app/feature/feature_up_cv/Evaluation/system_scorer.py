# -*- coding: utf-8 -*-
"""
System scorer — wraps hybrid_scoring.calculate_hybrid_score() for benchmark use.

Runs the system's own scoring engine on a parsed CV-JD pair and returns
scores in a standardized dict format.
"""
import sys
import os
from pathlib import Path

# Ensure the BE_InterviewAI root is on the path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import (
    get_embedding_service,
    EmbeddingService,
)
from app.feature.feature_up_cv.scoring.hybrid_scoring import calculate_hybrid_score


def _build_cv_text(cv_data: dict) -> str:
    parts = [
        cv_data.get("objective", ""),
        cv_data.get("career_objectives", ""),
        " ".join(cv_data.get("skills", [])),
        " ".join(cv_data.get("domain_skills", [])),
        " ".join(cv_data.get("technical_skills", [])),
    ]
    for proj in cv_data.get("projects", []):
        parts.append(proj.get("name", ""))
        parts.append(proj.get("description", ""))
        parts.extend(proj.get("technologies", []))
    for exp in cv_data.get("work_experience", []):
        parts.append(exp.get("title", ""))
        parts.append(exp.get("description", ""))
    return " ".join(p for p in parts if p)


def _build_jd_text(jd_data: dict) -> str:
    jd_struct = jd_data.get("structured", jd_data)
    parts = [
        jd_data.get("job_title", ""),
        jd_struct.get("job_title", ""),
        jd_struct.get("industry", ""),
        " ".join(jd_struct.get("skills_required", [])),
        " ".join(jd_struct.get("skills_preferred", [])),
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
    ]
    return " ".join(p for p in parts if p)


def score_with_system(cv_data: dict, jd_data: dict) -> dict:
    """
    Run the system's hybrid scoring engine on a CV-JD pair.

    Returns a dict:
    {
        "overall_score": float,
        "experience_score": float,   # 0-50
        "skills_score": float,       # 0-30 (total)
        "skills_keyword_score": float,
        "skills_embedding_score": float,
        "education_score": float,    # 0-10
        "career_objectives_score": float,  # 0-10
        "company_fit_score": float,   # 0-10 (separate, not in total)
        "embedding_similarity": float,
        "score_rationale": str,
        "matched_skills": list,
        "missing_skills": list,
        "experience_assessment": str,
        "recommendation": str,
        "cv_candidate": str,
        "job_position": str,
    }
    """
    try:
        embedder: EmbeddingService = get_embedding_service()
        cv_embedding = embedder.encode(_build_cv_text(cv_data))
        jd_embedding = embedder.encode(_build_jd_text(jd_data))

        result = calculate_hybrid_score(
            cv_data=cv_data,
            jd_data=jd_data,
            company_data=None,
            cv_embedding=cv_embedding,
            jd_embedding=jd_embedding,
        )

        ds = result.get("detailed_scores", {})

        return {
            "overall_score": float(result.get("overall_score", 0)),
            "experience_score": float(ds.get("experience_score", 0)),
            "skills_score": float(ds.get("skills_total_score", 0)),
            "skills_keyword_score": float(ds.get("skills_keyword_score", 0)),
            "skills_embedding_score": float(ds.get("skills_embedding_score", 0)),
            "education_score": float(ds.get("education_score", 0)),
            "career_objectives_score": float(ds.get("career_objectives_score", 0)),
            "company_fit_score": float(ds.get("company_fit_score", 0)),
            "embedding_similarity": float(result.get("embedding_similarity", 0)),
            "score_rationale": str(result.get("score_rationale", "")),
            "matched_skills": result.get("matched_skills", []),
            "missing_skills": result.get("missing_skills", []),
            "experience_assessment": str(result.get("experience_assessment", "")),
            "recommendation": str(result.get("recommendation", "")),
            "cv_candidate": str(result.get("cv_candidate", "")),
            "job_position": str(result.get("job_position", "")),
            "error": None,
        }
    except Exception as e:
        return {
            "overall_score": 0,
            "experience_score": 0,
            "skills_score": 0,
            "skills_keyword_score": 0,
            "skills_embedding_score": 0,
            "education_score": 0,
            "career_objectives_score": 0,
            "company_fit_score": 0,
            "embedding_similarity": 0,
            "score_rationale": "",
            "matched_skills": [],
            "missing_skills": [],
            "experience_assessment": "",
            "recommendation": "",
            "cv_candidate": "",
            "job_position": "",
            "error": str(e),
        }
