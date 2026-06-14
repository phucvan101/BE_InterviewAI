# -*- coding: utf-8 -*-
"""
Skills Scoring Module (0-30).

Scores technical skills based on:
- JD-generated criteria matching (CRITICAL/IMPORTANT/BONUS)
- 3-way match classification: PERFECT_MATCH, RELEVANT_MATCH, MISS_MATCH
- Domain penalty caps
- Cross-encoder verification for semantic matches
"""


import logging
import re
from typing import Any, Dict, List, Tuple

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import EmbeddingService

from ._shared import (
    SCORING_CONFIG,
    MATCH_PERFECT,
    MATCH_RELEVANT,
    MATCH_MISS,
    _SOFT_SKILL_KEYS,
    build_skill_groups,
    coerce_string_list,
    criterion_id,
    criterion_key,
    criterion_weight,
    dedupe_strings,
    get_sim_calibration,
    is_soft_skill_text,
    normalize_importance,
    normalize_skill_key,
    pprefix_batch,
    qprefix_batch,
)

logger = logging.getLogger(__name__)

_ScoreRatio = {
    MATCH_PERFECT: 1.0,
    MATCH_RELEVANT: 0.7,
    MATCH_MISS: 0.0,
}


# ── CV Evidence Collection ──────────────────────────────────────────────────────────────────
def collect_cv_evidence(cv_data: dict) -> Tuple[List[str], List[str]]:
    """
    Collect CV evidence: (skill_pool, full_evidence_strings).

    skill_pool: deduplicated normalized skill list
    full_evidence_strings: all text snippets for semantic matching
    """
    explicit_soft = {
        normalize_skill_key(s)
        for s in cv_data.get("soft_skills", [])
        if isinstance(s, str) and s.strip()
    }

    skill_pool: List[str] = []
    for key in ("technical_skills", "domain_skills"):
        skill_pool.extend(s for s in cv_data.get(key, []) if isinstance(s, str))
    for s in cv_data.get("skills", []):
        if isinstance(s, str) and normalize_skill_key(s) not in explicit_soft:
            skill_pool.append(s)
    for proj in cv_data.get("projects", []):
        skill_pool.extend(coerce_string_list(proj.get("technologies", [])))
    for cert in cv_data.get("certifications", []):
        if isinstance(cert, str):
            skill_pool.append(cert)
        elif isinstance(cert, dict):
            skill_pool.append(" ".join(str(v) for v in cert.values() if v))

    for lang in cv_data.get("languages", []):
        if isinstance(lang, dict):
            lang_name = lang.get("language", "").strip()
            prof = lang.get("proficiency", "").strip()
            if lang_name:
                skill_pool.append(f"{lang_name} {prof}".strip())

    evidence: List[str] = []
    evidence.extend(skill_pool)
    evidence.extend(s for s in cv_data.get("soft_skills", []) if isinstance(s, str))
    if cv_data.get("career_objectives"):
        evidence.append(str(cv_data.get("career_objectives")))
    if cv_data.get("objective"):
        evidence.append(str(cv_data.get("objective")))

    for exp in cv_data.get("work_experience", []):
        parts = [exp.get("title", ""), exp.get("company", ""), exp.get("description", "")]
        evidence.append(" ".join(str(p) for p in parts if p))
        for key in ("highlights", "responsibilities", "achievements"):
            evidence.extend(coerce_string_list(exp.get(key, [])))

    for proj in cv_data.get("projects", []):
        parts = [
            proj.get("name", ""), proj.get("role", ""), proj.get("description", ""),
            " ".join(coerce_string_list(proj.get("technologies", []))),
        ]
        evidence.append(" ".join(str(p) for p in parts if p))
        for key in ("highlights", "responsibilities"):
            evidence.extend(coerce_string_list(proj.get(key, [])))

    for edu in cv_data.get("education", []):
        parts = [
            edu.get("degree", ""), edu.get("major", ""), edu.get("school", ""),
            edu.get("description", ""), edu.get("details", ""),
        ]
        evidence.append(" ".join(str(p) for p in parts if p))

    return dedupe_strings(skill_pool), dedupe_strings([e[:700] for e in evidence])


