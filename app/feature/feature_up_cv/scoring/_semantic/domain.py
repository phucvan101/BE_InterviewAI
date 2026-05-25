# -*- coding: utf-8 -*-
"""
Semantic domain detection using embedding similarity with domain anchors.
"""

from typing import Optional

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from .._scores._shared import (
    _DOMAIN_ANCHORS,
    ensure_anchor_embs,
    get_sim_calibration,
    build_cv_text,
    build_jd_text,
)


class SemanticDomainDetector:
    """Stateful wrapper for semantic domain detection with caching."""

    def __init__(self, embedder: EmbeddingService, threshold: float = 0.40):
        self.embedder = embedder
        self.threshold = threshold
        ensure_anchor_embs(embedder)

    def detect(self, text: str) -> str:
        """
        Detect domain from text using semantic similarity.

        Returns one of: tech_ai, tech_software, tech_data, tech_devops,
        tech_security, sales, marketing, finance, hr, operations,
        healthcare, education, design, unknown.
        """
        return detect_cv_domain_from_text(text, self.embedder, self.threshold)


def detect_cv_domain_from_text(
    text: str,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> str:
    """
    Detect CV domain from arbitrary text using semantic similarity.
    Falls back to keyword-based detection if semantic score is too low.
    """
    ensure_anchor_embs(embedder)
    if not text.strip():
        return "unknown"

    from .._scores._shared import _domain_anchors_embs

    text_emb = embedder.encode(
        f"query: {text}" if "e5" in str(getattr(embedder, "model_name", "")).lower() else text,
        normalize=True,
    )
    scores: dict = {
        key: float(np.dot(text_emb, anchor_emb))
        for key, anchor_emb in _domain_anchors_embs.items()
    }

    best_domain = max(scores, key=lambda d: scores[d])
    best_score = scores[best_domain]
    second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0

    if best_score >= threshold and (best_score - second_best) >= 0.03:
        return best_domain

    return best_domain if best_score >= threshold else "unknown"


def detect_cv_domain(
    cv_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> str:
    """Detect domain from CV data."""
    cv_domain = cv_data.get("domain")
    if cv_domain and cv_domain != "unknown":
        return cv_domain
    cv_text = build_cv_text(cv_data)
    return detect_cv_domain_from_text(cv_text, embedder, threshold)


def detect_jd_domain(
    jd_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> str:
    """Detect domain from JD data."""
    jd_struct = jd_data.get("structured", {})
    jd_domain = jd_struct.get("domain") if isinstance(jd_struct, dict) else None
    if jd_domain and jd_domain != "unknown":
        return jd_domain
    jd_text = build_jd_text(jd_data)
    return detect_cv_domain_from_text(jd_text, embedder, threshold)
