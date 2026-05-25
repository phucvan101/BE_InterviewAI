# -*- coding: utf-8 -*-
"""
Company Fit Scoring Module (0-10).

Scores company/culture fit between CV and company data:
- [A] Tech Stack Match: CV skills vs company tech stack (F1-score style)
- [B] Domain/Industry Fit: CV domain vs company industry (semantic)
- [C] Culture Fit: CV objectives vs company culture/values (semantic)
- [D] Engineering Practices Bonus: CV evidence vs company engineering practices

Note: This score is separate from the total 100 and returned independently.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from ._shared import (
    build_skill_groups,
    coerce_string_list,
    get_sim_calibration,
    skill_group_match,
)

logger = logging.getLogger(__name__)


def score_company_fit(
    cv_data: dict,
    company_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    """
    Score company/culture fit (0-10).

    Returns: (score, rationale)

    Note: This score is NOT included in the total 100.

    Algorithm:
    [A] Tech Stack Match (0-4): F1-style coverage of company tech by CV skills
    [B] Domain/Industry Fit (0-3): Semantic similarity between CV and company industry
    [C] Culture Fit (0-2): Semantic similarity between CV objectives and company culture
    [D] Engineering Bonus (0-1): CV evidence vs company engineering practices
    """
    if not company_data or not company_data.get("success"):
        return 0.0, "Không có dữ liệu công ty."

    rationale_parts: List[str] = []

    # ── [A] Tech Stack Match (0-4.0) ───────────────────────────────
    tech_score, matched_tech = _score_tech_stack(cv_data, company_data)
    tech_rationale = (
        f"[Tech] {len(matched_tech)}/{len(build_skill_groups(_get_ci_tech(company_data)))} "
        f"nhom ky nang -> {tech_score}/4"
    ) if _get_ci_tech(company_data) else "[Tech] CI khong co du lieu tech stack -> mac dinh 2/4"
    rationale_parts.append(tech_rationale)

    # ── [B] Domain/Industry Fit (0-3.0) ────────────────────────────
    domain_score, domain_rationale = _score_domain_fit(cv_data, company_data, embedder)
    rationale_parts.append(f"[Domain] {domain_rationale} -> {domain_score}/3")

    # ── [C] Culture Fit (0-2.0) ────────────────────────────────────
    culture_score, culture_rationale = _score_culture_fit(cv_data, company_data, embedder)
    rationale_parts.append(f"[Culture] {culture_rationale} -> {culture_score}/2")

    # ── [D] Engineering Practices Bonus (0-1.0) ─────────────────────
    eng_bonus, eng_rationale = _score_engineering_bonus(cv_data, company_data, embedder)
    rationale_parts.append(f"[Engineering] {eng_rationale} -> +{eng_bonus}/1")

    # ── Total ──────────────────────────────────────────────────────
    total = round(min(tech_score + domain_score + culture_score + eng_bonus, 10.0), 2)
    summary = (
        f"Tech: {tech_score}/4 | Domain: {domain_score}/3 | "
        f"Culture: {culture_score}/2 | Engineering: {eng_bonus}/1 -> Tong: {total}/10"
    )
    rationale_parts.insert(0, summary)

    return total, " | ".join(rationale_parts)


def _get_ci_tech(company_data: dict) -> List[str]:
    """Collect all tech-related fields from company data."""
    ci_tech: List[str] = []
    for field in ("key_skills", "technologies", "primary_languages",
                  "frameworks", "databases", "infrastructure", "ai_ml_stack"):
        ci_tech.extend(company_data.get(field, []))
    return ci_tech


def _score_tech_stack(cv_data: dict, company_data: dict) -> Tuple[float, List[str]]:
    """Score tech stack match using F1-style coverage (0-4)."""
    ci_tech = _get_ci_tech(company_data)

    # Collect all CV skills
    cv_skill_pool: List[str] = []
    for field in ("skills", "technical_skills", "domain_skills"):
        cv_skill_pool.extend(cv_data.get(field, []))
    for proj in cv_data.get("projects", []):
        cv_skill_pool.extend(coerce_string_list(proj.get("technologies", [])))

    cv_groups = build_skill_groups(cv_skill_pool)
    comp_groups = build_skill_groups(ci_tech)

    if comp_groups:
        matched_tech, _ = skill_group_match(cv_groups, comp_groups)
        precision = len(matched_tech) / max(len(cv_groups), 1)
        recall = len(matched_tech) / max(len(comp_groups), 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-6)
        tech_score = round(min(f1 * 4.0, 4.0), 2)
    else:
        tech_score = 2.0
        matched_tech = []

    return tech_score, matched_tech


def _score_domain_fit(
    cv_data: dict,
    company_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    """Score domain/industry fit using semantic similarity (0-3)."""
    ci_industry_text = " ".join(filter(None, [
        str(company_data.get("industry", "")),
        str(company_data.get("sub_industry", "")),
        str(company_data.get("business_model", "")),
        " ".join(str(x) for x in company_data.get("ai_ml_stack", []) if x),
        str(company_data.get("tech_culture", "")),
    ])).lower()

    from ._shared import build_cv_text
    cv_text_for_domain = build_cv_text(cv_data)

    cv_domain = cv_data.get("domain")
    if not cv_domain or cv_domain == "unknown":
        from ._semantic.domain import detect_cv_domain_from_text
        cv_domain = detect_cv_domain_from_text(cv_text_for_domain, embedder, threshold=0.38)

    domain_score = 0.0
    domain_rationale = ""
    if ci_industry_text.strip():
        try:
            cv_text_for_domain = (cv_domain or "") + " " + cv_text_for_domain
            cv_dom_emb = embedder.encode(cv_text_for_domain[:600], normalize=True)
            ci_dom_emb = embedder.encode(ci_industry_text[:400], normalize=True)
            dom_sim = float(np.clip(np.dot(cv_dom_emb, ci_dom_emb), 0.0, 1.0))

            SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
            span = max(SIM_MAX - SIM_MIN, 0.1)
            scaled_sim = np.clip((dom_sim - SIM_MIN) / span, 0.0, 1.0)

            domain_score = round(scaled_sim * 3.0, 2)
            domain_rationale = f"Semantic match sim={dom_sim:.0%}"
        except Exception:
            domain_score, domain_rationale = 1.5, "Khong xac dinh duoc domain"
    else:
        domain_score, domain_rationale = 1.5, "CI khong co thong tin industry"

    return round(min(domain_score, 3.0), 2), domain_rationale


def _score_culture_fit(
    cv_data: dict,
    company_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    """Score culture fit using semantic similarity (0-2)."""
    ci_culture_text = " ".join(filter(None, [
        str(company_data.get("company_culture", "")),
        str(company_data.get("work_culture", "")),
        str(company_data.get("tech_culture", "")),
        str(company_data.get("remote_policy", "")),
        str(company_data.get("mission", "")),
        " ".join(str(x) for x in company_data.get("values", []) if x),
        " ".join(str(x) for x in company_data.get("products", []) if x),
        " ".join(str(x) for x in company_data.get("target_customers", []) if x),
    ]))

    cv_objective = (
        cv_data.get("career_objectives") or cv_data.get("objective") or ""
    ).strip()
    if not cv_objective:
        proxy_pool = (
            cv_data.get("skills", [])[:10]
            + [e.get("title", "") for e in cv_data.get("work_experience", [])[:3] if e.get("title")]
        )
        cv_objective = " ".join(str(x) for x in proxy_pool if x)

    culture_score = 0.0
    culture_rationale = ""
    if ci_culture_text.strip() and cv_objective:
        try:
            SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
            cv_cul_emb = embedder.encode(cv_objective[:600], normalize=True)
            ci_cul_emb = embedder.encode(ci_culture_text[:600], normalize=True)
            cul_sim = float(np.clip(np.dot(cv_cul_emb, ci_cul_emb), 0.0, 1.0))
            cul_scaled = float(
                np.clip((cul_sim - SIM_MIN) / max(SIM_MAX - SIM_MIN, 0.1), 0.0, 1.0)
            )
            culture_score = round(min(cul_scaled * 2.0, 2.0), 2)
            culture_rationale = f"sim={cul_sim:.0%} (scaled={cul_scaled:.0%})"
        except Exception as e:
            logger.warning(f"Embedding failed in culture fit: {e}")
            culture_score = 1.0
            culture_rationale = "Loi embedding -> mac dinh 1/2"
    else:
        culture_score = 1.0
        culture_rationale = "Thieu thong tin van hoa cong ty -> mac dinh 1/2"

    return culture_score, culture_rationale


def _score_engineering_bonus(
    cv_data: dict,
    company_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    """Score engineering practices bonus (0-1)."""
    ci_eng_practices: List[str] = company_data.get("engineering_practices", [])
    eng_bonus = 0.0
    eng_rationale = ""

    if ci_eng_practices:
        cv_evidence_text = " ".join(filter(None, [
            " ".join(str(x) for x in cv_data.get("skills", []) if x),
            " ".join(str(x) for x in cv_data.get("technical_skills", []) if x),
            " ".join(
                hl
                for exp in cv_data.get("work_experience", [])
                for hl in coerce_string_list(exp.get("highlights", []))
            ),
        ])).lower()

        ci_practices_text = " ".join(str(x) for x in ci_eng_practices if x).lower()

        try:
            cv_prac_emb = embedder.encode(cv_evidence_text[:600], normalize=True)
            ci_prac_emb = embedder.encode(ci_practices_text[:400], normalize=True)
            prac_sim = float(np.clip(np.dot(cv_prac_emb, ci_prac_emb), 0.0, 1.0))

            SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
            span = max(SIM_MAX - SIM_MIN, 0.1)
            scaled_sim = np.clip((prac_sim - SIM_MIN) / span, 0.0, 1.0)

            eng_bonus = round(scaled_sim * 1.0, 2)
            eng_rationale = f"semantic sim={prac_sim:.0%} -> +{eng_bonus}"
        except Exception:
            eng_bonus = 0.0
            eng_rationale = "Loi embedding -> +0/1"
    else:
        eng_rationale = "CI khong co engineering_practices -> +0"

    return eng_bonus, eng_rationale