# ── JD Criteria Builder ──────────────────────────────────────────────────────────────────
def build_jd_criteria(jd_data: dict) -> List[Dict[str, Any]]:
    """Build criteria list from JD data (parser output or fallback fields)."""
    jd_struct = jd_data.get("structured", jd_data)
    skill_importance = jd_struct.get("skill_importance", {})
    if not isinstance(skill_importance, dict):
        skill_importance = {}

    criteria: List[Dict[str, Any]] = []
    seen: set = set()

    def add(item: Any) -> None:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            return
        name = str(item.get("name") or item.get("criterion") or "").strip()
        if not name:
            return
        key = criterion_key(name)
        if not key or key in seen:
            return
        seen.add(key)
        idx = len(criteria) + 1
        criteria.append({
            "id": str(item.get("id") or criterion_id(idx, name)),
            "name": name,
            "category": str(item.get("category") or "requirement").strip() or "requirement",
            "importance": normalize_importance(item.get("importance")),
            "evidence_needed": str(
                item.get("evidence_needed") or f"CV cần có bằng chứng đáp ứng: {name}."
            ).strip(),
            "acceptable_equivalents": coerce_string_list(item.get("acceptable_equivalents", [])),
            "source": str(item.get("source") or "").strip(),
            "source_text": str(item.get("source_text") or "").strip(),
            "question_intent": str(
                item.get("question_intent") or "validate_depth"
            ).strip() or "validate_depth",
        })

    for item in jd_struct.get("evaluation_criteria", []):
        add(item)

    for skill in [s for s in jd_struct.get("skills_required", [])
                  if isinstance(s, str) and s.strip()]:
        if criterion_key(skill) not in seen:
            add({
                "name": skill,
                "category": "soft_skill" if is_soft_skill_text(skill) else "skill",
                "importance": skill_importance.get(skill, "IMPORTANT"),
                "source": "skills_required",
                "source_text": skill,
                "question_intent": "validate_depth",
            })

    for skill in [s for s in jd_struct.get("skills_preferred", [])
                  if isinstance(s, str) and s.strip()]:
        if criterion_key(skill) not in seen:
            add({
                "name": skill,
                "category": "soft_skill" if is_soft_skill_text(skill) else "skill",
                "importance": "BONUS",
                "source": "skills_preferred",
                "source_text": skill,
                "question_intent": "validate_depth",
            })

    if len(criteria) < 3:
        for source in ("requirements", "responsibilities"):
            for text in [s for s in jd_struct.get(source, [])
                         if isinstance(s, str) and s.strip()][:6]:
                add({
                    "name": text,
                    "category": "responsibility" if source == "responsibilities" else "experience",
                    "importance": "IMPORTANT",
                    "source": source,
                    "source_text": text,
                    "question_intent": "validate_depth",
                })

    for lang_req in jd_struct.get("languages_required", []):
        if isinstance(lang_req, dict):
            lang_name = lang_req.get("language", "").strip()
            proficiency = lang_req.get("proficiency", "").strip()
            if lang_name:
                name = f"{lang_name} {proficiency}".strip()
                if criterion_key(name) not in seen:
                    add({
                        "name": name,
                        "category": "language",
                        "importance": "CRITICAL",
                        "source": "languages_required",
                        "source_text": name,
                        "question_intent": "verify_gap",
                    })

    return criteria[:30]


# ── Criterion Text & Matching ──────────────────────────────────────────────────────────────────
def criterion_text(criterion: Dict[str, Any]) -> str:
    """Build searchable text for a criterion."""
    parts = [
        criterion.get("name", ""),
        criterion.get("evidence_needed", ""),
        " ".join(coerce_string_list(criterion.get("acceptable_equivalents", []))),
        criterion.get("source_text", ""),
    ]
    return " ".join(str(p) for p in parts if p).strip()


def extract_tech_keywords_from_criterion(text: str) -> List[str]:
    """Extract technical keywords from a long criterion sentence."""
    patterns = [
        r"\b([A-Z][a-z]+(?:[A-Z][a-z]*)+(?:v\d+)?(?:\.\d+)?)\b",
        r"\b([A-Z]{2,}(?:v\d+)?)\b",
        r"\b(python|javascript|typescript|golang|java|rust|ruby|php|scala|c\+\+|c#)\b",
        r"\b(pytorch|tensorflow|keras|sklearn|fastapi|flask|django|react|nodejs)\b",
    ]
    found: List[str] = []
    seen_lower: set = set()
    stopwords = {
        "experience", "proficiency", "knowledge", "ability", "understanding",
        "basic", "advanced", "familiarity", "good", "strong", "excellent",
        "or", "and", "with", "in", "of", "for", "at", "least", "one", "using",
        "such", "as", "like", "including", "related", "frameworks", "techniques",
        "concepts", "tools", "architectures", "libraries", "methods", "skills",
        "programming", "development", "software", "system",
    }
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            word = m.group(1).strip()
            if len(word) >= 2 and word.lower() not in seen_lower:
                if word.lower() not in stopwords:
                    found.append(word)
                    seen_lower.add(word.lower())
    return found


