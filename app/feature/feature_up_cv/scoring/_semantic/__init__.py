# -*- coding: utf-8 -*-
"""
Semantic matching module.

Provides embedding-based matching utilities:
- Domain detection
- Seniority level detection
- Project relevance scoring
"""

from .domain import (
    SemanticDomainDetector,
    detect_cv_domain,
    detect_jd_domain,
)

from .seniority import (
    SemanticSeniorityDetector,
    detect_seniority_level,
)

from .project_relevance import (
    compute_project_relevance,
    expand_proj_tech,
)

__all__ = [
    "SemanticDomainDetector",
    "detect_cv_domain",
    "detect_jd_domain",
    "SemanticSeniorityDetector",
    "detect_seniority_level",
    "compute_project_relevance",
    "expand_proj_tech",
]
