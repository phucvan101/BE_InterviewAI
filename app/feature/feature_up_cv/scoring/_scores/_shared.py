# -*- coding: utf-8 -*-
"""
Shared utilities, constants, and helpers for all scoring modules.

Centralizes:
- Skill normalization & synonym handling
- E5 prefix helpers
- CV/JD text builders
- Domain penalty computation
- SIM calibration cache
- Scoring constants
|- OVERQUALIFIED DETECTION (v2)
|- CAREER CHANGE DETECTION (v2)
|- EXPERIENCE QUALITY ANALYSIS (v2)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional

import numpy as np

from app.feature.feature_up_cv.core.utils import (
    coerce_string_list as _coerce_string_list,
    criterion_id as _criterion_id,
    criterion_key as _criterion_key,
    normalize_importance as _normalize_importance,
)
# Re-export for convenience
coerce_string_list = _coerce_string_list
normalize_importance = _normalize_importance
criterion_id = _criterion_id
criterion_key = _criterion_key


logger = logging.getLogger(__name__)


# ── Scoring Config ──────────────────────────────────────────────────────────────────
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringConfig:

    EXPERIENCE_WEIGHT: float = 50.0
    SKILLS_WEIGHT: float = 30.0
    EDUCATION_WEIGHT: float = 10.0
    CAREER_WEIGHT: float = 10.0

    PERFECT_MATCH_THRESHOLD: float = 0.80
    RELEVANT_MATCH_THRESHOLD: float = 0.60

    ATOMIC_MATCH_THRESHOLD: float = 0.80
    ATOMIC_RELATED_THRESHOLD: float = 0.60
    GENERIC_MATCH_THRESHOLD: float = 0.80
    GENERIC_RELATED_THRESHOLD: float = 0.60
    SEMANTIC_MATCH_THRESHOLD: float = 0.80
    RELATED_MATCH_THRESHOLD: float = 0.60

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

    UNDERQUALIFIED_CAP: float = 35.0
    SEVERE_GAP_CAP: float = 30.0
    SPECIALIZATION_MISMATCH_CAP: float = 40.0

    RERANK_TOP_K: int = 3
    RERANK_WEIGHT: float = 0.60

    # ── OVERQUALIFIED THRESHOLDS (v2) ────────────────────────────────────────────
    OVERQUALIFIED_SCORE_CAP: float = 75.0  # FIXED: Increased from 70 to 75 for better scoring
    OVERQUALIFIED_EXPERIENCE_RATIO: float = 2.0  # 2x more exp than required
    OVERQUALIFIED_PENALTY: float = 0.15  # FIXED: Reduced from 0.20 to 0.15
    OVERQUALIFIED_ABSOLUTE_CAP: float = 70.0  # FIXED: Increased from 65 to 70

    # ── CAREER CHANGE PENALTIES (v2) ────────────────────────────────────────────
    CAREER_CHANGE_SEVERE_PENALTY: float = 0.70  # Non-tech -> Tech
    CAREER_CHANGE_MODERATE_PENALTY: float = 0.50  # Tech cross-field
    CAREER_CHANGE_MILD_PENALTY: float = 0.20  # Within business domain

    # ── EXPERIENCE QUALITY WEIGHTS (v2) ─────────────────────────────────────────
    EXP_QUALITY_SAME_FIELD: float = 1.0  # Full weight
    EXP_QUALITY_CROSS_FIELD: float = 0.6  # 60% weight for cross-field
    EXP_QUALITY_CAREER_CHANGE: float = 0.3  # 30% weight for career change

    # ── SKILLS CONTEXT PENALTIES (v2) ──────────────────────────────────────────
    SKILLS_FROM_COURSE_PENALTY: float = 0.5  # Skills only from courses
    SKILLS_FROM_PROJECT_PENALTY: float = 0.3  # Skills only from school projects


SCORING_CONFIG = ScoringConfig()

_SIM_MIN_DEFAULT = 0.45
_SIM_MAX_DEFAULT = 0.92


# ── Soft Skill Keys ──────────────────────────────────────────────────────────────────
_SOFT_SKILL_KEYS: Set[str] = {
    "communication", "problemsolving", "projectmanagement", "agile",
    "teamwork", "leadership", "creativity", "adaptability",
}


# ── Domain Anchors ──────────────────────────────────────────────────────────────────
_DOMAIN_ANCHORS: Dict[str, str] = {
    "tech_ai": "AI Machine Learning Deep Learning Computer Vision NLP Neural Network Model Training MLOps",
    "tech_software": "Software Engineer Backend Frontend Fullstack DevOps Software Development API Database Microservice",
    "tech_data": "Data Engineer Data Analyst ETL Data Pipeline Analytics Business Intelligence SQL Data Warehouse",
    "sales": "Sales Business Development Account Management CRM Negotiation Lead Generation Revenue Customer Relationship B2B B2C",
    "marketing": "Digital Marketing SEO SEM Content Marketing Social Media Brand Campaign Advertising Growth",
    "finance": "Finance Accounting Financial Analysis Investment Banking Audit Tax Budgeting CFA Risk Management",
    "hr": "Human Resources Recruitment Talent Acquisition HRBP Training Employee Relations Payroll L&D",
    "operations": "Operations Supply Chain Logistics Procurement Process Improvement Lean Six Sigma Project Management",
}


# ── Seniority Anchors ──────────────────────────────────────────────────────────────────
_SENIORITY_ANCHORS: Dict[int, str] = {
    0: "Internship Fresher entry level no experience trainee beginner intern junior trainee",
    1: "Junior Developer Junior Engineer Entry level with 1-2 years experience junior software engineer",
    2: "Mid-level Developer Software Engineer with 2-5 years experience mid senior independent contributor",
    3: "Senior Developer Senior Engineer Lead with 5+ years experience senior specialist expert technical lead",
    4: "Principal Lead Manager Director Head Chief with 7+ years experience principal architect manager director chief",
}


# ── Project Tech Equivalents ──────────────────────────────────────────────────────────────────
_PROJECT_TECH_EQUIVALENTS: Dict[str, List[str]] = {
    "yolov8": ["yolo"],
    "yolov7": ["yolo"],
    "yolov5": ["yolo"],
    "ultralytics": ["yolo"],
    "opencv": ["opencv"],
    "roboflow": ["roboflow"],
    "labelme": [],
    "cvat": [],
    "labelbox": [],
    "pytorch": ["pytorch"],
    "tensorflow": ["tensorflow"],
    "keras": ["keras"],
    "mxnet": [],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "sklearn": ["scikit-learn", "sklearn"],
    "xgboost": [],
    "lightgbm": [],
    "pandas": [],
    "numpy": [],
    "matplotlib": [],
    "seaborn": [],
    "kaggle": [],
    "huggingface": ["huggingface", "transformers"],
    "transformers": ["transformers", "transformer"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "docker": ["docker"],
    "openai": ["openai"],
    "langchain": ["langchain"],
}


# ── Skill Synonyms Loader ──────────────────────────────────────────────────────────────────
def _load_skill_synonyms() -> Dict[str, List[str]]:
    base = Path(__file__).parent
    pyaml = base / "skill_synonyms.yaml"
    pjson = base / "skill_synonyms.json"
    data = {}
    try:
        if pyaml.exists():
            try:
                import yaml
            except Exception:
                logger.warning("PyYAML not available; falling back to JSON if present.")
            else:
                with pyaml.open("r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
        if not data and pjson.exists():
            with pjson.open("r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        if not isinstance(data, dict):
            return {}
        return {str(k): list(v) for k, v in data.items()}
    except Exception as _e:
        logger.warning("Failed to load skill_synonyms (yaml/json): %s", _e)
        return {}


_SKILL_SYNONYMS: Dict[str, List[str]] = _load_skill_synonyms()


def reload_skill_synonyms() -> Dict[str, List[str]]:
    """Reload skill synonyms after the feedback agent updates the YAML file."""
    global _SKILL_SYNONYMS
    _SKILL_SYNONYMS = _load_skill_synonyms()
    return _SKILL_SYNONYMS


# ── SIM Calibration Cache ──────────────────────────────────────────────────────────────────
_sim_calibration_cache: Dict[str, tuple] = {}

# Cache for domain/seniority embeddings
_domain_anchors_embs: Dict[str, np.ndarray] = {}
_seniority_anchors_embs: Dict[int, np.ndarray] = {}


# ── Skill Normalization ──────────────────────────────────────────────────────────────────
def normalize_skill_key(skill: str) -> str:
    """Normalize skill string to its canonical group key."""
    if not isinstance(skill, str):
        return ""
    s = skill.lower().strip()
    s = re.sub(r"\s+", "", s)
    for group_key, aliases in _SKILL_SYNONYMS.items():
        if s == group_key:
            return group_key
        for alias in aliases:
            alias_norm = re.sub(r"\s+", "", alias.lower().strip())
            if s == alias_norm:
                return group_key
    return s


def build_skill_groups(skills: List[str]) -> set:
    """Build normalized skill groups from a list of skills."""
    return {
        normalize_skill_key(s)
        for s in skills
        if s and isinstance(s, str) and len(s.strip()) >= 2
    }


def skill_group_match(cv_group: set, jd_group: set) -> Tuple[List[str], List[str]]:
    """Return (matched_skills, missing_skills) between CV and JD skill groups."""
    matched = list(cv_group & jd_group)
    missing = list(jd_group - cv_group)
    return matched, missing


# ── E5 Prefix Helpers ──────────────────────────────────────────────────────────────────
def _is_e5_model(embedder) -> bool:
    """True if embedder is using E5 family (needs query/passage prefix)."""
    model_name = str(getattr(embedder, "model_name", "") or "").lower()
    return "e5" in model_name


def qprefix(text: str, embedder) -> str:
    """Query prefix for E5 model."""
    return f"query: {text}" if _is_e5_model(embedder) else text


def pprefix(text: str, embedder) -> str:
    """Passage prefix for E5 model."""
    return f"passage: {text}" if _is_e5_model(embedder) else text


def qprefix_batch(texts: List[str], embedder) -> List[str]:
    """Query prefix for batch."""
    if not _is_e5_model(embedder):
        return texts
    return [f"query: {t}" for t in texts]


def pprefix_batch(texts: List[str], embedder) -> List[str]:
    """Passage prefix for batch."""
    if not _is_e5_model(embedder):
        return texts
    return [f"passage: {t}" for t in texts]


# ── SIM Calibration ──────────────────────────────────────────────────────────────────
def ensure_anchor_embs(embedder) -> None:
    """Pre-compute and cache domain/seniority anchor embeddings with correct prefix."""
    if not _domain_anchors_embs:
        for key, desc in _DOMAIN_ANCHORS.items():
            _domain_anchors_embs[key] = embedder.encode(
                pprefix(desc, embedder), normalize=True
            )
    if not _seniority_anchors_embs:
        for level, desc in _SENIORITY_ANCHORS.items():
            _seniority_anchors_embs[level] = embedder.encode(
                pprefix(desc, embedder), normalize=True
            )


def get_sim_calibration(embedder) -> Tuple[float, float]:
    """
    Return (SIM_MIN, SIM_MAX) calibrated for the current embedding model.

    Results are cached by model_name — only 4 encodings once per application lifecycle.
    """
    _SIM_MIN_DEFAULT = 0.45
    _SIM_MAX_DEFAULT = 0.92
    cache_key = str(getattr(embedder, "model_name", None) or id(embedder))
    if cache_key in _sim_calibration_cache:
        return _sim_calibration_cache[cache_key]

    try:
        _unrelated_a = embedder.encode(pprefix("software engineer python backend", embedder), normalize=True)
        _unrelated_b = embedder.encode(qprefix("chef cooking restaurant food", embedder), normalize=True)
        _identical_a = embedder.encode(pprefix("machine learning engineer AI", embedder), normalize=True)
        _identical_b = embedder.encode(qprefix("machine learning engineer artificial intelligence", embedder), normalize=True)
        sim_low = float(np.clip(np.dot(_unrelated_a, _unrelated_b), 0.0, 1.0))
        sim_high = float(np.clip(np.dot(_identical_a, _identical_b), 0.0, 1.0))
        if sim_high - sim_low > 0.1:
            result = (sim_low, sim_high)
        else:
            result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)
    except Exception:
        result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)

    _sim_calibration_cache[cache_key] = result
    logger.debug("SIM calibration cached for '%s': min=%.3f, max=%.3f", cache_key, result[0], result[1])
    return result


# ── Text Builders ──────────────────────────────────────────────────────────────────
def build_cv_text(cv_data: dict) -> str:
    """Concatenate entire CV content into a single string for domain detection."""
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


def build_jd_text(jd_data: dict) -> str:
    """Concatenate entire JD content into a single string for domain detection."""
    jd_struct = jd_data.get("structured", jd_data)
    parts = [
        jd_data.get("job_title", ""),
        jd_struct.get("job_title", ""),
        jd_struct.get("industry", ""),
        " ".join(jd_struct.get("skills_required", [])),
        " ".join(jd_struct.get("skills_preferred", [])),
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
        " ".join(jd_struct.get("keywords", [])),
        jd_struct.get("career_expectations", ""),
    ]
    return " ".join(p for p in parts if p)


# ── Domain Penalty ──────────────────────────────────────────────────────────────────
def compute_domain_penalty(
    cv_domain: str,
    jd_domain: str,
    skill_overlap: float,
) -> Tuple[float, str]:
    """
    Compute domain penalty based on:
    - Industry domain match/mismatch
    - Skill overlap ratio
    - v2: Enhanced for career change detection

    Returns (penalty_ratio, reason_string).
    penalty_ratio: 0.0 (no penalty) → 1.0 (full penalty).
    """
    _DOMAIN_FAMILY = {
        "tech_ai": "tech",
        "tech_software": "tech",
        "tech_data": "tech",
        "tech_devops": "tech",
        "tech_security": "tech",
        "tech_mobile": "tech",
        "tech_qa": "tech",
        "sales": "business",
        "marketing": "business",
        "finance": "business",
        "hr": "business",
        "operations": "business",
        "healthcare": "business",
        "education": "business",
        "design": "business",
        "management": "business",
    }
    cv_family = _DOMAIN_FAMILY.get(cv_domain, cv_domain)
    jd_family = _DOMAIN_FAMILY.get(jd_domain, jd_domain)

    _TECH_SUBFAMILY = {
        "tech_ai": {"tech_ai"},
        "tech_software": {"tech_software", "tech_backend", "tech_frontend", "tech_fullstack"},
        "tech_data": {"tech_data"},
        "tech_devops": {"tech_devops"},
        "tech_security": {"tech_security"},
        "tech_mobile": {"tech_mobile"},
        "tech_qa": {"tech_qa"},
    }
    cv_sub = _TECH_SUBFAMILY.get(cv_domain, set())
    jd_sub = _TECH_SUBFAMILY.get(jd_domain, set())
    same_tech_sub = bool(cv_sub and jd_sub and cv_sub == jd_sub)

    _BUSINESS_SUBFAMILY = {
        "sales": {"sales"},
        "marketing": {"marketing"},
        "finance": {"finance"},
        "hr": {"hr"},
        "operations": {"operations"},
        "healthcare": {"healthcare"},
        "education": {"education"},
        "design": {"design"},
        "management": {"management"},
    }
    cv_bus = _BUSINESS_SUBFAMILY.get(cv_domain, set())
    jd_bus = _BUSINESS_SUBFAMILY.get(jd_domain, set())
    same_business_sub = bool(cv_bus and jd_bus and cv_bus == jd_bus)

    # ── v2: ENHANCED CAREER CHANGE DETECTION ──────────────────────────────────
    # Special handling for severe career changes
    _NON_TECH_TO_TECH = {
        "sales", "marketing", "finance", "hr", "operations",
        "healthcare", "education", "design", "unknown"
    }

    if cv_domain in _NON_TECH_TO_TECH and jd_domain in _TECH_SUBFAMILY:
        # NON-TECH -> TECH: Severe career change
        if skill_overlap < 0.10:
            return 0.85, f"[CRITICAL] Career change nghiêm trọng: {cv_domain} -> {jd_domain}, skill overlap rất thấp ({skill_overlap:.0%})."
        if skill_overlap < 0.20:
            return 0.75, f"[SEVERE] Career change: {cv_domain} -> {jd_domain}, skill overlap thấp ({skill_overlap:.0%})."
        if skill_overlap < 0.35:
            return 0.60, f"[MODERATE] Career change: {cv_domain} -> {jd_domain}, có một phần skill chung ({skill_overlap:.0%})."
        return 0.40, f"[MILD] Career change: {cv_domain} -> {jd_domain}, có transferable skills ({skill_overlap:.0%})."

    if cv_domain == "unknown" and jd_domain == "unknown":
        return 0.0, "Không đủ dữ liệu để xác định domain; không áp dụng phạt domain."

    if cv_domain == "unknown" or jd_domain == "unknown":
        if skill_overlap >= 0.35:
            return 0.0, f"Một phía thiếu domain nhưng coverage kỹ năng đủ ({skill_overlap:.0%})."
        if skill_overlap >= 0.15:
            return 0.10, f"Một phía thiếu domain, skill overlap trung bình ({skill_overlap:.0%})."
        return 0.20, f"Một phía thiếu domain, skill overlap thấp ({skill_overlap:.0%})."

    if cv_domain == jd_domain:
        return 0.0, "Domain khớp."

    if same_tech_sub:
        return 0.0, "Cùng tech sub-domain."

    if same_business_sub:
        return 0.0, "Cùng business sub-domain."

    if cv_family == jd_family:
        if skill_overlap < 0.15:
            return 0.85, f"Domain tech khác chức năng ({cv_domain} vs {jd_domain}), skill overlap thấp ({skill_overlap:.0%})."
        if skill_overlap < 0.30:
            return 0.70, f"Domain tech khác chức năng ({cv_domain} vs {jd_domain}), skill overlap thấp ({skill_overlap:.0%})."
        return 0.50, f"Domain tech khác chức năng ({cv_domain} vs {jd_domain}), có một phần skill chung ({skill_overlap:.0%})."

    # Cross-family: Tech -> Business or Business -> Tech
    if skill_overlap < 0.1:
        return 0.85, f"Domain hoàn toàn khác ({cv_domain} vs {jd_domain}), skill overlap rất thấp ({skill_overlap:.0%})."
    if skill_overlap < 0.2:
        return 0.70, f"Domain khác nhau ({cv_domain} vs {jd_domain}), skill overlap thấp ({skill_overlap:.0%})."
    return 0.50, f"Domain khác nhau ({cv_domain} vs {jd_domain}), có một phần skill chung ({skill_overlap:.0%})."


# ── Project Tech Expansion ──────────────────────────────────────────────────────────────────
def expand_proj_tech(proj_tech: str) -> List[str]:
    """Expand a project technology to its equivalents + itself."""
    key = proj_tech.lower()
    equivalents = _PROJECT_TECH_EQUIVALENTS.get(key, [key])
    return [e.lower() for e in equivalents]


# ── Helpers ──────────────────────────────────────────────────────────────────
def safe_cap(value: float, cap: float) -> float:
    """Safely cap a numeric value."""
    try:
        return min(float(value), float(cap))
    except Exception:
        return value


def dedupe_strings(items: List[str]) -> List[str]:
    """Remove duplicate strings (case-insensitive)."""
    seen: set = set()
    output: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        clean = item.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def criterion_weight(importance: str) -> float:
    """Return weight multiplier for criterion importance level."""
    return {"CRITICAL": 3.0, "IMPORTANT": 2.0, "BONUS": 1.0}.get(
        _normalize_importance(importance), 2.0
    )


def is_soft_skill_text(skill: str) -> bool:
    """Check if a skill is classified as a soft skill."""
    return normalize_skill_key(skill) in _SOFT_SKILL_KEYS


# ── Expose for backward compat ──────────────────────────────────────────────────────────────────
MATCH_PERFECT = "PERFECT_MATCH"
MATCH_RELEVANT = "RELEVANT_MATCH"
MATCH_MISS = "MISS_MATCH"

_SCORE_RATIO = {
    MATCH_PERFECT: 1.0,
    MATCH_RELEVANT: 0.7,
    MATCH_MISS: 0.0,
}


# ══════════════════════════════════════════════════════════════════════════════
# v2: OVERQUALIFIED DETECTION - Fix loi 90% cases
# ══════════════════════════════════════════════════════════════════════════════

def is_overqualified(
    cv_data: dict,
    jd_data: dict,
    total_work_years: float,
    years_req: float,
) -> Tuple[bool, float, str]:
    """
    Detect if candidate is overqualified for the position.

    Returns: (is_overqualified, severity, reason)

    Severity:
    - 0.0: Not overqualified
    - 0.5: Mildly overqualified (1.5x-2x exp)
    - 1.0: Severely overqualified (2x+ exp)
    """
    if years_req <= 0:
        return False, 0.0, ""

    jd_struct = jd_data.get("structured", jd_data)
    seniority = (jd_struct.get("seniority") or "").lower()

    # JD levels that are sensitive to overqualification
    entry_level_keywords = ["intern", "fresher", "junior", "entry"]
    mid_level_keywords = ["mid", "ii", "trung cấp"]

    is_sensitive_level = any(kw in seniority for kw in entry_level_keywords + mid_level_keywords)

    if not is_sensitive_level:
        return False, 0.0, ""

    exp_ratio = total_work_years / years_req if years_req > 0 else 0

    # Determine severity
    if exp_ratio >= 3.0:
        severity = 1.0
        reason = f"Severely overqualified: {total_work_years:.0f} năm kinh nghiệm (yêu cầu ~{years_req:.0f} năm, ratio={exp_ratio:.1f}x)"
    elif exp_ratio >= 2.0:
        severity = 0.7
        reason = f"Overqualified: {total_work_years:.0f} năm kinh nghiệm (yêu cầu ~{years_req:.0f} năm, ratio={exp_ratio:.1f}x)"
    elif exp_ratio >= 1.5:
        severity = 0.5
        reason = f"Mildly overqualified: {total_work_years:.0f} năm kinh nghiệm (yêu cầu ~{years_req:.0f} năm, ratio={exp_ratio:.1f}x)"
    else:
        return False, 0.0, ""

    return True, severity, reason


def compute_overqualified_penalty(
    is_overqualified: bool,
    severity: float,
    base_score: float,
) -> Tuple[float, str]:
    """
    Compute penalty for overqualified candidates.

    Returns: (adjusted_score, reason)
    """
    if not is_overqualified:
        return base_score, ""

    config = SCORING_CONFIG

    # Progressive penalty based on severity
    if severity >= 1.0:
        # Severe: cap at 65
        capped_score = min(base_score, config.OVERQUALIFIED_ABSOLUTE_CAP)
        penalty = base_score - capped_score
        reason = f"Overqualified penalty: -{penalty:.1f} điểm (capped to {config.OVERQUALIFIED_ABSOLUTE_CAP})"
    elif severity >= 0.7:
        # Significant: cap at 70
        capped_score = min(base_score, config.OVERQUALIFIED_SCORE_CAP)
        penalty = base_score - capped_score
        reason = f"Overqualified penalty: -{penalty:.1f} điểm (capped to {config.OVERQUALIFIED_SCORE_CAP})"
    else:
        # Mild: apply 15% penalty
        penalty_ratio = config.OVERQUALIFIED_PENALTY * severity
        adjusted = base_score * (1 - penalty_ratio)
        capped_score = min(adjusted, config.OVERQUALIFIED_SCORE_CAP + 5)
        reason = f"Overqualified penalty: -{penalty_ratio*100:.0f}% ({severity*100:.0f}% severity)"

    return capped_score, reason


# ══════════════════════════════════════════════════════════════════════════════
# v2: CAREER CHANGE DETECTION - Fix loi 20% cases
# ══════════════════════════════════════════════════════════════════════════════

_CAREER_CHANGE_SEVERE_DOMAINS = {
    "sales", "marketing", "finance", "hr", "operations",
    "healthcare", "education", "design", "unknown"
}

_CAREER_CHANGE_TECH_DOMAINS = {
    "tech_ai", "tech_backend", "tech_frontend", "tech_data",
    "tech_devops", "tech_security", "tech_mobile", "tech_qa"
}


@dataclass
class CareerChangeAnalysis:
    """Result of career change detection."""
    is_career_change: bool
    severity: str  # "none", "mild", "moderate", "severe"
    cv_domain: str
    jd_domain: str
    penalty_ratio: float
    reason: str
    transferable_skills: List[str]
    gaps: List[str]


def analyze_career_change(
    cv_data: dict,
    jd_data: dict,
    skill_overlap: float,
) -> CareerChangeAnalysis:
    """
    Analyze if this is a career change scenario and compute appropriate penalty.

    Returns: CareerChangeAnalysis with severity and penalty ratio.
    """
    cv_domain = cv_data.get("domain", "unknown")
    jd_struct = jd_data.get("structured", jd_data)
    jd_domain = jd_struct.get("domain", "unknown")

    # Determine career change type
    cv_is_non_tech = cv_domain in _CAREER_CHANGE_SEVERE_DOMAINS
    cv_is_tech = cv_domain in _CAREER_CHANGE_TECH_DOMAINS
    jd_is_tech = jd_domain in _CAREER_CHANGE_TECH_DOMAINS

    # Check for career change scenarios
    if cv_is_non_tech and jd_is_tech:
        # NON-TECH -> TECH (Most severe)
        if skill_overlap < 0.15:
            severity = "severe"
            penalty_ratio = SCORING_CONFIG.CAREER_CHANGE_SEVERE_PENALTY
            reason = f"Career change nghiêm trọng: {cv_domain} -> {jd_domain}, skill overlap rất thấp ({skill_overlap:.0%})"
            gaps = ["Không có kinh nghiệm tech thực sự", "Skills chỉ từ khóa học/course", "Domain hoàn toàn khác"]
        elif skill_overlap < 0.30:
            severity = "moderate"
            penalty_ratio = 0.55
            reason = f"Career change vừa: {cv_domain} -> {jd_domain}, skill overlap thấp ({skill_overlap:.0%})"
            gaps = ["Thiếu kinh nghiệm dev chính thức", "Skills từ tự học"]
        else:
            severity = "mild"
            penalty_ratio = 0.30
            reason = f"Career change nhẹ: {cv_domain} -> {jd_domain}, có một phần skill chung ({skill_overlap:.0%})"
            gaps = ["Cần xác minh kinh nghiệm tech"]
        transferable = ["Problem Solving", "Communication", "Leadership", "Project Management"]

    elif cv_is_tech and jd_domain in ["sales", "marketing", "finance", "hr", "management"]:
        # TECH -> BUSINESS (Moderate)
        severity = "moderate"
        penalty_ratio = 0.30
        reason = f"Tech sang business: {cv_domain} -> {jd_domain}"
        gaps = ["Thiếu kinh nghiệm nghiệp vụ chuyên môn"]
        transferable = ["Technical Thinking", "System Design", "Data Analysis"]

    elif cv_is_tech and jd_is_tech and cv_domain != jd_domain:
        # TECH CROSS-FIELD (Mild to Moderate)
        severity = "mild"
        penalty_ratio = 0.15
        reason = f"Tech cross-field: {cv_domain} -> {jd_domain}, có transferable skills"
        gaps = []
        transferable = ["Programming Logic", "System Architecture", "DevOps Practices"]

    else:
        # No significant career change
        severity = "none"
        penalty_ratio = 0.0
        reason = ""
        gaps = []
        transferable = []

    return CareerChangeAnalysis(
        is_career_change=severity != "none",
        severity=severity,
        cv_domain=cv_domain,
        jd_domain=jd_domain,
        penalty_ratio=penalty_ratio,
        reason=reason,
        transferable_skills=transferable,
        gaps=gaps
    )


def compute_career_change_experience_penalty(
    career_change: CareerChangeAnalysis,
    experience_score: float,
    skill_overlap: float,
) -> Tuple[float, str]:
    """
    Compute experience score adjustment for career change.

    Returns: (adjusted_score, reason)
    """
    if not career_change.is_career_change:
        return experience_score, ""

    severity = career_change.severity
    base_penalty = career_change.penalty_ratio

    # Additional penalty based on skill overlap
    if skill_overlap < 0.10:
        # Very low overlap - increase penalty
        adjusted_penalty = min(base_penalty + 0.15, 0.85)
    elif skill_overlap < 0.20:
        adjusted_penalty = base_penalty
    else:
        # Higher overlap - reduce penalty slightly
        adjusted_penalty = base_penalty * 0.8

    adjusted_score = experience_score * (1 - adjusted_penalty)

    # Absolute caps based on severity
    if severity == "severe":
        adjusted_score = min(adjusted_score, 25.0)
    elif severity == "moderate":
        adjusted_score = min(adjusted_score, 35.0)
    else:
        adjusted_score = min(adjusted_score, 45.0)

    reason = f"Career change penalty: -{adjusted_penalty*100:.0f}% ({severity})"

    return adjusted_score, reason


# ══════════════════════════════════════════════════════════════════════════════
# v2: EXPERIENCE QUALITY ANALYSIS - Quality over Quantity
# ══════════════════════════════════════════════════════════════════════════════

_EXP_QUALITY_TECH_KEYWORDS = {
    "developer", "engineer", "programmer", "architect",
    "devops", "sre", "data engineer", "ml engineer", "ai engineer",
    "backend", "frontend", "fullstack", "mobile", "qa", "test"
}

_EXP_QUALITY_CONTEXT_KEYWORDS = {
    # Tech context keywords in work experience
    "production", "deployment", "api", "microservice", "database",
    "pipeline", "infrastructure", "architecture", "performance",
    # Non-tech context (weak evidence)
    "customer", "sales", "marketing", "hr", "accounting",
    "recruitment", "training", "presentation"
}


def analyze_experience_quality(
    cv_data: dict,
    jd_data: dict,
    cv_domain: str,
    jd_domain: str,
) -> Tuple[float, List[str], List[str]]:
    """
    Analyze the quality of experience (not just quantity).

    Returns: (quality_multiplier, quality_indicators, concerns)
    """
    work_experience = cv_data.get("work_experience", [])

    if not work_experience:
        return 0.5, [], ["Không có kinh nghiệm làm việc"]

    quality_indicators = []
    concerns = []

    # 1. Check if job titles contain tech keywords
    tech_title_count = 0
    for exp in work_experience:
        title = exp.get("title", "").lower()
        highlights = " ".join(exp.get("highlights", [])).lower()

        has_tech_title = any(kw in title for kw in _EXP_QUALITY_TECH_KEYWORDS)
        has_tech_context = any(kw in highlights for kw in _EXP_QUALITY_TECH_KEYWORDS)
        has_weak_context = any(kw in highlights for kw in _EXP_QUALITY_CONTEXT_KEYWORDS)

        if has_tech_title:
            tech_title_count += 1
            quality_indicators.append(f"Job title '{title}' chứa keywords tech")

        if has_tech_context and not has_weak_context:
            quality_indicators.append(f"Highlights chứa ngữ cảnh tech: {title}")

        if has_weak_context and not has_tech_context:
            concerns.append(f"Kinh nghiệm ở '{title}' không có ngữ cảnh tech rõ ràng")

    # 2. Check domain alignment of experience
    exp_domains = set()
    for exp in work_experience:
        # Infer domain from title
        title = exp.get("title", "").lower()
        if any(kw in title for kw in ["data", "analytics"]):
            exp_domains.add("tech_data")
        elif any(kw in title for kw in ["frontend", "ui", "ux", "web"]):
            exp_domains.add("tech_frontend")
        elif any(kw in title for kw in ["backend", "server", "api"]):
            exp_domains.add("tech_backend")
        elif any(kw in title for kw in ["devops", "sre", "infrastructure"]):
            exp_domains.add("tech_devops")
        elif any(kw in title for kw in ["ml", "ai", "machine learning"]):
            exp_domains.add("tech_ai")
        elif any(kw in title for kw in ["qa", "test", "quality"]):
            exp_domains.add("tech_qa")
        elif any(kw in title for kw in ["sales", "account", "customer"]):
            exp_domains.add("sales")
        elif any(kw in title for kw in ["market", "campaign", "brand"]):
            exp_domains.add("marketing")

    # 3. Compute quality multiplier
    jd_struct = jd_data.get("structured", jd_data)
    jd_domain_actual = jd_struct.get("domain", "unknown")

    tech_ratio = tech_title_count / max(len(work_experience), 1)

    # Base quality multiplier
    if jd_domain_actual in _CAREER_CHANGE_TECH_DOMAINS:
        # JD is tech role
        if tech_ratio >= 0.8:
            quality_multiplier = 1.0  # Full quality
        elif tech_ratio >= 0.5:
            quality_multiplier = 0.7  # Partial tech
        else:
            quality_multiplier = 0.4  # Mostly non-tech

        if jd_domain_actual not in exp_domains and exp_domains:
            # Experience in different tech subfield
            quality_multiplier *= 0.8

    elif jd_domain_actual in ["sales", "marketing", "finance", "hr", "management"]:
        # JD is business role
        if exp_domains & _CAREER_CHANGE_TECH_DOMAINS:
            # Has tech experience
            quality_multiplier = 0.8
            quality_indicators.append("Có kinh nghiệm tech, có thể transfer sang business")
        else:
            quality_multiplier = 1.0  # Full quality for business role

    else:
        quality_multiplier = 1.0  # Default

    return quality_multiplier, quality_indicators, concerns


# ══════════════════════════════════════════════════════════════════════════════
# v2: SKILLS CONTEXT VALIDATION - Validate skill context
# ══════════════════════════════════════════════════════════════════════════════

_SKILLS_FROM_COURSE_PATTERNS = [
    "khóa học", "course", "training", "online", "certification",
    "học viên", "student", "bootcamp", "self-taught", "tự học"
]

_SKILLS_STRONG_CONTEXT_PATTERNS = [
    "production", "deployed", "implemented", "developed", "built",
    "maintained", "led", "architected", "optimized", "scaled"
]


def validate_skills_context(
    cv_data: dict,
    jd_data: dict,
) -> Tuple[float, List[str], List[str]]:
    """
    Validate if skills are from real work context or just courses/projects.

    Returns: (context_multiplier, validations, warnings)
    """
    validations = []
    warnings = []

    work_experience = cv_data.get("work_experience", [])
    projects = cv_data.get("projects", [])
    # Normalize skills before comparison
    skills = set(normalize_skill_key(s) for s in cv_data.get("skills", []))
    # Remove empty strings
    skills = {s for s in skills if s}

    # 1. Check if skills appear in work experience (with normalization)
    skills_in_work = set()
    for exp in work_experience:
        exp_text = " ".join([
            exp.get("title", ""),
            exp.get("company", ""),
            " ".join(exp.get("highlights", []))
        ]).lower()

        for skill in skills:
            # Check both exact match and partial match for better coverage
            if skill in exp_text:
                skills_in_work.add(skill)

    # 2. Check if skills only from projects/courses
    skills_from_projects = set()
    for proj in projects:
        proj_text = " ".join([
            proj.get("name", ""),
            proj.get("description", ""),
            " ".join(proj.get("technologies", []))
        ]).lower()

        for skill in skills:
            if skill in proj_text:
                skills_from_projects.add(skill)

    # 3. Compute context multiplier
    total_skills = len(skills)
    work_covered = len(skills_in_work)
    project_only = len(skills_from_projects - skills_in_work)

    if total_skills == 0:
        return 0.5, [], ["Không có skills nào"]

    work_ratio = work_covered / total_skills
    project_ratio = project_only / total_skills

    # v2 FIX: Reduced penalties for better accuracy
    # Determine context quality with more lenient thresholds
    if work_ratio >= 0.5:
        # FIXED: Changed from 0.7 to 0.5 for better senior candidate scoring
        context_multiplier = 1.0
        validations.append(f"Skills chủ yếu từ kinh nghiệm làm việc ({work_ratio:.0%})")
    elif work_ratio >= 0.3:
        # FIXED: Changed from 0.4 to 0.3, and penalty from 0.85 to 0.95
        context_multiplier = 0.95
        validations.append(f"Skills một phần từ kinh nghiệm ({work_ratio:.0%})")
        if project_ratio > 0.3:
            warnings.append(f"Một số skills chỉ từ projects ({project_ratio:.0%})")
    else:
        # FIXED: Changed from 0.7 to 0.85 for better scoring
        context_multiplier = 0.85
        warnings.append(f"Nhiều skills có thể chỉ từ khóa học/dự án ({1-work_ratio:.0%} không có trong work experience)")

    return context_multiplier, validations, warnings