def find_exact_criterion_evidence(
    criterion: Dict[str, Any],
    cv_skill_pool: List[str],
) -> Tuple[str, str]:
    """
    Find exact/equivalent match between criterion and CV skill pool.

    Returns (match_type, matched_skill):
        ("exact_match", skill) — direct match
        ("equivalent_match", skill) — synonym/equivalent match
        ("requires_named", "") — needs named evidence
        ("", "") — no match
    """
    candidates = [criterion.get("name", "")] + coerce_string_list(
        criterion.get("acceptable_equivalents", [])
    )
    cv_norm_map = {normalize_skill_key(skill): skill for skill in cv_skill_pool}

    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        key = normalize_skill_key(candidate)
        if key in cv_norm_map:
            return ("exact_match" if idx == 0 else "equivalent_match"), cv_norm_map[key]

    primary = str(candidates[0] or "")

    def _parse_enumerated_names(s: str) -> List[str]:
        parts = [p.strip() for p in re.split(r",|/|;|\\bor\\b|\\band\\b", s) if p.strip()]
        return [p for p in parts if len(p) >= 2]

    enumerated = _parse_enumerated_names(primary)
    has_named_list = False
    if enumerated and (len(enumerated) > 1 or re.search(r"APIs?|platforms?", primary, re.IGNORECASE)):
        has_named_list = True

    if has_named_list:
        for name in enumerated:
            key = normalize_skill_key(name)
            if key in cv_norm_map:
                return "equivalent_match", cv_norm_map[key]
        return "requires_named", ""

    criterion_name = criterion.get("name", "")
    if isinstance(criterion_name, str) and len(criterion_name.split()) >= 3:
        tech_keywords = extract_tech_keywords_from_criterion(criterion_name)
        for kw in tech_keywords:
            key = normalize_skill_key(kw)
            if key in cv_norm_map:
                return "equivalent_match", cv_norm_map[key]

    return "", ""


def build_match_reason(
    criterion: Dict[str, Any],
    match_status: str,
    evidence: str,
    best_sim: float,
    confidence: float,
    evidence_context: str = "",
) -> str:
    """Generate human-readable explanation for match/mismatch."""
    name = criterion.get("name", "yêu cầu này")
    importance = criterion.get("importance", "IMPORTANT")
    category = str(criterion.get("category", "")).lower()
    source = str(criterion.get("source", "")).lower()

    if match_status == MATCH_PERFECT:
        if evidence_context:
            return (
                f"Tìm thấy '{name}' trong CV. "
                f"Chi tiết (từ CV): {evidence_context}. "
                f"Đây là yêu cầu quan trọng ({importance.lower()}) — đáp ứng đầy đủ."
            )
        elif evidence:
            ev = evidence[:120].strip()
            return (
                f"Tìm thấy '{name}' trong CV "
                f"(bằng chứng: {ev}...). "
                f"Đây là yêu cầu quan trọng ({importance.lower()}) — đáp ứng đầy đủ."
            )
        return f"Yêu cầu '{name}' được tìm thấy trong CV. Đây là yêu cầu ({importance.lower()}) — đáp ứng đầy đủ."

    elif match_status == MATCH_RELEVANT:
        if evidence_context:
            return (
                f"Phát hiện nội dung liên quan '{name}' trong CV. "
                f"Chi tiết (từ CV): {evidence_context}. "
                f"Có thể đáp ứng yêu cầu này ở mức cơ bản."
            )
        if category in {"skill", "technical_skill", "tool"}:
            return (
                f"Không tìm thấy trực tiếp '{name}' trong CV, "
                f"nhưng phát hiện nội dung liên quan "
                f"(similarity={confidence:.0%}, bằng chứng: {evidence[:80] if evidence else 'N/A'}...). "
                f"Có thể đáp ứng yêu cầu này ở mức cơ bản."
            )
        elif category in {"responsibility", "experience"}:
            return (
                f"Phát hiện kinh nghiệm liên quan đến '{name}' trong CV "
                f"(similarity={confidence:.0%}). Có thể đáp ứng yêu cầu này."
            )
        else:
            return (
                f"Nội dung CV có liên quan đến '{name}' "
                f"(similarity={confidence:.0%}). Cần kiểm chứng thêm trong phỏng vấn."
            )

    else:  # MISS_MATCH
        if importance == "CRITICAL":
            return (
                f"Không tìm thấy '{name}' trong CV. "
                f"Đây là yêu cầu BẮT BUỘC — ứng viên cần bổ sung kỹ năng này "
                f"trước khi ứng tuyển."
            )
        elif importance == "IMPORTANT":
            return (
                f"Không tìm thấy '{name}' trong CV. "
                f"Đây là yêu cầu quan trọng — nên bổ sung để tăng cơ hội."
            )
        elif source == "skills_preferred":
            return f"'{name}' không có trong CV (yêu cầu ưu tiên). Không bắt buộc nhưng là điểm cộng nếu có."
        else:
            return f"Không tìm thấy '{name}' trong CV. Có thể bổ sung để cải thiện hồ sơ."


