# -*- coding: utf-8 -*-
"""
Semantic seniority level detection using embedding similarity with seniority anchors.
"""

from typing import List

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from .._scores._shared import (
    _seniority_anchors_embs,
    ensure_anchor_embs,
    qprefix,
)


class SemanticSeniorityDetector:
    """Stateful wrapper for semantic seniority detection with caching."""

    def __init__(self, embedder: EmbeddingService):
        self.embedder = embedder
        ensure_anchor_embs(embedder)

    def detect(self, titles: List[str], descriptions: List[str]) -> int:
        """
        Detect seniority level from CV titles and descriptions.

        Returns level 0-4:
            0 = Intern/Fresher
            1 = Junior
            2 = Mid-level
            3 = Senior
            4 = Lead/Principal/Manager
        """
        return detect_seniority_level(titles, descriptions, self.embedder)


def detect_seniority_level(
    titles: List[str],
    descriptions: List[str],
    embedder: EmbeddingService,
) -> int:
    """
    Detect seniority level using semantic similarity with anchor descriptions.

    Returns level 0-4:
        0 = Intern/Fresher
        1 = Junior
        2 = Mid-level
        3 = Senior
        4 = Lead/Principal/Manager
    """
    ensure_anchor_embs(embedder)
    if not titles and not descriptions:
        return 0

    cv_text = " ".join(titles + descriptions)
    if not cv_text.strip():
        return 0

    from .._scores._shared import _seniority_anchors_embs

    cv_emb = embedder.encode(qprefix(cv_text, embedder), normalize=True)
    best_level = 0
    best_sim = -1.0
    for level, anchor_emb in _seniority_anchors_embs.items():
        sim = float(np.dot(cv_emb, anchor_emb))
        if sim > best_sim:
            best_sim = sim
            best_level = level

    return best_level
