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
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

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

    Returns (penalty_ratio, reason_string).
    penalty_ratio: 0.0 (no penalty) → 1.0 (full penalty).
    """
    _DOMAIN_FAMILY = {
        "tech_ai": "tech",
        "tech_software": "tech",
        "tech_data": "tech",
        "tech_devops": "tech",
        "tech_security": "tech",
        "sales": "business",
        "marketing": "business",
        "finance": "business",
        "hr": "business",
        "operations": "business",
        "healthcare": "business",
        "education": "business",
        "design": "business",
    }
    cv_family = _DOMAIN_FAMILY.get(cv_domain, cv_domain)
    jd_family = _DOMAIN_FAMILY.get(jd_domain, jd_domain)

    _TECH_SUBFAMILY = {
        "tech_ai": {"tech_ai"},
        "tech_software": {"tech_software"},
        "tech_data": {"tech_data"},
        "tech_devops": {"tech_devops"},
        "tech_security": {"tech_security"},
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
    }
    cv_bus = _BUSINESS_SUBFAMILY.get(cv_domain, set())
    jd_bus = _BUSINESS_SUBFAMILY.get(jd_domain, set())
    same_business_sub = bool(cv_bus and jd_bus and cv_bus == jd_bus)

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
            return 0.85, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), skill overlap thap ({skill_overlap:.0%})."
        if skill_overlap < 0.30:
            return 0.70, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), skill overlap thap ({skill_overlap:.0%})."
        return 0.50, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), co mot phan skill chung ({skill_overlap:.0%})."

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