# ── Semantic Matching ──────────────────────────────────────────────────────────────────
def match_criteria_to_cv(
    criteria: List[Dict[str, Any]],
    cv_data: dict,
    embedder: EmbeddingService,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Match JD criteria against CV evidence using semantic embedding.

    Returns: (results, cv_skill_pool)
    """
    cv_skill_pool, cv_evidence = collect_cv_evidence(cv_data)
    if not criteria:
        return [], cv_skill_pool

    criterion_texts = [criterion_text(c) for c in criteria]
    sim_matrix = None
    if cv_evidence and criterion_texts:
        try:
            cv_prefixed = pprefix_batch(cv_evidence, embedder)
            crit_prefixed = qprefix_batch(criterion_texts, embedder)
            all_texts = cv_prefixed + crit_prefixed
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[:len(cv_evidence)]
            criterion_embs = embs[len(cv_evidence):]
            if cv_embs.size and criterion_embs.size:
                sim_matrix = np.dot(cv_embs, criterion_embs.T)
        except Exception as e:
            logger.warning(f"Criteria evidence embedding failed: {e}")

    results: List[Dict[str, Any]] = []

    for j, criterion in enumerate(criteria):
        importance = normalize_importance(criterion.get("importance"))
        raw_status, evidence = find_exact_criterion_evidence(criterion, cv_skill_pool)
        skip_embedding = False

        # Direct match found — PERFECT
        if raw_status in {"exact_match", "equivalent_match"}:
            best_sim = 1.0
            match_status = MATCH_PERFECT

        # Requires named evidence but none found — MISS
        elif raw_status == "requires_named":
            best_sim = 0.0
            match_status = MATCH_MISS
            evidence = ""
            skip_embedding = True

        # No direct match — try semantic
        else:
            best_sim = 0.0
            match_status = MATCH_MISS
            if sim_matrix is not None and not skip_embedding:
                try:
                    category_key = str(criterion.get("category", "")).lower()
                    col_sims = sim_matrix[:, j]

                    if category_key in {"technical_skill", "tool", "skill"}:
                        for idx in np.argsort(col_sims)[::-1]:
                            ev_str = cv_evidence[idx]
                            if (ev_str in cv_data.get("soft_skills", [])
                                    and ev_str not in cv_data.get("technical_skills", [])
                                    and ev_str not in cv_data.get("skills", [])):
                                continue
                            best_idx = idx
                            break
                        else:
                            best_idx = int(col_sims.argmax())
                    elif category_key in {"soft_skill", "culture"}:
                        for idx in np.argsort(col_sims)[::-1]:
                            ev_str = cv_evidence[idx]
                            if (ev_str in cv_data.get("technical_skills", [])
                                    and ev_str not in cv_data.get("soft_skills", [])):
                                continue
                            best_idx = idx
                            break
                        else:
                            best_idx = int(col_sims.argmax())
                    else:
                        best_idx = int(col_sims.argmax())

                    raw_sim = float(np.clip(sim_matrix[best_idx, j], 0.0, 1.0))
                    SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
                    span = max(SIM_MAX - SIM_MIN, 0.05)
                    best_sim = float(np.clip((raw_sim - SIM_MIN) / span, 0.0, 1.0))
                    evidence = cv_evidence[best_idx]

                    perfect_thr = SCORING_CONFIG.PERFECT_MATCH_THRESHOLD
                    relevant_thr = SCORING_CONFIG.RELEVANT_MATCH_THRESHOLD

                    if best_sim >= perfect_thr:
                        match_status = MATCH_PERFECT
                    elif best_sim >= relevant_thr:
                        crit_cat = category_key
                        ev_str = evidence
                        is_lang_crit = crit_cat == "language"
                        is_soft_ev = ev_str in cv_data.get("soft_skills", [])
                        is_lang_ev = any(
                            isinstance(l, dict) and l.get("language", "").lower() in ev_str.lower()
                            for l in cv_data.get("languages", [])
                        )
                        if is_lang_crit and is_soft_ev and not is_lang_ev:
                            match_status = MATCH_MISS
                            evidence = ""
                        elif crit_cat in {"soft_skill", "culture"} and is_lang_ev and not is_soft_ev:
                            match_status = MATCH_MISS
                            evidence = ""
                        else:
                            match_status = MATCH_RELEVANT
                    else:
                        match_status = MATCH_MISS
                        evidence = ""

                except Exception as e:
                    logger.debug(f"Semantic match failed for criterion {j}: {e}")

        score_ratio = _ScoreRatio.get(match_status, 0.0)

        reason_context = ""
        if match_status in {MATCH_PERFECT, MATCH_RELEVANT}:
            skill_ev_dict = {
                normalize_skill_key(se.get("skill", "")): se.get("context", "")
                for se in cv_data.get("skill_evidence", []) if isinstance(se, dict)
            }
            if evidence and normalize_skill_key(evidence) in skill_ev_dict:
                reason_context = skill_ev_dict[normalize_skill_key(evidence)]
            elif normalize_skill_key(criterion.get("name", "")) in skill_ev_dict:
                reason_context = skill_ev_dict[normalize_skill_key(criterion.get("name", ""))]

        reason = build_match_reason(
            criterion, match_status, evidence, best_sim, best_sim, reason_context
        )

        results.append({
            "criterion_id": criterion.get("id", criterion_id(j + 1, criterion.get("name", ""))),
            "requirement": criterion.get("name", ""),
            "category": criterion.get("category", "requirement"),
            "importance": importance,
            "match_status": match_status,
            "score_ratio": score_ratio,
            "confidence": round(best_sim, 4),
            "cv_evidence": evidence,
            "reason": reason,
            "question_intent": criterion.get("question_intent", "validate_depth"),
        })

    return results, cv_skill_pool


# ── Skill Overlap Ratio ──────────────────────────────────────────────────────────────────
def compute_skill_overlap_ratio(
    cv_skills: List[str],
    jd_skills: List[str],
    embedder: EmbeddingService,
    threshold: float = 0.85,
) -> float:
    """Return proportion of JD skills that are truly covered."""
    cv_skills = dedupe_strings(cv_skills)
    jd_skills = dedupe_strings(jd_skills)
    if not jd_skills or not cv_skills:
        return 0.0

    cv_groups = build_skill_groups(cv_skills)
    matched = 0
    unmatched: List[str] = []
    for skill in jd_skills:
        if normalize_skill_key(skill) in cv_groups:
            matched += 1
        else:
            unmatched.append(skill)

    if unmatched:
        try:
            cv_prefixed = pprefix_batch(cv_skills, embedder)
            jd_prefixed = qprefix_batch(unmatched, embedder)
            all_texts = cv_prefixed + jd_prefixed
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[:len(cv_skills)]
            jd_embs = embs[len(cv_skills):]
            if cv_embs.size and jd_embs.size:
                sim_matrix = np.dot(cv_embs, jd_embs.T)
                max_sims = sim_matrix.max(axis=0)
                SIM_MIN, SIM_MAX = get_sim_calibration(embedder)
                span = max(SIM_MAX - SIM_MIN, 0.05)
                raw_threshold = SIM_MIN + threshold * span
                matched += int(np.sum(max_sims >= raw_threshold))
        except Exception as e:
            logger.warning(f"Skill overlap embedding failed: {e}")

    return float(matched / max(len(jd_skills), 1))


# ── Main Skills Scoring ──────────────────────────────────────────────────────────────────
def score_skills(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float,
    cv_embedding: np.ndarray = None,
    jd_embedding: np.ndarray = None,
) -> Tuple[
    float,                    # score
    List[dict],               # perfect_requirements
    List[dict],               # missing_requirements
    float,                    # embedding_similarity
    List[dict],               # relevant_requirements
    Dict[str, Any],           # breakdown
    List[Dict[str, Any]],     # criteria_results
]:
    """
    Score technical skills (0-30).

    Algorithm:
    1. Build JD criteria from parser output
    2. Match each criterion against CV evidence (exact + semantic)
    3. Aggregate weighted coverage
    4. Apply domain penalty caps
    5. Return structured requirement lists

    Returns: (score, perfect_requirements, missing_requirements,
              embedding_sim, relevant_requirements, breakdown, criteria_results)
    """
    criteria = build_jd_criteria(jd_data)
    criteria_results, _ = match_criteria_to_cv(criteria, cv_data, embedder)

    if not criteria:
        return (
            0.0, [], [], 0.0, [],
            {
                "raw_score": 0.0, "coverage_ratio": 0.0, "perfect_score": 0.0,
                "relevant_score": 0.0, "perfect_weight": 0.0, "relevant_weight": 0.0,
                "total_weight": 0.0, "criteria_count": 0,
                "critical_matched": 0, "critical_total": 0,
                "important_matched": 0, "important_total": 0,
                "domain_cap_applied": False,
            },
            [],
        )

    total_weight = sum(criterion_weight(r["importance"]) for r in criteria_results) or 1.0
    perfect_weight = 0.0
    relevant_weight = 0.0
    earned_weight = 0.0

    for result in criteria_results:
        weight = criterion_weight(result["importance"])
        contribution = weight * float(result.get("score_ratio", 0.0))
        earned_weight += contribution
        if result["match_status"] == MATCH_PERFECT:
            perfect_weight += contribution
        elif result["match_status"] == MATCH_RELEVANT:
            relevant_weight += contribution

    coverage_ratio = earned_weight / total_weight
    raw_skills = min(coverage_ratio * 30.0, 30.0)

    # Domain taxonomy caps
    max_skills = SCORING_CONFIG.SKILLS_MAX
    if (domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_SEVERE_PENALTY
            and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_SEVERE_COVERAGE):
        max_skills = SCORING_CONFIG.DOMAIN_CAP_SEVERE
    elif (domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_MODERATE_PENALTY
          and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_MODERATE_COVERAGE):
        max_skills = SCORING_CONFIG.DOMAIN_CAP_MODERATE

    if (domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_PENALTY
            and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_COVERAGE):
        max_skills = min(max_skills, SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_MAX)

    total_score = round(min(raw_skills, max_skills), 2)
    cap_factor = total_score / raw_skills if raw_skills > 0 else 1.0
    perfect_raw = (perfect_weight / total_weight) * raw_skills
    perfect_capped = perfect_raw * cap_factor
    perfect_score = round(min(perfect_capped, total_score), 2)
    relevant_score = round(max(0.0, total_score - perfect_score), 2)

    # ── v2: APPLY SKILLS CONTEXT VALIDATION ──────────────────────────────────────
    # Fix for cases where skills match but context is wrong (e.g., Designer with JS)
    from ._shared import validate_skills_context
    context_mult, context_validations, context_warnings = validate_skills_context(cv_data, jd_data)
    if context_mult < 1.0:
        # Apply context penalty
        total_score = total_score * (0.5 + 0.5 * context_mult)
        perfect_score = perfect_score * (0.5 + 0.5 * context_mult)
        relevant_score = relevant_score * (0.5 + 0.5 * context_mult)
        total_score = round(min(total_score, max_skills), 2)
        perfect_score = round(min(perfect_score, total_score), 2)
        relevant_score = round(max(0.0, total_score - perfect_score), 2)
        logger.info(f"[SKILLS_CONTEXT] Validations: {context_validations}")
        logger.warning(f"[SKILLS_CONTEXT] Warnings: {context_warnings}")

    # Build structured requirement lists
    _EXCLUDED_CATEGORIES = {"education", "degree", "academic", "soft_skill"}

    perfect_requirements = [
        {
            "requirement": r["requirement"],
            "importance": r["importance"],
            "confidence": r["confidence"],
            "reason": r.get("reason", ""),
        }
        for r in criteria_results
        if r["match_status"] == MATCH_PERFECT
        and str(r.get("category", "")).lower() not in _EXCLUDED_CATEGORIES
    ]

    relevant_requirements = [
        {
            "requirement": r["requirement"],
            "importance": r["importance"],
            "confidence": r["confidence"],
            "reason": r.get("reason", ""),
        }
        for r in criteria_results
        if r["match_status"] == MATCH_RELEVANT
        and str(r.get("category", "")).lower() not in _EXCLUDED_CATEGORIES
    ]

    missing_requirements = [
        {
            "requirement": r["requirement"],
            "importance": r["importance"],
            "reason": r.get("reason", ""),
        }
        for r in criteria_results
        if r["match_status"] == MATCH_MISS
        and r["importance"] in {"CRITICAL", "IMPORTANT"}
        and str(r.get("category", "")).lower() not in _EXCLUDED_CATEGORIES
    ]

    # Dedup across buckets
    perfect_requirements = _dedupe_requirements(perfect_requirements)
    relevant_requirements = _dedupe_requirements(
        relevant_requirements, covered_by=perfect_requirements
    )
    missing_requirements = _dedupe_requirements(
        missing_requirements,
        covered_by=perfect_requirements + relevant_requirements,
    )

    # CV-JD embedding similarity for telemetry
    sim = 0.0
    try:
        from ._shared import pprefix, qprefix
        if cv_embedding is not None and jd_embedding is not None:
            cv_emb = cv_embedding
            jd_emb = jd_embedding
        else:
            from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service
            es = get_embedding_service()
            cv_text = es.encode_structured_cv(cv_data)
            jd_text = es.encode_structured_jd(jd_data)
            cv_emb = es.encode(pprefix(cv_text, embedder))
            jd_emb = es.encode(qprefix(jd_text, embedder))
        sim_raw = float(np.dot(cv_emb, jd_emb))
        sim = float(np.clip(sim_raw, 0.0, 1.0))
    except Exception as e:
        logger.warning(f"Embedding failed in skills scoring: {e}")
        sim = 0.0

    critical_total = sum(1 for r in criteria_results if r["importance"] == "CRITICAL")
    critical_matched = sum(
        1 for r in criteria_results
        if r["importance"] == "CRITICAL"
        and r["match_status"] in {MATCH_PERFECT, MATCH_RELEVANT}
    )
    important_total = sum(1 for r in criteria_results if r["importance"] == "IMPORTANT")
    important_matched = sum(
        1 for r in criteria_results
        if r["importance"] == "IMPORTANT"
        and r["match_status"] in {MATCH_PERFECT, MATCH_RELEVANT}
    )

    breakdown = {
        "raw_score": round(raw_skills, 2),
        "coverage_ratio": round(coverage_ratio, 4),
        "perfect_score": perfect_score,
        "relevant_score": relevant_score,
        "perfect_weight": round(perfect_weight, 2),
        "relevant_weight": round(relevant_weight, 2),
        "total_weight": round(total_weight, 2),
        "criteria_count": len(criteria_results),
        "critical_matched": critical_matched,
        "critical_total": critical_total,
        "important_matched": important_matched,
        "important_total": important_total,
        "domain_cap_applied": total_score < round(raw_skills, 2),
        # v2: Skills context validation
        "context_validation": {
            "context_multiplier": context_mult if 'context_mult' in dir() else 1.0,
            "validations": context_validations if 'context_validations' in dir() else [],
            "warnings": context_warnings if 'context_warnings' in dir() else [],
        }
    }

    return (
        total_score,
        perfect_requirements,
        missing_requirements,
        sim,
        relevant_requirements,
        breakdown,
        criteria_results,
    )


def _dedupe_requirements(
    items: List[dict],
    covered_by: List[dict] = None,
) -> List[dict]:
    """Remove semantically duplicate requirements using substring containment."""
    def _norm_req(s: str) -> str:
        return re.sub(r"\s+", "", s.strip().lower())

    covered_norms = []
    if covered_by:
        covered_norms = [_norm_req(r["requirement"]) for r in covered_by]

    seen: list = list(covered_norms)
    deduped: list = []
    for r in items:
        n = _norm_req(r["requirement"])
        if not any(n in s or s in n for s in seen):
            seen.append(n)
            deduped.append(r)
    return deduped
