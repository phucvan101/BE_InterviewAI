# -*- coding: utf-8 -*-
"""
Scoring modules.

Each module is responsible for scoring one aspect of the CV-JD match:
- experience_score: work experience + projects scoring (0-50)
- skills_score: technical skills + criteria matching (0-30)
- education_score: education level + major relevance (0-10)
- career_score: career objectives alignment (0-10)
- company_fit_score: company/culture fit (0-10, not in total 100)

Shared utilities are in _shared.py.
"""

from ._shared import (
    SCORING_CONFIG,
    ScoringConfig,
    MATCH_PERFECT,
    MATCH_RELEVANT,
    MATCH_MISS,
    _SOFT_SKILL_KEYS,
    build_cv_text,
    build_jd_text,
    compute_domain_penalty,
    criterion_weight,
    dedupe_strings,
    expand_proj_tech,
    get_sim_calibration,
    is_soft_skill_text,
    normalize_skill_key,
    qprefix,
    qprefix_batch,
    pprefix,
    pprefix_batch,
    safe_cap,
    skill_group_match,
    build_skill_groups,
)

__all__ = [
    "SCORING_CONFIG",
    "ScoringConfig",
    "MATCH_PERFECT",
    "MATCH_RELEVANT",
    "MATCH_MISS",
]
