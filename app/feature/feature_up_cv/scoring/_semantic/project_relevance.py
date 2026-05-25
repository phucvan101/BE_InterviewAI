# -*- coding: utf-8 -*-
"""
Semantic project relevance scoring.

Combines embedding similarity and tech stack exact match to compute
per-project relevance scores to JD responsibilities.
"""

from __future__ import annotations

import datetime
import logging
import math
import re
from typing import Any, Dict, List, Tuple

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from .._scores._shared import (
    SCORING_CONFIG,
    _PROJECT_TECH_EQUIVALENTS,
    expand_proj_tech,
    get_sim_calibration,
    pprefix,
    pprefix_batch,
    qprefix,
)

logger = logging.getLogger(__name__)


def compute_project_relevance(
    projects: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
    default_duration: float = 0.25,
    use_reranker: bool = True,
) -> Tuple[float, List[float], List[str]]:
    """
    Compute semantic project relevance: embedding similarity + tech stack exact match.

    Flow:
    1. Embed project description vs JD responsibilities (semantic)
    2. Exact intersection of project technologies vs JD skills (tech match)
    3. Final relevance = weighted combination

    Returns (total_project_years, relevance_scores_per_project, project_descriptions).

    total_project_years: sum of (duration * relevance) for each project
    relevance_scores_per_project: per-project relevance [0, 1]
    project_descriptions: original project text strings
    """
    if not projects:
        return 0.0, [], []

    jd_struct = jd_data.get("structured", jd_data)

    # ── Precompute tech match scores for all projects ──────────────────
    jd_skills_all = set(
        s.lower()
        for s in (jd_struct.get("skills_required", []) + jd_struct.get("skills_preferred", []))
    )
    skill_importance = jd_struct.get("skill_importance", {})
    jd_critical = set(s.lower() for s in jd_struct.get("skills_required", []))
    jd_important = {
        s.lower()
        for s in jd_struct.get("skills_required", [])
        if skill_importance.get(s, "").lower() in ("important", "critical")
    }
    total_required = len(jd_critical)
    total_important = max(len(jd_important), 1)

    tech_info: List[Dict[str, Any]] = []
    for proj in projects:
        expanded_techs: set = set()
        for t in proj.get("technologies", []):
            expanded_techs.update(expand_proj_tech(t))
        intersection = jd_skills_all.intersection(expanded_techs)
        critical_hits = len(intersection.intersection(jd_critical))
        important_hits = len(intersection.intersection(jd_important))

        quality_score = (
            2.0 * critical_hits / max(total_required, 1)
            + 1.0 * important_hits / total_important
        ) / 3.0

        tech_info.append({
            "intersection": intersection,
            "intersection_count": len(intersection),
            "critical_hits": critical_hits,
            "quality_score": quality_score,
        })

    # ── Build JD responsibilities text ───────────────────────────────
    resp_text = " ".join(jd_struct.get("responsibilities", []))
    req_text = " ".join(jd_struct.get("requirements", []))
    if len(resp_text.split()) < 50:
        resp_text = resp_text + " " + req_text

    # ── Build project texts ────────────────────────────────────────────
    proj_texts = []
    for proj in projects:
        parts = [proj.get("name", ""), proj.get("description", "")]
        for hl in proj.get("highlights", []):
            parts.append(str(hl))
        proj_texts.append(" ".join(p for p in parts if p))

    # ── Semantic embedding ─────────────────────────────────────────────
    try:
        jd_emb = embedder.encode(qprefix(resp_text, embedder), normalize=True)
        proj_prefixed = pprefix_batch(proj_texts, embedder)
        proj_embs = embedder.encode_batch(proj_prefixed, normalize=True)
        sims = np.clip(proj_embs @ jd_emb, 0.0, 1.0)
    except Exception as e:
        logger.warning(f"compute_project_relevance embedding failed: {e}")
        return 0.0, [], proj_texts

    SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
    span = max(SIM_MAX - SIM_MIN, 0.05)

    # ── Duration computation ───────────────────────────────────────────
    durations: List[float] = []
    for proj in projects:
        if proj.get("start") and not proj.get("end"):
            durations.append(default_duration)
        elif proj.get("start") or proj.get("end"):
            parsed = _parse_years(proj.get("start", ""), proj.get("end", ""))
            durations.append(parsed if parsed > 0 else default_duration)
        else:
            durations.append(default_duration)

    relevance_scores: List[float] = []
    descriptions: List[str] = []

    # ── Compute per-project hybrid relevance ───────────────────────────
    for i, (proj, dur) in enumerate(zip(projects, durations)):
        raw_sim = float(sims[i])
        normalized_sim = (raw_sim - SIM_MIN) / span

        intersection_count = tech_info[i]["intersection_count"]
        tech_score = min(0.10 + 0.35 * math.sqrt(intersection_count), 0.70)
        has_tech = intersection_count > 0

        semantic_score = max(0.0, normalized_sim)
        critical_hits = tech_info[i].get("critical_hits", 0)

        if has_tech:
            if intersection_count >= 2 or critical_hits > 0:
                tech_weight = 0.70
            elif intersection_count == 1:
                tech_weight = 0.60
            else:
                tech_weight = 0.55
            relevance = float(
                np.clip(
                    tech_weight * tech_score
                    + (1.0 - tech_weight) * semantic_score,
                    0.0, 1.0,
                )
            )
        else:
            relevance = float(np.clip(0.70 * semantic_score, 0.0, 1.0))

        relevance_scores.append(float(np.clip(relevance, 0.0, 1.0)))
        descriptions.append(proj_texts[i])

    # ── Optional: cross-encoder reranking for top-K candidates ─────────
    if use_reranker and len(relevance_scores) > 0:
        _apply_reranking(
            relevance_scores, proj_texts, resp_text, embedder,
            top_k=min(SCORING_CONFIG.RERANK_TOP_K, len(relevance_scores)),
        )

    # ── Compute total project years ────────────────────────────────────
    total_years = 0.0
    for dur, rel in zip(durations, relevance_scores):
        total_years += dur * float(rel)

    return total_years, relevance_scores, descriptions


def _apply_reranking(
    relevance_scores: List[float],
    proj_texts: List[str],
    resp_text: str,
    embedder: EmbeddingService,
    top_k: int = 3,
) -> None:
    """Apply cross-encoder reranking in-place to top-K candidates."""
    try:
        from app.feature.feature_up_cv.scoring.cross_encoder_reranker import CrossEncoderReranker
        ce = CrossEncoderReranker(model_name=SCORING_CONFIG.CE_MODEL_NAME)
        top_idxs = list(np.argsort(relevance_scores)[::-1][:top_k])
        candidates = [proj_texts[i] for i in top_idxs]
        ce_raw = ce.score(resp_text, candidates)
        if ce_raw:
            ce_arr = np.array(ce_raw, dtype=float)
            if float(np.ptp(ce_arr)) == 0.0:
                ce_norm = np.full_like(ce_arr, 0.5)
            else:
                ce_norm = (ce_arr - ce_arr.min()) / float(np.ptp(ce_arr))
            beta = float(np.clip(SCORING_CONFIG.RERANK_WEIGHT, 0.0, 1.0))
            for idx, ce_score in zip(top_idxs, ce_norm.tolist()):
                orig = relevance_scores[idx]
                new_rel = float(
                    np.clip(beta * orig + (1.0 - beta) * float(ce_score), 0.0, 1.0)
                )
                relevance_scores[idx] = new_rel
    except Exception as e:
        logger.debug("Reranker failed: %s", e)


def _parse_years(start: str, end: str) -> float:
    """Parse years from start/end strings."""
    try:
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
