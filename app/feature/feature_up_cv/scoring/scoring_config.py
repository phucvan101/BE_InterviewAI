# -*- coding: utf-8 -*-
"""Scoring configuration and small helpers for hybrid scoring.

This module centralizes thresholds, caps, and small helper functions so
the main scoring logic can import them and remain focused.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ScoringConfig:
    EXPERIENCE_WEIGHT: float = 50.0
    SKILLS_WEIGHT: float = 30.0
    EDUCATION_WEIGHT: float = 10.0
    CAREER_WEIGHT: float = 10.0

    SEMANTIC_MATCH_THRESHOLD: float = 0.80
    RELATED_MATCH_THRESHOLD: float = 0.62

    UNDERQUALIFIED_CAP: float = 30.0
    SEVERE_GAP_CAP: float = 25.0
    SPECIALIZATION_MISMATCH_CAP: float = 35.0

    # Criteria matching thresholds (atomic skills vs generic criteria)
    ATOMIC_MATCH_THRESHOLD: float = 0.88
    ATOMIC_RELATED_THRESHOLD: float = 0.68
    GENERIC_MATCH_THRESHOLD: float = 0.80
    GENERIC_RELATED_THRESHOLD: float = 0.62

    # Skills scoring caps and domain thresholds
    SKILLS_MAX: float = 30.0
    DOMAIN_CAP_SEVERE: float = 12.0
    DOMAIN_CAP_MODERATE: float = 18.0
    DOMAIN_CAP_SEMANTIC_MISMATCH_MAX: float = 8.0
    DOMAIN_CAP_SEVERE_PENALTY: float = 0.7
    DOMAIN_CAP_SEVERE_COVERAGE: float = 0.35
    DOMAIN_CAP_MODERATE_PENALTY: float = 0.4
    DOMAIN_CAP_MODERATE_COVERAGE: float = 0.25
    DOMAIN_CAP_SEMANTIC_MISMATCH_PENALTY: float = 0.5
    DOMAIN_CAP_SEMANTIC_MISMATCH_COVERAGE: float = 0.20
    # Reranker config: when enabled, rerank top-K projects using a cross-encoder
    RERANK_TOP_K: int = 3
    # How much to trust the original hybrid relevance vs reranker (0-1)
    # final = RERANK_WEIGHT * original + (1-RERANK_WEIGHT) * reranker_score
    RERANK_WEIGHT: float = 0.60
    # Default cross-encoder model name (CrossEncoder).
    CE_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Whether to run cross-encoder verification on semantic matches
    CE_VERIFY_ENABLED: bool = True
    # Threshold (0-1) on normalized cross-encoder score to accept a semantic match
    CE_VERIFICATION_THRESHOLD: float = 0.65


SCORING_CONFIG = ScoringConfig()


def _safe_cap(value: float, cap: float) -> float:
    """Safely cap a numeric value.

    Returns min(value, cap) when possible; if conversion fails, returns original value.
    """
    try:
        return min(float(value), float(cap))
    except Exception:
        return value


def _build_experience_features(
    all_exp_years: float,
    years_req: float,
    skill_overlap: float,
    domain_penalty: float,
    seniority_gap: int,
) -> Dict[str, Any]:
    """Return a small feature dict summarizing experience-related signals.

    Useful for later refactor into feature-based scoring or learning-to-rank.
    """
    return {
        "years_ratio": round(all_exp_years / max(years_req, 1.0), 4),
        "skill_overlap": round(skill_overlap, 4),
        "domain_penalty": round(domain_penalty, 4),
        "seniority_gap": int(seniority_gap),
    }


__all__ = [
    "ScoringConfig",
    "SCORING_CONFIG",
    "_safe_cap",
    "_build_experience_features",
]
