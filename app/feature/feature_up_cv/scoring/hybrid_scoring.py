# -*- coding: utf-8 -*-
"""
Hybrid CV-JD Scoring Engine — v4.

Changes from v3:
1. Trọng số mới: [50/30/10/10] — kinh nghiệm/kỹ năng/học vấn/mục tiêu nghề nghiệp
2. Thêm career_objectives_score (0-10) — đánh giá phù hợp mục tiêu nghề nghiệp
3. company_fit_score (0-10) tách riêng KHÔNG tính vào tổng 100
4. Tổng = exp(50) + skills(30) + education(10) + career_objectives(10) = 100
"""

import logging
import math
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass

import numpy as np

from app.feature.feature_up_cv.vector_search.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)
from app.feature.feature_up_cv.core.utils import (
    coerce_string_list as _coerce_string_list,
    criterion_id as _criterion_id,
    criterion_key as _criterion_key,
    normalize_importance as _normalize_importance,
)

logger = logging.getLogger(__name__)

from .scoring_config import SCORING_CONFIG, _safe_cap, _build_experience_features
from .scoring_constants import (
    _SOFT_SKILL_KEYS,
    _DOMAIN_ANCHORS,
    _SENIORITY_ANCHORS,
    _PROJECT_TECH_EQUIVALENTS,
)
from .cross_encoder_reranker import CrossEncoderReranker


# ── Skill synonym groups (loaded from external JSON) ─────────────────────────
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


def _normalize_skill_key(skill: str) -> str:
    """Normalize skill string to its canonical group key."""
    if not isinstance(skill, str):
        return ""
    # Bước 1: lowercase + strip
    s = skill.lower().strip()
    # Bước 2: collapse multiple spaces and remove ALL spaces
    # KHÔNG được xóa punctuation vì sẽ làm hỏng "c++", "c#", "node.js", "scikit-learn"
    s = re.sub(r"\s+", "", s)
    
    # Bước 3: lookup synonym group
    for group_key, aliases in _SKILL_SYNONYMS.items():
        if s == group_key:
            return group_key
        for alias in aliases:
            # Chuẩn hóa alias theo đúng cách trên
            alias_norm = re.sub(r"\s+", "", alias.lower().strip())
            if s == alias_norm:
                return group_key
    return s


def _build_skill_groups(skills: List[str]) -> set:
    return {
        _normalize_skill_key(s)
        for s in skills
        if s and isinstance(s, str) and len(s.strip()) >= 2
    }


def _skill_group_match(cv_group: set, jd_group: set) -> Tuple[List[str], List[str]]:
    matched = list(cv_group & jd_group)
    missing = list(jd_group - cv_group)
    return matched, missing


# ── E5 prefix helpers ─────────────────────────────────────────────────────────
# intfloat/multilingual-e5-base yêu cầu prefix để similarity hoạt động đúng:
#   - Text dùng để SEARCH/QUERY → "query: " + text
#   - Text dùng để MATCH AGAINST (corpus/passage) → "passage: " + text
# Nếu không có prefix, model sẽ encode theo chế độ mặc định gây sim bị deflate.
# Hàm này tự detect model qua model_name attribute, fallback safe nếu không phải e5.

def _is_e5_model(embedder) -> bool:
    """True nếu embedder đang dùng E5 family (cần query/passage prefix)."""
    model_name = str(getattr(embedder, "model_name", "") or "").lower()
    return "e5" in model_name

def _qprefix(text: str, embedder) -> str:
    """Query prefix cho E5 model."""
    return f"query: {text}" if _is_e5_model(embedder) else text

def _pprefix(text: str, embedder) -> str:
    """Passage prefix cho E5 model."""
    return f"passage: {text}" if _is_e5_model(embedder) else text

def _qprefix_batch(texts: List[str], embedder) -> List[str]:
    """Query prefix cho batch."""
    if not _is_e5_model(embedder):
        return texts
    return [f"query: {t}" for t in texts]

def _pprefix_batch(texts: List[str], embedder) -> List[str]:
    """Passage prefix cho batch."""
    if not _is_e5_model(embedder):
        return texts
    return [f"passage: {t}" for t in texts]



def _build_cv_text(cv_data: dict) -> str:
    """Gộp toàn bộ nội dung CV thành một chuỗi để detect domain."""
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


def _build_jd_text(jd_data: dict) -> str:
    """Gộp toàn bộ nội dung JD thành một chuỗi để detect domain."""
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


def _compute_domain_penalty(
    cv_domain: str,
    jd_domain: str,
    skill_overlap: float,
) -> Tuple[float, str]:
    """
    Tính domain penalty dựa trên:
    - Industry domain match/mismatch
    - Skill overlap tỷ lệ

    Returns (penalty_ratio, reason_string).
    penalty_ratio: 0.0 (không phạt) → 1.0 (phạt toàn bộ).
    """
    # Nhóm các domain "họ hàng" với nhau
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

    # NEW — sub-family: phân biệt tech sub-domain (AI/Software/Data/DevOps/Security
    # cùng "tech" family nhưng là job functions hoàn toàn khác nhau.
    # Backend engineer vs AI engineer là MISMATCH dù cùng "tech".
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

    # business sub-family: phân biệt HR/Sales/Marketing/Finance/Operations
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
        # Cùng domain: không phạt
        return 0.0, "Domain khớp."

    # NEW: cùng tech sub-family → coi như cùng domain (không phạt)
    if same_tech_sub:
        return 0.0, "Cùng tech sub-domain."

    # NEW: cùng business sub-family → coi như cùng domain (không phạt)
    if same_business_sub:
        return 0.0, "Cùng business sub-domain."

    if cv_family == jd_family:
        # Cùng họ nhưng khác sub-family (vd: tech_ai vs tech_software)
        # = hoàn toàn khác job function → phạt nặng
        if skill_overlap < 0.15:
            return 0.85, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), skill overlap thap ({skill_overlap:.0%})."
        if skill_overlap < 0.30:
            return 0.70, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), skill overlap thap ({skill_overlap:.0%})."
        return 0.50, f"Domain tech khac chuc nang ({cv_domain} vs {jd_domain}), co mot phan skill chung ({skill_overlap:.0%})."

    # Khác họ hoàn toàn (vd: tech vs business)
    if skill_overlap < 0.1:
        return 0.85, f"Domain hoàn toàn khác ({cv_domain} vs {jd_domain}), skill overlap rất thấp ({skill_overlap:.0%})."
    if skill_overlap < 0.2:
        return 0.70, f"Domain khác nhau ({cv_domain} vs {jd_domain}), skill overlap thấp ({skill_overlap:.0%})."
    return 0.50, f"Domain khác nhau ({cv_domain} vs {jd_domain}), có một phần skill chung ({skill_overlap:.0%})."


# ── Experience Scoring (0-50) ─────────────────────────────────────────────────
def _score_experience(
    cv_data: dict,
    jd_data: dict,
    cv_domain: str,
    jd_domain: str,
    skill_overlap: float,
    embedder: EmbeddingService,
) -> Tuple[float, str, Dict[str, Any]]:
    jd_struct = jd_data.get("structured", jd_data)

    # 0. JD yêu cầu bao nhiêu năm kinh nghiệm
    seniority_req = (jd_struct.get("seniority") or "").lower()
    seniority_parts = [p.strip().lower() for p in seniority_req.split("/")]
    seniority_level_map = {
        "intern": 0, "fresher": 0, "junior": 1,
        "mid": 2, "mid-level": 2, "senior": 3,
        "lead": 4, "principal": 4, "expert": 4, "manager": 4,
    }
    # "Junior/Fresher" nghĩa là JD chấp nhận cả hai → lấy min() để inclusive
    # max() sẽ lấy Junior=1, bỏ qua Fresher=0 → is_entry_level luôn False
    req_level = min(
        (seniority_level_map.get(p, 2) for p in seniority_parts),
        default=2,
    )

    years_req_map = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    years_req_raw = jd_struct.get("years_of_experience", "")
    if years_req_raw:
        numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(years_req_raw))]
        # BUG 1 FIX: JD "2-4 years" nghĩa là chấp nhận từ 2 năm trở lên → lấy min,
        # không phải max (4 năm). Lấy max sẽ làm CV 2-3 năm bị thiếu điểm sai.
        years_req = min(numbers) if numbers else years_req_map.get(req_level, 2.0)
    else:
        years_req = years_req_map.get(req_level, 2.0)

    # 1. Kinh nghiệm làm việc thực tế
    total_work_years = 0.0
    exp_titles: List[str] = []
    for exp in cv_data.get("work_experience", []):
        start = exp.get("start") or exp.get("start_date") or ""
        end = exp.get("end") or exp.get("end_date") or ""
        if isinstance(exp.get("years"), str) and " - " in exp.get("years", ""):
            parts = exp["years"].split(" - ")
            start, end = parts[0], parts[-1]
        total_work_years += _parse_years(start, end)
        if t := exp.get("title"):
            exp_titles.append(t.lower())

    # ── Detect intern/fresher mode ────────────────────────────────────────────
    # JD Intern/Fresher/Junior: project cá nhân là primary evidence, không phải secondary.
    # req_level <= 1 bao gồm: intern(0), fresher(0), junior(1)
    # years_req thường 0-2 → không penalize nặng khi CV chỉ có project.
    is_entry_level = req_level <= 1

    # 2. Project years — SEMANTIC MATCHING: dùng embedding thay keyword matching
    # proj_dur mặc định: intern/fresher dùng 0.5y (6 tháng) vì project là bằng chứng chính;
    # mid+ dùng 0.25y (3 tháng) vì work experience mới là primary.
    default_proj_dur = 0.5 if is_entry_level else 0.25
    project_years, project_relevance_scores, project_descriptions = \
        _semantic_project_relevance(
            cv_data.get("projects", []),
            jd_data,
            "",  # unused: responsibilities text built internally from jd_data
            embedder,
            default_proj_dur,
        )

    all_exp_years = total_work_years + project_years

    # 3. Years score (0-40)
    # Intern/Fresher: years_req thường = 1 hoặc 0.
    # Khi years_req = 0 (pure intern), mọi CV có project đều đủ điều kiện → cho điểm tối đa.
    # Khi years_req = 1, project 6 tháng × relevance 0.6 ≈ 0.5 năm → ratio 0.5 → vẫn hợp lý.
    if is_entry_level and years_req == 0:
        # JD không yêu cầu năm kinh nghiệm → đánh giá qua project relevance thực tế.
        # KHÔNG cho flat 40.0 bất kể relevance — tránh trường hợp CV thuần CV
        # apply JD NLP vẫn được experience_score cao do project_years > 0 (relevance 11%).
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        has_any_project = len(cv_data.get("projects", [])) > 0

        if total_work_years > 0:
            # FIX 15C: For SEVERE domain mismatch (skill_overlap < 0.1),
            # having unrelated work experience (e.g., Barista) should NOT give 35/40.
            # A Literature student's barista job is completely irrelevant to IT backend.
            if skill_overlap < 0.1:
                # Severely mismatched domain — work experience doesn't count
                years_score = 5.0
            else:
                years_score = 35.0
        elif avg_rel >= 0.55:
            # Project rất relevant → full score
            years_score = 40.0
        elif avg_rel >= 0.20:
            # Project có liên quan → scale tuyến tính 15→40 theo relevance
            years_score = 15.0 + (avg_rel - 0.20) / 0.35 * 25.0
        elif has_any_project and avg_rel > 0:
            # Có project nhưng relevance thấp < 25% → 10–15đ
            years_score = 10.0 + avg_rel / 0.25 * 5.0
        elif has_any_project:
            # Có project nhưng relevance = 0 (domain hoàn toàn lệch)
            years_score = 8.0
        else:
            years_score = 5.0  # Không có gì
    elif years_req > 0:
        ratio = min(all_exp_years / years_req, 2.0)
        # BUG 8a FIX: Scale years_score proportionally when CV is underqualified
        # Before: min(40*ratio, 40) — when ratio=0.875 (3.5y exp / 4y req),
        #   raw_years_score=35/40 = 87.5% — too generous for an underqualified CV.
        # After: cap at years_req/years_req = 1.0 when ratio < 1.0 (underqualified)
        #   ratio=0.875 → raw_years_score = 35 (proportional to the gap)
        #   But we also need to respect the gap: CV with 87.5% of required years
        #   should NOT get 87.5% of the 40 pts for years. Cap years_score component
        #   so that underqualified CVs can't reach 35/40.
        # Fix: apply a gap multiplier when ratio < 1.0 to further penalize the gap.
        #   years_ratio_score = min(40 * ratio, 40) is kept as-is for overqualified cases.
        #   For underqualified: scale down by ratio itself to avoid over-rewarding partial exp.
        if all_exp_years < years_req:
            # Underqualified: scale years_score down by (all_exp_years / years_req)
            # This means a CV with 3.5y exp for a 4y req gets (3.5/4)^2 * 40 = 76.6% of 40 = 30.6
            gap_ratio = all_exp_years / years_req
            raw_years_score = min(40.0 * gap_ratio * gap_ratio, 40.0)
        else:
            raw_years_score = min(40.0 * ratio, 40.0)
        # BUG 2 FIX: Overqualified penalty cho experience khi JD là Intern/Fresher
        # CV có kinh nghiệm >> yêu cầu sẽ bị trừ nhẹ (tối đa -8 điểm) vì khả năng
        # ứng viên không gắn bó lâu dài hoặc mức lương không phù hợp.
        if is_entry_level and all_exp_years > 0 and years_req >= 0:
            # Chỉ phạt khi CV có > 2x năm kinh nghiệm so với yêu cầu tối đa
            # (ví dụ JD Fresher, CV 5 năm → overqualified rõ ràng)
            years_req_max_raw = jd_struct.get("years_of_experience", "")
            max_numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(years_req_max_raw))]
            years_req_upper = max(max_numbers) if max_numbers else (years_req + 1.0)
            if all_exp_years > years_req_upper * 2.0:
                overqualified_penalty = min(8.0, (all_exp_years - years_req_upper * 2.0) * 2.0)
                raw_years_score = max(raw_years_score - overqualified_penalty, 20.0)
        years_score = raw_years_score
    else:
        years_score = min(all_exp_years * 20.0, 40.0)

    # 4. Domain penalty
    domain_penalty, penalty_reason = _compute_domain_penalty(cv_domain, jd_domain, skill_overlap)

    # 5. Seniority score (0-10)
    cv_level = _semantic_seniority_detection(
        exp_titles, project_descriptions, embedder
    )

    # BUG 13 FIX: For intern/fresher JDs, seniority should be proportional to work years vs requirement.
    # OLD: if total_work_years > 0 → seniority = 10.0 (too generous for even 1y freelance)
    # NEW: Scale seniority by (actual_work_years / years_req) for intern JDs.
    seniority_base = 0.0
    if domain_penalty >= 0.7:
        seniority_base = 0.0
    elif is_entry_level:
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        if total_work_years > 0:
            # Scale by work years vs JD requirement to avoid giving 10/10 for any work experience
            # For "0-2 years" JD: years_req=0 → fall through to project-based scoring
            # For "1-3 years" JD: years_req=1 → partial credit based on years ratio
            if years_req > 0:
                # Scale seniority: years_actual / years_req gives 0-1 ratio, cap at 10
                years_ratio = min(total_work_years / years_req, 1.5)
                seniority_base = round(min(years_ratio * 10.0, 10.0), 1)
            else:
                seniority_base = 10.0
        elif avg_rel >= 0.70:
            seniority_base = 7.0
        elif avg_rel >= 0.45:
            seniority_base = 5.0
        elif avg_rel >= 0.25:
            seniority_base = 3.0
        else:
            seniority_base = 1.0
    elif cv_level >= req_level:
        seniority_base = 10.0
    elif cv_level == req_level - 1:
        seniority_base = 5.0
    elif cv_level > 0:
        seniority_base = 2.0
    else:
        seniority_base = 0.0

    # Apply level-ratio scaling when CV is below required level (within same domain)
    # This penalizes e.g. Junior CV (level 1) applying for Senior JD (level 3) even
    # when domain is the same and domain_penalty = 0.
    if domain_penalty < 0.7 and req_level > 0 and cv_level < req_level and cv_level > 0:
        level_ratio = cv_level / req_level
        seniority_score = round(min(seniority_base * level_ratio, 10.0), 1)
    else:
        seniority_score = seniority_base

    # NEW: Severe seniority gap — hard cap
    # AI/NLP 2y → Senior AI/CV JD (4-7y): gap >= 2 levels → seniority capped at 2.0
    # HR 4y → BDR (entry): gap >= 3 levels → seniority = 0
    if domain_penalty < 0.7 and req_level > 0 and cv_level < req_level:
        level_gap = req_level - cv_level
        if level_gap >= 3:
            seniority_score = 0.0
        elif level_gap >= 2:
            seniority_score = min(seniority_score, 2.0)

    # 6. Bonus — chỉ cộng khi domain gần nhau
    bonus = 0.0
    if domain_penalty < 0.4:
        if total_work_years > 0 and project_years > 0:
            bonus += 8.0
        elif project_years > 0:
            avg_rel = (
                sum(project_relevance_scores) / len(project_relevance_scores)
                if project_relevance_scores else 0.0
            )
            rel_threshold_high = 0.55 if is_entry_level else 0.65
            rel_threshold_mid = 0.35 if is_entry_level else 0.50
            if avg_rel >= rel_threshold_high:
                bonus += 5.0
            elif avg_rel >= rel_threshold_mid:
                bonus += 3.0

    # FIX: Intern JD bonus cap — years_req <= 1 năm means no one deserves full 50/50
    # Với JD intern/fresher (years_req <= 1), max possible raw = 40+10+5 = 55
    # Cap raw ở 42 (roughly 85% của max) để tránh CV 1 năm exp đạt 50/50
    if is_entry_level and years_req <= 1.0:
        bonus = min(bonus, 3.0)

    raw_total = years_score + seniority_score + bonus

    # NEW: Domain-mismatch experience penalty
    # Backend 2y apply AI NLP JD: work experience không đếm khi domain hoàn toàn khác
    # Chỉ áp dụng khi domain_penalty >= 0.5 (tức tech_ai vs tech_software,
    # hoặc business vs tech)
    if domain_penalty >= 0.5 and total_work_years > 0 and skill_overlap < 0.10:
        # Kiểm tra domain của work experience có match JD không
        # Nếu work domain (từ title/company) hoàn toàn khác JD domain
        # → giảm years_score đáng kể
        years_score = years_score * 0.65  # penalty 50% cho work years không liên quan

    # FIX 11: Cap seniority directly when years gap is severe
    # When CV has less than 50% of required years (not intern JD), seniority should be
    # further penalized regardless of cv_level detection. A 1.5-year CV for a 4-year
    # Senior JD has years_gap_ratio=0.375 — even cv_level detection might give mid-level
    # credit that doesn't reflect the actual gap. Cap seniority at years_gap_ratio.
    if (not is_entry_level and
            years_req > 0 and
            all_exp_years <= years_req * 0.5):
        years_gap_ratio = all_exp_years / years_req
        seniority_score = round(min(seniority_score * years_gap_ratio, 10.0), 1)

    # FIX 11 (hard cap): Severe underqualification → cap raw at 30/50 (60% of max)
    # Threshold 0.86: when CV has ≤86% of JD minimum required years (same domain),
    # cap experience score. This prevents same-domain CVs with significant experience gap
    # from scoring too high just because domain matches.
    #   - pair_04: 3.42y exp for "4-7y" JD → years_req=4.0 (min), ratio=0.855
    #     0.855 ≤ 0.86 → cap triggers → exp ~30 → total ~60
    #   - pair_09: 2y finance exp for "1-3y" data JD → years_req=1.0 (min), ratio=2.0
    #     2.0 > 0.86 → cap NOT triggered → exp stays at 25 (correct)
    if (not is_entry_level and
            years_req > 0 and
            all_exp_years > 0 and
            all_exp_years <= years_req * 0.86 and
            domain_penalty < 0.7):
        raw_total = _safe_cap(raw_total, SCORING_CONFIG.UNDERQUALIFIED_CAP)

    # NEW: Aggressive cap for large seniority gap (>= 2 years short)
    # AI/NLP 2y -> Senior AI/CV JD (4y min): gap = 2y, ratio = 0.5 -> cap at 25
    if (not is_entry_level and
            years_req > 0 and
            all_exp_years > 0 and
            years_req - all_exp_years >= 2.0):
        raw_total = _safe_cap(raw_total, SCORING_CONFIG.SEVERE_GAP_CAP)

    # NEW: Same-domain specialization mismatch cap
    # tech_ai CV (NLP) vs tech_ai JD (CV): same domain but different specialization
    # skill_overlap < 0.40 signals wrong specialization within same domain
    # Apply to non-severe-domain-penalty cases where coverage is suspiciously low
    if (domain_penalty < 0.4 and
            skill_overlap < 0.40 and
            not is_entry_level and
            years_req > 0 and
            all_exp_years > 0):
        # Cap raw at 35 to reflect: same-domain spirit but wrong specialization
        raw_total = _safe_cap(raw_total, SCORING_CONFIG.SPECIALIZATION_MISMATCH_CAP)

    total_exp = round(min(raw_total * (1.0 - domain_penalty), 50.0), 2)

    # Build experience features for downstream use / debugging
    try:
        features = _build_experience_features(
            all_exp_years, years_req, skill_overlap, domain_penalty, int(req_level - cv_level)
        )
        # Attach per-project debug info so callers can inspect relevance per project
        try:
            features["project_relevance_scores"] = project_relevance_scores
            features["project_descriptions"] = project_descriptions
            features["project_years"] = project_years
        except Exception:
            # non-fatal: keep base features if project details missing
            pass
        logger.debug("Experience features: %s", features)
    except Exception:
        features = {}

    # 7. Rationale
    if domain_penalty >= 0.7:
        rationale = (
            f"Domain không phù hợp ({cv_domain} vs {jd_domain}). "
            f"Kinh nghiệm bị giảm mạnh ({int(domain_penalty*100)}% penalty). "
            f"{penalty_reason}"
        )
    elif domain_penalty >= 0.4:
        rationale = (
            f"Domain lệch một phần ({cv_domain} vs {jd_domain}). "
            f"Kinh nghiệm bị giảm {int(domain_penalty*100)}%. "
            f"{penalty_reason}"
        )
    elif domain_penalty > 0:
        rationale = f"Domain gần nhau, penalty nhẹ {int(domain_penalty*100)}%. {penalty_reason}"
    elif is_entry_level and project_years > 0:
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        rationale = (
            f"JD Intern/Fresher — dự án cá nhân là bằng chứng chính "
            f"(relevance trung bình: {avg_rel:.0%})."
        )
    elif seniority_score >= 10:
        rationale = "Kinh nghiệm và cấp độ đạt yêu cầu."
    elif seniority_score >= 5:
        rationale = "Kinh nghiệm gần đạt yêu cầu."
    elif total_work_years > 0 or project_years > 0:
        rationale = "Kinh nghiệm thấp hơn yêu cầu (fresh grad / dự án cá nhân)."
    else:
        rationale = "Chưa có kinh nghiệm làm việc hoặc dự án liên quan."

    return total_exp, rationale, features


def _build_experience_detail(cv_data: dict) -> str:
    work = cv_data.get("work_experience", [])
    projects = cv_data.get("projects", [])
    parts = []
    if work:
        work_parts = []
        for e in work:
            if e.get("title"):
                period = e.get("years") or (e.get("start", "") + "-" + e.get("end", ""))
                work_parts.append(f"{e['title']} ({period})")
        if work_parts:
            parts.append("Work: [" + ", ".join(work_parts) + "]")
    if projects:
        proj_parts = [p.get("name", "N/A") for p in projects if p.get("name")]
        if proj_parts:
            parts.append("Projects: [" + ", ".join(proj_parts) + "]")
    return ". ".join(parts) + "." if parts else "Chưa có kinh nghiệm làm việc hoặc dự án cá nhân."


def _parse_years(start: str, end: str) -> float:
    try:
        import datetime
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
                    # Year-only format (e.g. "2022"): interpret as END of year (December)
                    # because most CVs list work years by calendar year, and "2022"
                    # in a resume typically means "some time in 2022" ending by Dec 2022.
                    # This is more conservative than defaulting to January.
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


def _dedupe_strings(items: List[str]) -> List[str]:
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


# _criterion_key, _coerce_string_list, _normalize_importance, _criterion_id
# are now imported from app.feature.feature_up_cv.core.utils


def _criterion_weight(importance: str) -> float:
    return {"CRITICAL": 3.0, "IMPORTANT": 2.0, "BONUS": 1.0}.get(
        _normalize_importance(importance), 2.0
    )


def _is_soft_skill_text(skill: str) -> bool:
    return _normalize_skill_key(skill) in _SOFT_SKILL_KEYS


def _build_jd_criteria(jd_data: dict) -> List[Dict[str, Any]]:
    """Use parser-provided criteria when available, then backfill legacy JD fields."""
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
        key = _criterion_key(name)
        if not key or key in seen:
            return
        seen.add(key)
        idx = len(criteria) + 1
        criteria.append({
            "id": str(item.get("id") or _criterion_id(idx, name)),
            "name": name,
            "category": str(item.get("category") or "requirement").strip() or "requirement",
            "importance": _normalize_importance(item.get("importance")),
            "evidence_needed": str(item.get("evidence_needed") or f"CV cần có bằng chứng đáp ứng: {name}.").strip(),
            "acceptable_equivalents": _coerce_string_list(item.get("acceptable_equivalents", [])),
            "source": str(item.get("source") or "").strip(),
            "source_text": str(item.get("source_text") or "").strip(),
            "question_intent": str(item.get("question_intent") or "validate_depth").strip() or "validate_depth",
        })

    for item in jd_struct.get("evaluation_criteria", []):
        add(item)

    for skill in [s for s in jd_struct.get("skills_required", []) if isinstance(s, str) and s.strip()]:
        if _criterion_key(skill) not in seen:
            add({
                "name": skill,
                "category": "soft_skill" if _is_soft_skill_text(skill) else "skill",
                "importance": skill_importance.get(skill, "IMPORTANT"),
                "source": "skills_required",
                "source_text": skill,
                "question_intent": "validate_depth",
            })

    for skill in [s for s in jd_struct.get("skills_preferred", []) if isinstance(s, str) and s.strip()]:
        if _criterion_key(skill) not in seen:
            add({
                "name": skill,
                "category": "soft_skill" if _is_soft_skill_text(skill) else "skill",
                "importance": "BONUS",
                "source": "skills_preferred",
                "source_text": skill,
                "question_intent": "validate_depth",
            })

    if len(criteria) < 3:
        for source in ("requirements", "responsibilities"):
            for text in [s for s in jd_struct.get(source, []) if isinstance(s, str) and s.strip()][:6]:
                add({
                    "name": text,
                    "category": "responsibility" if source == "responsibilities" else "experience",
                    "importance": "IMPORTANT",
                    "source": source,
                    "source_text": text,
                    "question_intent": "validate_depth",
                })

    return criteria[:30]


def _collect_cv_evidence(cv_data: dict) -> Tuple[List[str], List[str]]:
    """Collect general CV evidence without assuming a fixed industry taxonomy."""
    explicit_soft = {
        _normalize_skill_key(s)
        for s in cv_data.get("soft_skills", [])
        if isinstance(s, str) and s.strip()
    }

    skill_pool: List[str] = []
    for key in ("technical_skills", "domain_skills"):
        skill_pool.extend(s for s in cv_data.get(key, []) if isinstance(s, str))
    for s in cv_data.get("skills", []):
        if isinstance(s, str) and _normalize_skill_key(s) not in explicit_soft:
            skill_pool.append(s)
    for proj in cv_data.get("projects", []):
        skill_pool.extend(_coerce_string_list(proj.get("technologies", [])))
    for cert in cv_data.get("certifications", []):
        if isinstance(cert, str):
            skill_pool.append(cert)
        elif isinstance(cert, dict):
            skill_pool.append(" ".join(str(v) for v in cert.values() if v))

    evidence: List[str] = []
    evidence.extend(skill_pool)
    evidence.extend(s for s in cv_data.get("soft_skills", []) if isinstance(s, str))
    if cv_data.get("career_objectives"):
        evidence.append(str(cv_data.get("career_objectives")))
    if cv_data.get("objective"):
        evidence.append(str(cv_data.get("objective")))

    for exp in cv_data.get("work_experience", []):
        parts = [
            exp.get("title", ""),
            exp.get("company", ""),
            exp.get("description", ""),
        ]
        evidence.append(" ".join(str(p) for p in parts if p))
        for key in ("highlights", "responsibilities", "achievements"):
            evidence.extend(_coerce_string_list(exp.get(key, [])))

    for proj in cv_data.get("projects", []):
        parts = [
            proj.get("name", ""),
            proj.get("role", ""),
            proj.get("description", ""),
            " ".join(_coerce_string_list(proj.get("technologies", []))),
        ]
        evidence.append(" ".join(str(p) for p in parts if p))
        for key in ("highlights", "responsibilities"):
            evidence.extend(_coerce_string_list(proj.get(key, [])))

    for edu in cv_data.get("education", []):
        parts = [
            edu.get("degree", ""),
            edu.get("major", ""),
            edu.get("school", ""),
            edu.get("description", ""),
            edu.get("details", ""),
        ]
        evidence.append(" ".join(str(p) for p in parts if p))

    return _dedupe_strings(skill_pool), _dedupe_strings([e[:700] for e in evidence])


def _criterion_text(criterion: Dict[str, Any]) -> str:
    parts = [
        criterion.get("name", ""),
        criterion.get("evidence_needed", ""),
        " ".join(_coerce_string_list(criterion.get("acceptable_equivalents", []))),
        criterion.get("source_text", ""),
    ]
    return " ".join(str(p) for p in parts if p).strip()


def _extract_tech_keywords_from_criterion(text: str) -> List[str]:
    """
    Trích xuất các technical keyword ngắn từ criteria dạng câu dài.

    Ví dụ:
      "Proficiency in Python programming" → ["Python"]
      "Experience with PyTorch or TensorFlow frameworks" → ["PyTorch", "TensorFlow"]
      "Basic understanding of CNN, Transformer, YOLO architectures" → ["CNN", "Transformer", "YOLO"]

    Mục đích: khi criteria là câu mô tả dài, normalize toàn bộ câu sẽ không match
    với từng skill ngắn trong skill pool. Tách keyword ngắn ra để match riêng.
    """
    # Pattern 1: Tên công nghệ/framework viết hoa hoặc mixed-case dài >= 2 ký tự
    # Ưu tiên match các từ như PyTorch, TensorFlow, YOLO, CNN, OpenCV, Python...
    patterns = [
        # Chuỗi như "PyTorch", "TensorFlow", "OpenCV", "YOLOv8" — PascalCase/MixedCase
        r"\b([A-Z][a-z]+(?:[A-Z][a-z]*)+(?:v\d+)?(?:\.\d+)?)\b",
        # Chuỗi ALL CAPS dài >= 2: "CNN", "YOLO", "OCR", "NLP", "API"
        r"\b([A-Z]{2,}(?:v\d+)?)\b",
        # Ngôn ngữ lowercase phổ biến
        r"\b(python|javascript|typescript|golang|java|rust|ruby|php|scala|c\+\+|c#)\b",
        # Framework phổ biến lowercase
        r"\b(pytorch|tensorflow|keras|sklearn|fastapi|flask|django|react|nodejs)\b",
    ]
    found: List[str] = []
    seen_lower: set = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            word = m.group(1).strip()
            if len(word) >= 2 and word.lower() not in seen_lower:
                # Bỏ qua các stopwords dạng viết hoa đầu câu
                if word.lower() not in {
                    "experience", "proficiency", "knowledge", "ability",
                    "understanding", "basic", "advanced", "familiarity",
                    "good", "strong", "excellent", "or", "and", "with",
                    "in", "of", "for", "at", "least", "one", "using",
                    "such", "as", "like", "including", "related",
                    "frameworks", "techniques", "concepts", "tools",
                    "architectures", "libraries", "methods", "skills",
                    "programming", "development", "software", "system",
                }:
                    found.append(word)
                    seen_lower.add(word.lower())
    return found


def _find_exact_criterion_evidence(
    criterion: Dict[str, Any],
    cv_skill_pool: List[str],
) -> Tuple[str, str]:
    """
    Tìm exact/equivalent match giữa criterion và CV skill pool.

    Chiến lược 2 bước:
    1. Match trực tiếp: normalize toàn bộ criterion name → so với skill pool.
    2. Keyword extraction: nếu criterion là câu dài (>= 3 từ), tách keywords
       ngắn từ câu → match từng keyword với skill pool. Nếu tìm được, trả về
       "equivalent_match" (vì là partial match, không phải exact).
    """
    candidates = [criterion.get("name", "")] + _coerce_string_list(
        criterion.get("acceptable_equivalents", [])
    )
    cv_norm_map = {_normalize_skill_key(skill): skill for skill in cv_skill_pool}

    # Bước 1: Match trực tiếp (giữ nguyên hành vi cũ)
    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        key = _normalize_skill_key(candidate)
        if key in cv_norm_map:
            return ("exact_match" if idx == 0 else "equivalent_match"), cv_norm_map[key]

    # Bước 2: Keyword extraction cho criteria dạng câu dài
    # Chỉ áp dụng khi criterion name có >= 3 từ (tức là câu mô tả, không phải tên kỹ năng đơn)
    criterion_name = criterion.get("name", "")
    # Special-case: if criterion explicitly lists named platforms/APIs (comma-separated
    # or contains words like 'APIs'/'platforms' and proper names), require explicit
    # presence of one of those names in the CV instead of falling back to generic
    # semantic matching. This prevents a generic 'LLM' mention from satisfying a
    # requirement that asks for specific platform experience.
    def _parse_enumerated_names(s: str) -> List[str]:
        parts = [p.strip() for p in re.split(r",|/|;|\\bor\\b|\\band\\b", s) if p.strip()]
        # filter out overly short tokens
        parts = [p for p in parts if len(p) >= 2]
        return parts

    # detect enumerated names in the primary candidate string
    primary = str(candidates[0] or "")
    enumerated = _parse_enumerated_names(primary)
    has_named_list = False
    if enumerated and (len(enumerated) > 1 or re.search(r"APIs?|platforms?", primary, re.IGNORECASE)):
        # treat as named list criterion
        has_named_list = True

    if has_named_list:
        # try to match any enumerated item exactly against CV skills
        for name in enumerated:
            key = _normalize_skill_key(name)
            if key in cv_norm_map:
                return "equivalent_match", cv_norm_map[key]
        # none of the explicit names appeared in CV: require named evidence
        return "requires_named", ""

    if isinstance(criterion_name, str) and len(criterion_name.split()) >= 3:
        tech_keywords = _extract_tech_keywords_from_criterion(criterion_name)
        for kw in tech_keywords:
            key = _normalize_skill_key(kw)
            if key in cv_norm_map:
                return "equivalent_match", cv_norm_map[key]

    return "", ""


def _match_criteria_to_cv(
    criteria: List[Dict[str, Any]],
    cv_data: dict,
    embedder: EmbeddingService,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    cv_skill_pool, cv_evidence = _collect_cv_evidence(cv_data)
    if not criteria:
        return [], cv_skill_pool

    criterion_texts = [_criterion_text(c) for c in criteria]
    sim_matrix = None
    if cv_evidence and criterion_texts:
        try:
            # CV evidence là passage (corpus), criteria là query (tìm kiếm)
            cv_prefixed   = _pprefix_batch(cv_evidence, embedder)
            crit_prefixed = _qprefix_batch(criterion_texts, embedder)
            all_texts = cv_prefixed + crit_prefixed
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[: len(cv_evidence)]
            criterion_embs = embs[len(cv_evidence):]
            if cv_embs.size and criterion_embs.size:
                sim_matrix = np.dot(cv_embs, criterion_embs.T)
        except Exception as e:
            logger.warning(f"Criteria evidence embedding failed: {e}")

    results: List[Dict[str, Any]] = []
    # lazy cross-encoder instance for verification
    ce_reranker = None
    for j, criterion in enumerate(criteria):
        importance = _normalize_importance(criterion.get("importance"))
        status, evidence = _find_exact_criterion_evidence(criterion, cv_skill_pool)
        ce_score = None
        # If criterion requires explicit named platform evidence and none was found,
        # skip semantic embedding fallback to avoid matching generic mentions.
        if status == "requires_named":
            best_sim = 0.0
            # treat as missing without embedding fallback
            status = "missing"
            evidence = ""
            skip_embedding = True
        else:
            best_sim = 1.0 if status else 0.0
            skip_embedding = False

        if not status and sim_matrix is not None and not skip_embedding:
            best_idx = int(sim_matrix[:, j].argmax())
            raw_sim = float(np.clip(sim_matrix[best_idx, j], 0.0, 1.0))

            SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
            span = max(SIM_MAX - SIM_MIN, 0.05)
            best_sim = float(np.clip((raw_sim - SIM_MIN) / span, 0.0, 1.0))

            evidence = cv_evidence[best_idx]
            category = str(criterion.get("category", "")).lower()
            source = str(criterion.get("source", "")).lower()
            is_atomic_skill = source.startswith("skills_") or category in {"skill", "technical_skill", "tool"}

            # Universal thresholds on normalized [0, 1] scale (config-driven)
            if is_atomic_skill:
                match_threshold = SCORING_CONFIG.ATOMIC_MATCH_THRESHOLD
                related_threshold = SCORING_CONFIG.ATOMIC_RELATED_THRESHOLD
            else:
                match_threshold = SCORING_CONFIG.GENERIC_MATCH_THRESHOLD
                related_threshold = SCORING_CONFIG.GENERIC_RELATED_THRESHOLD

            # Cross-domain guard: English atomic skill criteria are prone to false-positive
            # semantic matches against unrelated Vietnamese CV text.
            # e.g. "Sales Prospecting" vs "Tm Kim Khch Hng" → sim ~0.65-0.75 (similar
            # generic semantics) but different domains. We require sim >= 0.88 (exact
            # match bar) to accept, rejecting "related_only" false positives.
            criterion_name_lower = str(criterion.get("name", "")).lower()
            has_latin = bool(re.search(r'[a-z]{4,}', criterion_name_lower))
            has_vietnamese = bool(re.search(
                r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩđùúụủũôồốộổỗơờớợởỡỳýỵ]',
                criterion_name_lower
            ))
            is_english_atomic = is_atomic_skill and has_latin and not has_vietnamese

            if is_english_atomic and status not in {"exact_match", "equivalent_match"}:
                # Strict: only accept if sim >= match_threshold, else missing
                if best_sim < match_threshold:
                    status = "missing"
                    evidence = ""
                    best_sim = 0.0
                    ratio = 0.0
                # if best_sim >= match_threshold, fall through to set as semantic_match
            elif best_sim >= match_threshold:
                status = "semantic_match"
            elif best_sim >= related_threshold:
                status = "related_only"
            else:
                status = "missing"
                evidence = ""
                best_sim = 0.0

            # Cross-encoder verification: optionally verify semantic/related matches
            if (
                SCORING_CONFIG.CE_VERIFY_ENABLED
                and status in {"semantic_match", "related_only"}
                and evidence
            ):
                try:
                    if ce_reranker is None:
                        ce_reranker = CrossEncoderReranker(model_name=SCORING_CONFIG.CE_MODEL_NAME)
                    # criterion text (query) vs evidence (passage)
                    crit_text = criterion_texts[j]
                    ce_score = ce_reranker.score(crit_text, [evidence])[0]
                    # if CE verification fails, downgrade or mark missing
                    if ce_score < SCORING_CONFIG.CE_VERIFICATION_THRESHOLD:
                        if status == "semantic_match" and best_sim >= related_threshold:
                            status = "related_only"
                        else:
                            status = "missing"
                            evidence = ""
                            best_sim = 0.0
                    else:
                        # tighten confidence to reflect CE verification
                        best_sim = float(min(best_sim, ce_score))
                except Exception as _cev:
                    logger.debug(f"CE verification error: {_cev}")

        if not status:
            status = "missing"

        ratio = {
            "exact_match": 1.0,
            "equivalent_match": 1.0,
            "semantic_match": 0.85,
            "related_only": 0.35,
            "missing": 0.0,
        }.get(status, 0.0)

        results.append({
            "criterion_id": criterion.get("id", _criterion_id(j + 1, criterion.get("name", ""))),
            "name": criterion.get("name", ""),
            "category": criterion.get("category", "requirement"),
            "importance": importance,
            "match_status": status,
            "score_ratio": ratio,
            "confidence": round(best_sim, 4),
            "ce_score": round(ce_score, 4) if ce_score is not None else None,
            "cv_evidence": evidence,
            "question_intent": criterion.get("question_intent", "validate_depth"),
        })

    return results, cv_skill_pool


def _compute_skill_overlap_ratio(
    cv_skills: List[str],
    jd_skills: List[str],
    embedder: EmbeddingService,
    threshold: float = 0.85,  # FIX: was 0.70 — higher to reduce false positive semantic matches
) -> float:
    """Return proportion of JD skills that are truly covered, not mean raw similarity."""
    jd_skills = _dedupe_strings(jd_skills)
    cv_skills = _dedupe_strings(cv_skills)
    if not jd_skills:
        return 0.0
    if not cv_skills:
        return 0.0

    cv_groups = _build_skill_groups(cv_skills)
    matched = 0
    unmatched: List[str] = []
    for skill in jd_skills:
        if _normalize_skill_key(skill) in cv_groups:
            matched += 1
        else:
            unmatched.append(skill)

    if unmatched:
        try:
            # CV skills là passage, JD unmatched skills là query
            cv_prefixed  = _pprefix_batch(cv_skills, embedder)
            jd_prefixed  = _qprefix_batch(unmatched, embedder)
            all_texts = cv_prefixed + jd_prefixed
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[: len(cv_skills)]
            jd_embs = embs[len(cv_skills):]
            if cv_embs.size and jd_embs.size:
                sim_matrix = np.dot(cv_embs, jd_embs.T)
                max_sims = sim_matrix.max(axis=0)
                
                SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
                span = max(SIM_MAX - SIM_MIN, 0.05)
                raw_threshold = SIM_MIN + threshold * span
                
                matched += int(np.sum(max_sims >= raw_threshold))
        except Exception as e:
            logger.warning(f"Skill overlap embedding failed: {e}")

    return float(matched / max(len(jd_skills), 1))


# ── Skills Scoring (0-30) ─────────────────────────────────────────────────────
def _score_skills(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float,
    cv_embedding: np.ndarray = None,
    jd_embedding: np.ndarray = None,
) -> Tuple[float, List[str], List[str], float, List[str], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Score 0-30:
    - JD-generated criteria là nguồn scoring chính.
    - Embedding dùng để retrieve/verify evidence, không lấy mean similarity để cộng điểm.
    - Domain penalty chỉ cap khi coverage thấp, tránh phạt sai các ngành ngoài taxonomy.
    """
    criteria = _build_jd_criteria(jd_data)
    criteria_results, _ = _match_criteria_to_cv(criteria, cv_data, embedder)

    if not criteria:
        return 0.0, [], [], 0.0, [], {
            "raw_score": 0.0,
            "coverage_ratio": 0.0,
            "rule_score": 0.0,
            "semantic_score": 0.0,
            "exact_weight": 0.0,
            "semantic_weight": 0.0,
            "related_weight": 0.0,
            "total_weight": 0.0,
            "criteria_count": 0,
            "critical_matched": 0,
            "critical_total": 0,
            "important_matched": 0,
            "important_total": 0,
            "domain_cap_applied": False,
        }, []

    total_weight = sum(_criterion_weight(r["importance"]) for r in criteria_results) or 1.0
    exact_weight = 0.0
    semantic_weight = 0.0
    related_weight = 0.0
    earned_weight = 0.0

    for result in criteria_results:
        weight = _criterion_weight(result["importance"])
        contribution = weight * float(result.get("score_ratio", 0.0))
        earned_weight += contribution
        if result["match_status"] in {"exact_match", "equivalent_match"}:
            exact_weight += contribution
        elif result["match_status"] == "semantic_match":
            semantic_weight += contribution
        elif result["match_status"] == "related_only":
            related_weight += contribution

    coverage_ratio = earned_weight / total_weight
    raw_skills = min(coverage_ratio * 30.0, 30.0)

    # Domain taxonomy chỉ là phụ trợ: cap dựa theo cấu hình
    max_skills = SCORING_CONFIG.SKILLS_MAX
    if domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_SEVERE_PENALTY and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_SEVERE_COVERAGE:
        max_skills = SCORING_CONFIG.DOMAIN_CAP_SEVERE
    elif domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_MODERATE_PENALTY and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_MODERATE_COVERAGE:
        max_skills = SCORING_CONFIG.DOMAIN_CAP_MODERATE

    # Severe semantic mismatch cap
    if domain_penalty >= SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_PENALTY and coverage_ratio < SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_COVERAGE:
        max_skills = min(max_skills, SCORING_CONFIG.DOMAIN_CAP_SEMANTIC_MISMATCH_MAX)

    total_score = round(min(raw_skills, max_skills), 2)
    cap_factor = total_score / raw_skills if raw_skills > 0 else 1.0
    # Exact score = proportional share of total (respecting cap), not double-capped
    exact_raw = (exact_weight / total_weight) * raw_skills
    exact_capped = exact_raw * cap_factor
    exact_score = round(min(exact_capped, total_score), 2)
    semantic_score = round(max(0.0, total_score - exact_score), 2)

    matched_display = [
        r["name"]
        for r in criteria_results
        if r["match_status"] in {"exact_match", "equivalent_match", "semantic_match"}
    ]
    related_display = [
        r["name"]
        for r in criteria_results
        if r["match_status"] == "related_only"
    ]
    # Loại criteria category='education' và 'soft_skill' khỏi missing_skills:
    # - Education: đã được tính trong education_score riêng
    # - Soft skill: không thể verify qua CV text, gây noise cho HR
    _EXCLUDED_MISSING_CATEGORIES = {"education", "degree", "academic", "soft_skill"}
    missing_display = [
        r["name"]
        for r in criteria_results
        if r["match_status"] == "missing"
        and r["importance"] != "BONUS"
        and str(r.get("category", "")).lower() not in _EXCLUDED_MISSING_CATEGORIES
    ]
    missing_display.extend(
        r["name"]
        for r in criteria_results
        if r["match_status"] == "missing"
        and r["importance"] == "BONUS"
        and str(r.get("category", "")).lower() not in _EXCLUDED_MISSING_CATEGORIES
    )

    # Overall CV-JD embedding similarity for telemetry only.
    sim = 0.0
    try:
        if cv_embedding is not None and jd_embedding is not None:
            cv_emb = cv_embedding
            jd_emb = jd_embedding
        else:
            cv_text = embedder.encode_structured_cv(cv_data)
            jd_text = embedder.encode_structured_jd(jd_data)
            cv_emb = embedder.encode(_pprefix(cv_text, embedder))
            jd_emb = embedder.encode(_qprefix(jd_text, embedder))
        sim_raw = float(np.dot(cv_emb, jd_emb))
        sim = float(np.clip(sim_raw, 0.0, 1.0))
    except Exception as e:
        logger.warning(f"Embedding failed in skills scoring: {e}")
        sim = 0.0

    critical_total = sum(1 for r in criteria_results if r["importance"] == "CRITICAL")
    critical_matched = sum(
        1 for r in criteria_results
        if r["importance"] == "CRITICAL" and r["match_status"] != "missing"
    )
    important_total = sum(1 for r in criteria_results if r["importance"] == "IMPORTANT")
    important_matched = sum(
        1 for r in criteria_results
        if r["importance"] == "IMPORTANT" and r["match_status"] != "missing"
    )

    breakdown = {
        "raw_score": round(raw_skills, 2),
        "coverage_ratio": round(coverage_ratio, 4),
        "rule_score": exact_score,
        "semantic_score": semantic_score,
        "exact_weight": round(exact_weight, 2),
        "semantic_weight": round(semantic_weight, 2),
        "related_weight": round(related_weight, 2),
        "total_weight": round(total_weight, 2),
        "criteria_count": len(criteria_results),
        "critical_matched": critical_matched,
        "critical_total": critical_total,
        "important_matched": important_matched,
        "important_total": important_total,
        "domain_cap_applied": total_score < round(raw_skills, 2),
    }

    return (
        total_score,
        _dedupe_strings(matched_display),
        _dedupe_strings(missing_display),
        sim,
        _dedupe_strings(related_display),
        breakdown,
        criteria_results,
    )


# ════════════════════════════════════════════════════════════════════════════
# SEMANTIC MATCHING — thay thế keyword matching bằng embedding similarity
# ════════════════════════════════════════════════════════════════════════════

# Domain and seniority anchors moved to scoring_constants._DOMAIN_ANCHORS
# and scoring_constants._SENIORITY_ANCHORS to keep this module lightweight.

# Cache cho domain/seniority embeddings — init lần đầu khi dùng
_domain_anchors_embs: Dict[str, np.ndarray] = {}
_seniority_anchors_embs: Dict[int, np.ndarray] = {}

# Cache SIM calibration (SIM_MIN, SIM_MAX) theo model name
# Tránh 4 lần encode mỗi request trong _score_career_objectives
_sim_calibration_cache: Dict[str, tuple] = {}


def _ensure_anchor_embs(embedder: EmbeddingService) -> None:
    """Pre-compute và cache domain/seniority anchor embeddings với đúng prefix."""
    if not _domain_anchors_embs:
        for key, desc in _DOMAIN_ANCHORS.items():
            # Anchor là passage (corpus), dùng passage prefix
            _domain_anchors_embs[key] = embedder.encode(_pprefix(desc, embedder), normalize=True)
    if not _seniority_anchors_embs:
        for level, desc in _SENIORITY_ANCHORS.items():
            _seniority_anchors_embs[level] = embedder.encode(_pprefix(desc, embedder), normalize=True)


def _get_sim_calibration(embedder: EmbeddingService) -> tuple:
    """
    Trả về (SIM_MIN, SIM_MAX) được calibrate theo embedding model hiện tại.

    Kết quả được cache theo model_name — chỉ thực hiện 4 lần encode một lần duy nhất
    trong toàn bộ lifecycle ứng dụng. Các lần gọi sau trả về cached value O(1).

    SIM_MIN: similarity của 2 câu hoàn toàn không liên quan (lower bound).
    SIM_MAX: similarity của 2 câu gần giống nhau (upper bound).
    Dùng để rescale raw cosine similarity → [0, 10] score.
    """
    # Default cho multilingual-e5-base:
    # - Unrelated pairs: ~0.45–0.55
    # - Near-identical: ~0.92–0.97
    # Dùng giá trị thực đo được thay vì hardcode 0.25/0.65
    _SIM_MIN_DEFAULT = 0.45
    _SIM_MAX_DEFAULT = 0.92
    cache_key = str(getattr(embedder, "model_name", None) or id(embedder))
    if cache_key in _sim_calibration_cache:
        return _sim_calibration_cache[cache_key]
    try:
        # Dùng mixed prefix (passage vs query) để calibration phản ánh đúng
        # distribution thực tế khi so sánh CV (passage) vs JD/criteria (query)
        _unrelated_a = embedder.encode(_pprefix("software engineer python backend", embedder), normalize=True)
        _unrelated_b = embedder.encode(_qprefix("chef cooking restaurant food", embedder), normalize=True)
        _identical_a = embedder.encode(_pprefix("machine learning engineer AI", embedder), normalize=True)
        _identical_b = embedder.encode(_qprefix("machine learning engineer artificial intelligence", embedder), normalize=True)
        sim_low  = float(np.clip(np.dot(_unrelated_a, _unrelated_b), 0.0, 1.0))
        sim_high = float(np.clip(np.dot(_identical_a, _identical_b), 0.0, 1.0))
        if sim_high - sim_low > 0.1:
            result = (sim_low, sim_high)
        else:
            result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)
    except Exception:
        result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)
    _sim_calibration_cache[cache_key] = result
    logger.debug(f"SIM calibration cached for '{cache_key}': min={result[0]:.3f}, max={result[1]:.3f}")
    return result




def _semantic_domain_detection(
    text: str,
    embedder: EmbeddingService,
    threshold: float = 0.40,  # Normalized threshold
) -> str:
    """
    Semantic domain detection: embed text rồi so sánh cosine với domain anchors.
    Falls back to keyword-based detection if semantic score is too low.

    Threshold tuned cho multilingual-e5-base:
    - Unrelated pairs: ~0.45–0.55
    - Same domain: ~0.70–0.85
    - Threshold 0.50 → phân biệt được rõ ràng
    """
    _ensure_anchor_embs(embedder)
    if not text.strip():
        return "unknown"

    # Text cần detect → query role
    text_emb = embedder.encode(_qprefix(text, embedder), normalize=True)
    scores: Dict[str, float] = {
        key: float(np.dot(text_emb, anchor_emb))
        for key, anchor_emb in _domain_anchors_embs.items()
    }

    best_domain = max(scores, key=lambda d: scores[d])
    best_score = scores[best_domain]
    second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0

    # Yêu cầu: best phải vượt threshold VÀ cách biệt second-best ít nhất 0.03
    # Tránh case: 2 domain có sim gần bằng nhau → không rõ ràng
    if best_score >= threshold and (best_score - second_best) >= 0.03:
        return best_domain

    return best_domain if best_score >= threshold else "unknown"


# Project tech equivalence mapping moved to scoring_constants._PROJECT_TECH_EQUIVALENTS


def _expand_proj_tech(proj_tech: str) -> List[str]:
    """Expand a project technology to its equivalents + itself."""
    key = proj_tech.lower()
    equivalents = _PROJECT_TECH_EQUIVALENTS.get(key, [key])
    return [e.lower() for e in equivalents]


def _semantic_project_relevance(
    projects: List[dict],
    jd_data: dict,
    jd_text: str,
    embedder: EmbeddingService,
    default_duration: float = 0.25,
) -> Tuple[float, List[float], List[str]]:
    """
    Semantic project relevance: kết hợp Embedding Similarity và Tech Stack Exact Match.

    Flow:
    1. Embedding chỉ so sánh project description với JD RESPONSIBILITIES
       (không gộp skills list để tránh dilute embedding).
    2. Tech stack match: exact intersection giữa project technologies và JD skills.
    3. Final relevance = 40% semantic + 60% tech match.
    """
    if not projects:
        return 0.0, [], []

    jd_struct = jd_data.get("structured", jd_data)
    jd_skills = set(s.lower() for s in
                    jd_struct.get("skills_required", []) +
                    jd_struct.get("skills_preferred", []))

    # ── Precompute tech match scores cho tất cả projects ──────────────────
    jd_skills_all = set(s.lower() for s in
                        jd_struct.get("skills_required", []) +
                        jd_struct.get("skills_preferred", []))
    # skill_importance keys are capitalized (e.g. "Python", "OpenCV")
    skill_importance = jd_struct.get("skill_importance", {})
    # jd_critical: all skills from skills_required (normalized to lowercase)
    jd_critical = set(s.lower() for s in jd_struct.get("skills_required", []))
    # jd_important: skills where importance is IMPORTANT or CRITICAL
    jd_important = {
        s.lower() for s in jd_struct.get("skills_required", [])
        if skill_importance.get(s, "").lower() in ("important", "critical")
    }
    total_required = len(jd_critical)
    total_important = max(len(jd_important), 1)

    tech_info: List[Dict[str, Any]] = []
    for proj in projects:
        # Expand project techs via equivalence mapping before matching
        expanded_techs: set = set()
        for t in proj.get("technologies", []):
            expanded_techs.update(_expand_proj_tech(t))
        intersection = jd_skills_all.intersection(expanded_techs)
        critical_hits = len(intersection.intersection(jd_critical))
        important_hits = len(intersection.intersection(jd_important))

        # Quality-adjusted coverage: critical hits weigh 2x, important hits weigh 1x
        quality_score = (
            2.0 * critical_hits / max(total_required, 1) +
            1.0 * important_hits / total_important
        ) / 3.0

        tech_info.append({
            "intersection": intersection,
            "intersection_count": len(intersection),
            "critical_hits": critical_hits,
            "quality_score": quality_score,
        })

    # Responsibilities text là nguồn semantic signal tốt nhất (không có skills để dilute).
    # Nếu responsibilities quá ngắn → bổ sung requirements để có đủ ngữ cảnh.
    resp_text = " ".join(jd_struct.get("responsibilities", []))
    req_text = " ".join(jd_struct.get("requirements", []))
    if len(resp_text.split()) < 50:
        resp_text = resp_text + " " + req_text

    proj_texts = []
    for proj in projects:
        parts = [proj.get("name", ""), proj.get("description", "")]
        for hl in proj.get("highlights", []):
            parts.append(str(hl))
        proj_texts.append(" ".join(p for p in parts if p))

    try:
        jd_emb = embedder.encode(_qprefix(resp_text, embedder), normalize=True)
        proj_prefixed = _pprefix_batch(proj_texts, embedder)
        proj_embs = embedder.encode_batch(proj_prefixed, normalize=True)
        sims = np.clip(proj_embs @ jd_emb, 0.0, 1.0)
    except Exception as e:
        logger.warning(f"_semantic_project_relevance embedding failed: {e}")
        return 0.0, [], proj_texts

    SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
    span = max(SIM_MAX - SIM_MIN, 0.05)

    # ── Duration computation ───────────────────────────────────────────────
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

    # Compute per-project hybrid relevance (embedding + tech) first
    for i, (proj, dur) in enumerate(zip(projects, durations)):
        raw_sim = float(sims[i])
        normalized_sim = (raw_sim - SIM_MIN) / span

        intersection_count = tech_info[i]["intersection_count"]
        tech_score = min(0.10 + 0.35 * math.sqrt(intersection_count), 0.70)
        has_tech = intersection_count > 0

        semantic_score = max(0.0, normalized_sim)

        # use per-project critical_hits from tech_info (avoid relying on outer-scope var)
        critical_hits = tech_info[i].get("critical_hits", 0)

        if has_tech:
            if intersection_count >= 2 or critical_hits > 0:
                tech_weight = 0.70
            elif intersection_count == 1:
                tech_weight = 0.60
            else:
                tech_weight = 0.55
            relevance = float(np.clip(tech_weight * tech_score + (1.0 - tech_weight) * semantic_score, 0.0, 1.0))
        else:
            relevance = float(np.clip(0.70 * semantic_score, 0.0, 1.0))

        relevance = float(np.clip(relevance, 0.0, 1.0))
        relevance_scores.append(relevance)
        descriptions.append(proj_texts[i])

    # ── Optional: cross-encoder reranking for top-K candidates
    try:
        top_k = min(max(int(SCORING_CONFIG.RERANK_TOP_K), 0), len(relevance_scores))
    except Exception:
        top_k = 0

    if top_k > 0 and len(relevance_scores) > 0:
        try:
            ce = CrossEncoderReranker(model_name=SCORING_CONFIG.CE_MODEL_NAME)
            # Select top-K by current relevance
            top_idxs = list(np.argsort(relevance_scores)[::-1][:top_k])
            candidates = [proj_texts[i] for i in top_idxs]
            ce_raw = ce.score(resp_text, candidates)
            if ce_raw:
                ce_arr = np.array(ce_raw, dtype=float)
                # normalize to [0,1]
                if float(np.ptp(ce_arr)) == 0.0:
                    ce_norm = np.full_like(ce_arr, 0.5)
                else:
                    ce_norm = (ce_arr - ce_arr.min()) / float(np.ptp(ce_arr))
                beta = float(np.clip(SCORING_CONFIG.RERANK_WEIGHT, 0.0, 1.0))
                for idx, ce_score in zip(top_idxs, ce_norm.tolist()):
                    orig = relevance_scores[idx]
                    new_rel = float(np.clip(beta * orig + (1.0 - beta) * float(ce_score), 0.0, 1.0))
                    relevance_scores[idx] = new_rel
        except Exception as e:
            logger.debug("Reranker failed: %s", e)

    # Compute total project-years after any reranking adjustments
    total_years = 0.0
    for dur, rel in zip(durations, relevance_scores):
        total_years += dur * float(rel)

    return total_years, relevance_scores, descriptions


def _semantic_seniority_detection(
    titles: List[str],
    descriptions: List[str],
    embedder: EmbeddingService,
) -> int:
    """
    Semantic seniority detection: so sánh CV title+description với seniority anchors.

    Trả về level 0-4 dựa trên anchor có similarity cao nhất.
    """
    _ensure_anchor_embs(embedder)
    if not titles and not descriptions:
        return 0

    cv_text = " ".join(titles + descriptions)
    if not cv_text.strip():
        return 0

    # CV text là query (tìm anchor phù hợp nhất), anchor là passage → dùng query prefix
    cv_emb = embedder.encode(_qprefix(cv_text, embedder), normalize=True)
    best_level = 0
    best_sim = -1.0
    for level, anchor_emb in _seniority_anchors_embs.items():
        sim = float(np.dot(cv_emb, anchor_emb))
        if sim > best_sim:
            best_sim = sim
            best_level = level

    return best_level


def _major_relevance_score(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
) -> float:
    """
    Semantic-based major relevance scoring — ATS modern approach.

    KhÔNG hardcode keyword cho từng ngành. Dùng embedding similarity giữa
    education text và JD context để xác định mức độ phù hợp.

    Returns float 0.0-1.0:
        1.0 = strong major-domain match (e.g. "Kế toán" CV vs "Accountant" JD)
        0.5 = partial/adjaent match (e.g. "Kinh tế" CV vs "Data Analyst" JD)
        0.0 = no relevance (e.g. "Văn học" CV vs "Software Engineer" JD)

    Chiến lược 2-tier giống ATS hiện đại:
      1. Enrich education text bằng school context để tăng embedding density
      2. Embed education vs JD context text, dùng raw cosine similarity
    """
    if not cv_education:
        return 0.0

    jd_struct = jd_data.get("structured", jd_data)

    # Build JD context text — enriched version của job để embedding có ngữ cảnh
    jd_context_parts = [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        # Sử dụng responsibilities + requirements vì chúng mô tả CÔNG VIỆC thực tế,
        # không phải title trừu tượng. VD: "Senior AI Engineer" quá ngắn, nhưng
        # "Design and develop AI/ML systems, fine-tune LLMs" cho embedding context tốt hơn.
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
        # Skills required cung cấp vocabulary cụ thể cho domain
        " ".join(jd_struct.get("skills_required", [])),
        " ".join(jd_struct.get("skills_preferred", [])),
    ]
    jd_context = " ".join(filter(None, jd_context_parts)).strip()

    # Enrich education text — school name cung cấp domain context quan trọng
    # VD: "ĐH Bách Khoa Hà Nội" → context "engineering", "ĐH Kinh tế" → "business/finance"
    # Dùng school name thay vì industry vì school name thường có trong parsed data
    edu_texts: List[str] = []
    for edu in cv_education:
        edu_parts = [
            edu.get("major", ""),
            edu.get("degree", ""),
            edu.get("school", ""),
            edu.get("description", ""),
        ]
        # Filter out empty parts but keep structure
        filtered = [p.strip() for p in edu_parts if p.strip()]
        edu_text = " ".join(filtered)
        if edu_text:
            edu_texts.append(edu_text)

    if not edu_texts or not jd_context:
        return 0.0

    try:
        SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
        span = max(SIM_MAX - SIM_MIN, 0.05)

        # Embed: JD là query, mỗi education entry là passage
        jd_emb = embedder.encode(_qprefix(jd_context, embedder), normalize=True)
        edu_embs = embedder.encode_batch(_pprefix_batch(edu_texts, embedder), normalize=True)

        # Lấy max similarity — chỉ cần 1 education entry phù hợp là đạt
        best_sim = 0.0
        for i in range(len(edu_texts)):
            raw_sim = float(np.dot(edu_embs[i], jd_emb))
            # Normalize về 0-1 scale
            normalized_sim = max(0.0, min(1.0, (raw_sim - SIM_MIN) / span))
            if normalized_sim > best_sim:
                best_sim = normalized_sim

        return round(best_sim, 3)

    except Exception as e:
        logger.warning(f"Major relevance embedding failed: {e}")
        return 0.0


def _semantic_major_relevance(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> bool:
    """
    Legacy wrapper — kept for backward compatibility.
    Returns True if _major_relevance_score >= threshold.
    """
    score = _major_relevance_score(cv_education, jd_data, embedder)
    return score >= threshold


# ════════════════════════════════════════════════════════════════════════════
# END SEMANTIC MATCHING
# ════════════════════════════════════════════════════════════════════════════




# ── Education Scoring (0-10) ──────────────────────────────────────────────────
def _score_education(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float = 0.0,
) -> Tuple[float, str]:
    """
    Score 0-10.
    domain_penalty: passed from scoring engine (0.0 = same domain, 1.0 = completely unrelated).
    When domain_penalty >= 0.7 (SEVERE mismatch), education base is heavily capped because
    a Literature degree is completely irrelevant to IT — the degree level alone is not enough.
    """
    jd_struct = jd_data.get("structured", jd_data)
    req_text = " ".join(jd_struct.get("requirements", []))

    degree_map = {
        "phd": 5, "tiến sĩ": 5, "doctor": 5,
        "thạc sĩ": 4, "master": 4, "m.sc": 4,
        "cử nhân": 3, "bachelor": 3, "b.sc": 3, "đại học": 3,
        "cao đẳng": 2, "college": 2,
        "trung cấp": 1,
    }

    req_degree = 0
    for kw, val in degree_map.items():
        if kw in req_text.lower():
            req_degree = max(req_degree, val)

    cv_degree = 0
    for edu in cv_data.get("education", []):
        text = f"{edu.get('degree', '')} {edu.get('major', '')} {edu.get('school', '')}".lower()
        for kw, val in degree_map.items():
            if kw in text:
                cv_degree = max(cv_degree, val)
        if edu.get("degree") or edu.get("major"):
            cv_degree = max(cv_degree, 2)

    # Lấy thông tin sinh viên từ LLM Parser
    cv_is_student = cv_data.get("is_student", False)
    if cv_is_student:
        cv_degree = max(cv_degree, 3)

    # FIX 15A: For SEVERE domain mismatch, force cv_major_match=False regardless
    # of semantic similarity. A Literature degree is NEVER relevant to IT backend,
    # even if the embedding model finds some superficial similarity.
    if domain_penalty >= 0.7:
        cv_major_match = False
        is_severe_domain_mismatch = True
    else:
        cv_major_match = _semantic_major_relevance(
            cv_data.get("education", []), jd_data, embedder, threshold=0.40
        )
        is_severe_domain_mismatch = False

    # Sử dụng mảng certifications bóc tách bởi LLM Parser thay vì regex keyword
    cert_count = len(cv_data.get("certifications", []))

    # JD Intern / Sinh viên được xác định bằng LLM Parser
    jd_is_intern_student = jd_struct.get("is_entry_level", False)

    effective_req_degree = req_degree
    if req_degree == 0 and jd_is_intern_student:
        # JD dành cho sinh viên/intern: kỳ vọng ngầm là đang học đại học
        effective_req_degree = 3

    if effective_req_degree > 0:
        if cv_degree >= effective_req_degree:
            # Đáp ứng đủ bằng cấp: base 8.0 (đúng ngành) hoặc 5.0 (trái ngành)
            base = 8.0 if cv_major_match else 5.0
        elif cv_is_student and cv_degree >= effective_req_degree - 1:
            # Đang học, sắp đủ bằng: base 7.5 (đúng ngành) hoặc 4.5 (trái ngành)
            base = 7.5 if cv_major_match else 4.5
        else:
            base = max(0.0, (cv_degree / max(effective_req_degree, 1)) * 5.0)
            if cv_major_match:
                base += 1.5
    else:
        base = 6.0 if cv_major_match else 4.0

    # FIX 15A (continued): SEVERE domain mismatch — hard cap on base
    # Even if degree level is sufficient, a completely unrelated degree deserves
    # at most 2.0 base. This prevents Literature → IT from scoring 5.0 just because
    # both have "bachelor" degree level.
    if is_severe_domain_mismatch:
        base = min(base, 2.0)
        cert_bonus_max = 1.0  # at most +1.0 from certs (max score = 3.0)
    elif domain_penalty >= 0.5:
        # NEW: Moderate domain mismatch — education score capped at 4.0
        base = min(base, 4.0)
        cert_bonus_max = 1.0
    else:
        cert_bonus_max = 2.0   # at most +2.0 from certs (max score = 10.0)

    # Bonus cho sinh viên đang học đúng ngành với JD intern/fresher
    if cv_is_student and cv_major_match:
        base = min(base + 1.0, 9.0)  # tối đa 9.0 để còn chỗ cho cert bonus

    # Mỗi chứng chỉ +0.5 điểm (tối đa 4 chứng chỉ = 2.0 điểm)
    score = min(base + min(cert_count, 4) * 0.5, 10.0)
    # But cap cert bonus for severe mismatch
    score = min(score, base + cert_bonus_max)

    major_note = "Ngành học phù hợp." if cv_major_match else "Ngành học không liên quan trực tiếp."
    student_note = " Đang học (chưa tốt nghiệp)." if cv_is_student else ""
    if is_severe_domain_mismatch:
        major_note = "Domain hoàn toàn không liên quan — ngành học không có giá trị cho JD này."
    student_note = " Đang học (chưa tốt nghiệp)." if cv_is_student else ""
    rationale = f"Trình độ: {cv_degree}/5.{student_note} {major_note}"
    if cert_count > 0:
        rationale += f" Có {cert_count} chứng chỉ liên quan."

    return round(min(score, 10.0), 2), rationale


# ── Career Objectives Scoring (0-10) ─────────────────────────────────────────
def _score_career_objectives(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float = 0.0,
) -> Tuple[float, str]:
    """
    Score 0-10.
    domain_penalty: passed from scoring engine (0.0 = same domain, 1.0 = completely unrelated).
    When domain_penalty >= 0.7 (SEVERE mismatch), career score is capped at max 1.0 because
    a Literature major's career goals are completely irrelevant to IT — even if the embedding
    finds superficial semantic similarity between "communication skills" and "teamwork", it
    shouldn't count as career alignment.
    """
    cv_objective = (cv_data.get("career_objectives") or cv_data.get("objective") or "").strip()
    jd_struct = jd_data.get("structured", jd_data)

    jd_goal_text = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("responsibilities", [])),
        " ".join(jd_struct.get("requirements", [])),
        jd_struct.get("industry", ""),
        jd_struct.get("career_expectations", ""),
    ]))

    # BUG 5 FIX: CV không có career objective → không phạt cứng 0 điểm.
    # Thay vào đó, fallback sang so sánh cv.skills + cv.work_experience titles với JD.
    if not cv_objective:
        # Fallback: xây dựng proxy text từ skills + experience titles
        cv_skills_list = cv_data.get("skills", []) + cv_data.get("technical_skills", []) + cv_data.get("domain_skills", [])
        cv_exp_titles = [exp.get("title", "") for exp in cv_data.get("work_experience", []) if exp.get("title")]
        cv_proxy_text = " ".join(filter(None, cv_skills_list + cv_exp_titles)).strip()
        if not cv_proxy_text:
            default = 1.0 if domain_penalty >= 0.7 else 3.0
            note = "Domain hoan toan khong lien quan." if domain_penalty >= 0.7 else "Khong du thong tin de danh gia."
            return default, f"CV khong co muc tieu nghe nghiep. {note} (diem mac dinh {default}/10)."
        # Dùng proxy text để tính similarity, nhưng cap tối đa 6/10 vì thiếu objective
        try:
            proxy_emb = embedder.encode(cv_proxy_text, normalize=True)
            jd_emb_fb = embedder.encode(jd_goal_text, normalize=True)
            sim_fb = float(np.clip(np.dot(proxy_emb, jd_emb_fb), 0.0, 1.0))
            SIM_MIN_FB, SIM_MAX_FB = 0.25, 0.65
            proxy_score = float(np.clip((sim_fb - SIM_MIN_FB) / (SIM_MAX_FB - SIM_MIN_FB) * 6.0, 0.0, 6.0))
            return round(min(proxy_score, 2.0 if domain_penalty >= 0.7 else 6.0), 2), (
                f"CV khong co muc tieu nghe nghiep. "
                f"Diem proxy tu skills + kinh nghiem (max {2.0 if domain_penalty >= 0.7 else 6.0}/10): {proxy_score:.1f}/10."
                f" {'Domain khong lien quan.' if domain_penalty >= 0.7 else ''}"
            )
        except Exception:
            return round(min(3.0, 1.0 if domain_penalty >= 0.7 else 3.0), 2), (
                f"CV khong co muc tieu nghe nghiep. Khong the tinh diem proxy "
                f"(diem mac dinh {1.0 if domain_penalty >= 0.7 else 3.0}/10)."
                f" {'Domain khong lien quan.' if domain_penalty >= 0.7 else ''}"
            )

    if not jd_goal_text:
        return 5.0, "Không có thông tin JD để so sánh mục tiêu."

    score = 0.0
    sim = 0.0
    rationale_parts: List[str] = []

    # 1. Semantic similarity
    # BUG 6 FIX: SIM_MIN/SIM_MAX trước đây hardcode 0.25/0.65.
    # Nếu đổi embedding model, range similarity thay đổi hoàn toàn → threshold lỗi.
    # Fix: tính SIM_MIN/SIM_MAX động bằng cách embed 2 cặp câu cực đoan (unrelated/identical)
    # rồi dùng làm anchor. Kết quả được CACHE theo model name để tránh 4 encode/request.
    SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)

    # Chỉ embed job_title + responsibilities (focused, không bị nhiễu bởi requirements dài)
    jd_focused_text = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("responsibilities", [])),
        jd_struct.get("industry", ""),
        jd_struct.get("career_expectations", ""),
    ]))

    try:
        # Objective là query (ứng viên tìm job), JD focused text là passage (job description)
        cv_emb = embedder.encode(_qprefix(cv_objective, embedder), normalize=True)
        jd_emb = embedder.encode(_pprefix(jd_focused_text, embedder), normalize=True)
        sim = float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0))
        score = float(np.clip((sim - SIM_MIN) / (SIM_MAX - SIM_MIN) * 10.0, 0.0, 10.0))
        
        # Keyword Boost: Nếu CV objective chứa từ khóa chính của Job Title
        jd_title_lower = str(jd_data.get("job_title", "")).lower()
        title_kws = [w for w in re.split(r'\W+', jd_title_lower) if len(w) > 2]
        obj_lower = cv_objective.lower()
        match_count = sum(1 for kw in title_kws if kw in obj_lower)
        
        if match_count >= 2:
            score = max(score, 8.5)
        elif match_count == 1:
            score = max(score, 6.0)
            
    except Exception as e:
        logger.warning(f"Embedding failed in career objectives scoring: {e}")
        sim = 0.0
        score = 0.0

    # 2. Overqualified penalty: objective nhắm vị trí cao hơn JD
    obj_lower = cv_objective.lower()
    senior_kws = ["manager", "senior", "lead", "director", "head", "chief", "principal"]
    jd_lower = jd_focused_text.lower()
    cv_targets_senior = any(kw in obj_lower for kw in senior_kws)
    jd_is_junior = any(kw in jd_lower for kw in ["intern", "fresher", "junior", "entry"])
    if cv_targets_senior and jd_is_junior:
        score = max(score - 2.0, 0.0)
        rationale_parts.append("Mục tiêu vị trí cao hơn JD (overqualified).")

    # 3. Rationale dựa trên score đã rescale (không phải sim raw)
    if score >= 8.0:
        rationale_parts.append("Mục tiêu nghề nghiệp phù hợp cao với JD.")
    elif score >= 5.0:
        rationale_parts.append("Mục tiêu nghề nghiệp phù hợp với JD.")
    elif score >= 2.5:
        rationale_parts.append("Mục tiêu nghề nghiệp có liên quan một phần.")
    else:
        rationale_parts.append("Mục tiêu nghề nghiệp chưa phù hợp với JD.")

    rationale = " ".join(rationale_parts) if rationale_parts else "Mục tiêu nghề nghiệp chưa rõ ràng."

    # FIX 15B: SEVERE domain mismatch — cap career score at 1.0
    # Even if the embedding finds some semantic similarity (e.g., "communication" vs
    # "teamwork"), a Literature major's career goals are completely unrelated to IT.
    # The proxy fallback also shouldn't score high for unrelated domains.
    if domain_penalty >= 0.7:
        score = min(score, 1.0)
        rationale = "Domain hoàn toàn không liên quan — mục tiêu nghề nghiệp không có giá trị cho JD này."

    return round(min(score, 10.0), 2), rationale


# ── Company Fit Scoring (0-10) ────────────────────────────────────────────
def _score_company_fit(
    cv_data: dict,
    company_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    """
    Cham diem do phu hop giua CV va Company Info (CI).

    Thang diem 0-10 (KHONG tinh vao tong 100):
        [A] Tech Stack Match  : 0-4.0  -- CV skills vs tech stack chi tiet cua cong ty
        [B] Domain / Industry : 0-3.0  -- CV domain vs company industry + sub_industry
        [C] Culture Fit       : 0-2.0  -- CV objective vs company culture + values (embedding)
        [D] Engineering Bonus : 0-1.0  -- CV co CI/CD, Agile... matches engineering_practices

    Schema CI (tu parser_company):
        key_skills, technologies, primary_languages, frameworks,
        databases, infrastructure, ai_ml_stack,
        industry, sub_industry, business_model,
        company_culture, work_culture, tech_culture, remote_policy,
        values, mission, description, engineering_practices
    """
    if not company_data or not company_data.get("success"):
        return 0.0, "Khong co du lieu cong ty."

    rationale_parts: List[str] = []

    # -- [A] Tech Stack Match (0-4.0) -----------------------------------------
    # Gom toan bo tech stack tu CI
    ci_tech: List[str] = []
    for field in ("key_skills", "technologies", "primary_languages",
                  "frameworks", "databases", "infrastructure", "ai_ml_stack"):
        ci_tech.extend(company_data.get(field, []))

    # Gom skills day du tu CV
    cv_skill_pool: List[str] = []
    for field in ("skills", "technical_skills", "domain_skills"):
        cv_skill_pool.extend(cv_data.get(field, []))
    for proj in cv_data.get("projects", []):
        cv_skill_pool.extend(_coerce_string_list(proj.get("technologies", [])))

    cv_groups   = _build_skill_groups(cv_skill_pool)
    comp_groups = _build_skill_groups(ci_tech)

    if comp_groups:
        matched_tech, _ = _skill_group_match(cv_groups, comp_groups)
        # F1-style: ca coverage tu phia cong ty VA tu phia CV
        precision = len(matched_tech) / max(len(cv_groups), 1)
        recall    = len(matched_tech) / max(len(comp_groups), 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-6)
        tech_score = round(min(f1 * 4.0, 4.0), 2)
        rationale_parts.append(
            f"[Tech] {len(matched_tech)}/{len(comp_groups)} nhom ky nang (F1={f1:.0%}) -> {tech_score}/4"
        )
    else:
        tech_score = 2.0
        matched_tech = []
        rationale_parts.append("[Tech] CI khong co du lieu tech stack -> mac dinh 2/4")

    # -- [B] Domain / Industry Fit (0-3.0) ------------------------------------
    ci_industry_text = " ".join(filter(None, [
        str(company_data.get("industry", "")),
        str(company_data.get("sub_industry", "")),
        str(company_data.get("business_model", "")),
        " ".join(str(x) for x in company_data.get("ai_ml_stack", []) if x),
        str(company_data.get("tech_culture", "")),
    ])).lower()

    cv_domain = cv_data.get("domain")
    if not cv_domain or cv_domain == "unknown":
        cv_text_for_domain = _build_cv_text(cv_data)
        cv_domain = _semantic_domain_detection(cv_text_for_domain, embedder, threshold=0.38)

    domain_score = 0.0
    domain_rationale = ""
    if ci_industry_text.strip():
        # Dùng hoàn toàn semantic similarity thay vì keyword dictionary
        try:
            cv_text_for_domain = cv_data.get("domain", "") + " " + cv_text_for_domain
            cv_dom_emb = embedder.encode(cv_text_for_domain[:600], normalize=True)
            ci_dom_emb = embedder.encode(ci_industry_text[:400], normalize=True)
            dom_sim = float(np.clip(np.dot(cv_dom_emb, ci_dom_emb), 0.0, 1.0))
            
            SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
            span = max(SIM_MAX - SIM_MIN, 0.1)
            scaled_sim = np.clip((dom_sim - SIM_MIN) / span, 0.0, 1.0)
            
            domain_score = round(scaled_sim * 3.0, 2)
            domain_rationale = f"Semantic match sim={dom_sim:.0%}"
        except Exception:
            domain_score, domain_rationale = 1.5, "Khong xac dinh duoc domain"
    else:
        domain_score, domain_rationale = 1.5, "CI khong co thong tin industry"

    domain_score = round(min(domain_score, 3.0), 2)
    rationale_parts.append(f"[Domain] {domain_rationale} -> {domain_score}/3")

    # -- [C] Culture Fit -- Embedding (0-2.0) ----------------------------------
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
    if ci_culture_text.strip() and cv_objective:
        try:
            SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
            cv_cul_emb = embedder.encode(cv_objective[:600], normalize=True)
            ci_cul_emb = embedder.encode(ci_culture_text[:600], normalize=True)
            cul_sim = float(np.clip(np.dot(cv_cul_emb, ci_cul_emb), 0.0, 1.0))
            cul_scaled = float(np.clip(
                (cul_sim - SIM_MIN) / max(SIM_MAX - SIM_MIN, 0.1), 0.0, 1.0
            ))
            culture_score = round(min(cul_scaled * 2.0, 2.0), 2)
            rationale_parts.append(
                f"[Culture] sim={cul_sim:.0%} (scaled={cul_scaled:.0%}) -> {culture_score}/2"
            )
        except Exception as e:
            logger.warning(f"Embedding failed in culture fit: {e}")
            culture_score = 1.0
            rationale_parts.append("[Culture] Loi embedding -> mac dinh 1/2")
    else:
        culture_score = 1.0
        rationale_parts.append("[Culture] Thieu thong tin van hoa cong ty -> mac dinh 1/2")

    # -- [D] Engineering Practices Bonus (0-1.0) -------------------------------
    ci_eng_practices: List[str] = company_data.get("engineering_practices", [])
    eng_bonus = 0.0
    if ci_eng_practices:
        cv_evidence_text = " ".join(filter(None, [
            " ".join(str(x) for x in cv_data.get("skills", []) if x),
            " ".join(str(x) for x in cv_data.get("technical_skills", []) if x),
            " ".join(
                hl
                for exp in cv_data.get("work_experience", [])
                for hl in _coerce_string_list(exp.get("highlights", []))
            ),
        ])).lower()
        ci_practices_text = " ".join(str(x) for x in ci_eng_practices if x).lower()

        # Dùng hoàn toàn semantic similarity thay vì keyword dictionary
        try:
            cv_prac_emb = embedder.encode(cv_evidence_text[:600], normalize=True)
            ci_prac_emb = embedder.encode(ci_practices_text[:400], normalize=True)
            prac_sim = float(np.clip(np.dot(cv_prac_emb, ci_prac_emb), 0.0, 1.0))
            
            SIM_MIN, SIM_MAX = _get_sim_calibration(embedder)
            span = max(SIM_MAX - SIM_MIN, 0.1)
            scaled_sim = np.clip((prac_sim - SIM_MIN) / span, 0.0, 1.0)
            
            eng_bonus = round(scaled_sim * 1.0, 2)
            rationale_parts.append(f"[Engineering] semantic sim={prac_sim:.0%} -> +{eng_bonus}/1")
        except Exception:
            eng_bonus = 0.0
            rationale_parts.append("[Engineering] Loi embedding -> +0/1")
    else:
        rationale_parts.append("[Engineering] CI khong co engineering_practices -> +0")

    # -- Tong hop --------------------------------------------------------------
    total = round(min(tech_score + domain_score + culture_score + eng_bonus, 10.0), 2)
    summary = (
        f"Tech: {tech_score}/4 | Domain: {domain_score}/3 | "
        f"Culture: {culture_score}/2 | Engineering: {eng_bonus}/1 -> Tong: {total}/10"
    )
    rationale_parts.insert(0, summary)
    return total, " | ".join(rationale_parts)


# ── Main Entry Point ──────────────────────────────────────────────────────────
def calculate_hybrid_score(
    cv_data: dict,
    jd_data: dict,
    company_data: dict = None,
    cv_embedding: np.ndarray = None,
    jd_embedding: np.ndarray = None,
) -> dict:
    """
    Hybrid CV-JD scoring v4.

    Scoring formula (max = 100):
        experience_score        : 0-50  — work years + seniority + domain penalty
        skills_score           : 0-30  — CRITICAL/IMPORTANT/BONUS + embedding boost + domain cap
        education_score        : 0-10  — degree level + major relevance + certifications
        career_objectives_score: 0-10  — semantic match CV objective vs JD goal

    company_fit_score (0-10) được trả về riêng, KHÔNG tính vào tổng 100.

    Domain penalty được tính một lần, áp dụng xuyên suốt exp và skills.
    """
    try:
        embedder = get_embedding_service()

        # Detect domain sớm — dùng cho penalty toàn hệ thống
        # SEMANTIC MATCHING: dùng embedding thay keyword cho domain detection
        cv_domain = cv_data.get("domain")
        if not cv_domain or cv_domain == "unknown":
            cv_text_full = _build_cv_text(cv_data)
            cv_domain = _semantic_domain_detection(cv_text_full, embedder, threshold=0.40)
            
        jd_domain = jd_data.get("structured", {}).get("domain")
        if not jd_domain or jd_domain == "unknown":
            jd_text_full = _build_jd_text(jd_data)
            jd_domain = _semantic_domain_detection(jd_text_full, embedder, threshold=0.40)

        # Skill overlap cho domain penalty: dùng tỷ lệ JD required được cover thật,
        # không dùng mean raw cosine similarity.
        jd_struct = jd_data.get("structured", jd_data)

        # BUG 7 FIX: Chỉ dùng skills_required (kỹ thuật) để tính skill_overlap cho domain penalty.
        # KHÔNG dùng skills_preferred vì preferred thường gồm soft skills như "Problem Solving",
        # "Logical Thinking" — những kỹ năng này tương đồng ngữ nghĩa với CV sales ("Negotiation",
        # "Communication") → inflate skill_overlap → domain penalty bị underestimate.
        # Ví dụ: sales CV vs AI JD → skill_overlap = 34% thay vì ~5% → penalty 0.50 thay vì 0.85.
        jd_skills_for_overlap = [
            s for s in jd_struct.get("skills_required", [])
            if isinstance(s, str) and s.strip()
            and _normalize_skill_key(s) not in _SOFT_SKILL_KEYS
        ]
        # Fallback: nếu required rỗng hoàn toàn, dùng preferred nhưng vẫn filter soft skills
        if not jd_skills_for_overlap:
            jd_skills_for_overlap = [
                s for s in jd_struct.get("skills_preferred", [])
                if isinstance(s, str) and s.strip()
                and _normalize_skill_key(s) not in _SOFT_SKILL_KEYS
            ]

        cv_skills_flat, _ = _collect_cv_evidence(cv_data)
        skill_overlap = _compute_skill_overlap_ratio(
            cv_skills_flat, jd_skills_for_overlap, embedder, threshold=0.72
        )

        domain_penalty, _ = _compute_domain_penalty(cv_domain, jd_domain, skill_overlap)

        exp_score, exp_rationale, exp_features = _score_experience(
            cv_data, jd_data, cv_domain, jd_domain, skill_overlap, embedder
        )
        (
            skills_score,
            matched_skills,
            missing_skills_list,
            sim,
            related_skills,
            skills_breakdown,
            criteria_match_results,
        ) = _score_skills(
            cv_data, jd_data, embedder, domain_penalty,
            cv_embedding=cv_embedding, jd_embedding=jd_embedding
        )
        edu_score, edu_rationale = _score_education(cv_data, jd_data, embedder, domain_penalty)
        career_obj_score, career_obj_rationale = _score_career_objectives(
            cv_data, jd_data, embedder, domain_penalty
        )
        try:
            company_score, company_rationale = _score_company_fit(cv_data, company_data, embedder)
        except Exception as _ce:
            import logging as _lg
            _lg.getLogger(__name__).error(f"[COMPANY_FIT] Isolated exception: {_ce}", exc_info=True)
            company_score, company_rationale = 0.0, f"Loi tinh company fit: {_ce}"

        overall = round(min(exp_score + skills_score + edu_score + career_obj_score, 100.0))

    except Exception as e:
        logger.error(f"Scoring failed, using fallback: {e}")
        embedder = get_embedding_service()
        sim = 0.0
        try:
            cv_emb = embedder.encode(_qprefix(embedder.encode_structured_cv(cv_data), embedder))
            jd_emb = embedder.encode(_pprefix(embedder.encode_structured_jd(jd_data), embedder))
            sim = round(float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0)), 4)
        except Exception as inner_e:
            logger.error(f"Fallback embedding also failed: {inner_e}")
            sim = 0.0
        exp_score = skills_score = edu_score = career_obj_score = company_score = overall = 0
        exp_rationale = "Không thể tính điểm kinh nghiệm."
        exp_features = {}
        matched_skills = []
        related_skills = []
        missing_skills_list = []
        skills_breakdown = {
            "raw_score": 0.0,
            "coverage_ratio": 0.0,
            "rule_score": 0.0,
            "semantic_score": 0.0,
            "criteria_count": 0,
            "domain_cap_applied": False,
        }
        criteria_match_results = []
        edu_rationale = "Không thể tính điểm học vấn."
        career_obj_rationale = "Không thể tính điểm mục tiêu nghề nghiệp."
        company_rationale = "Không có dữ liệu công ty."
        cv_domain = jd_domain = "unknown"
        domain_penalty = 0.0

    # Build strengths
    main_strengths: List[str] = []
    if exp_score >= 40:
        main_strengths.append("Kinh nghiệm phù hợp và dồi dào")
    elif exp_score >= 25:
        main_strengths.append("Có nền tảng kinh nghiệm tốt")
    if skills_score >= 20:
        main_strengths.append("Kỹ năng đáp ứng tốt yêu cầu")
    elif skills_score >= 12:
        main_strengths.append("Kỹ năng đáp ứng một phần yêu cầu")
    if edu_score >= 7:
        main_strengths.append("Trình độ học vấn đạt chuẩn và đúng ngành")
    if career_obj_score >= 7:
        main_strengths.append("Mục tiêu nghề nghiệp rõ ràng, phù hợp JD")

    # Build areas
    areas: List[str] = []
    if missing_skills_list:
        areas.append(f"Bổ sung kỹ năng: {', '.join(missing_skills_list[:5])}")
    if domain_penalty >= 0.5:
        areas.append(f"Domain không phù hợp: CV thuộc {cv_domain}, JD yêu cầu {jd_domain}")
    if exp_score < 25:
        areas.append("Tích lũy thêm kinh nghiệm thực tế trong đúng ngành")
    if skills_score < 15:
        areas.append("Mở rộng kỹ năng theo yêu cầu JD")
    if career_obj_score < 5:
        areas.append("Rà soát lại mục tiêu nghề nghiệp để phù hợp với JD")

    # Recommendation
    if overall >= 75:
        recommendation = "Ứng viên rất phù hợp. Nên ứng tuyển."
    elif overall >= 55:
        recommendation = "Ứng viên khá phù hợp. Cân nhắc ứng tuyển."
    elif overall >= 35:
        recommendation = "Ứng viên đáp ứng một phần. Cân nhắc nếu ứng tuyển."
    else:
        recommendation = "Ứng viên chưa đáp ứng yêu cầu chính. Không nên ứng tuyển."

    cv_name = cv_data.get("personal_info", {}).get("name", "Unknown")
    job_title = (
        jd_data.get("job_title")
        or (jd_data.get("structured", {}) or {}).get("job_title")
        or "Unknown"
    )

    return {
        "overall_score": overall,
        "detailed_scores": {
            "experience_score": round(exp_score),
            "skills_keyword_score": round(skills_breakdown.get("rule_score", 0.0)),
            "skills_embedding_score": round(skills_breakdown.get("semantic_score", 0.0)),
            "skills_total_score": round(skills_score),
            "education_score": round(edu_score),
            "career_objectives_score": round(career_obj_score),
            "company_fit_score": round(company_score),
        },
        "score_rationale": (
            f"Kinh nghiệm: {exp_score}/50, Kỹ năng: {skills_score}/30, "
            f"Học vấn: {edu_score}/10, Mục tiêu nghề nghiệp: {career_obj_score}/10. "
            f"Tổng: {overall}/100. "
            f"Độ phù hợp công ty: {company_score}/10 (đánh giá riêng)."
        ),
        "domain_analysis": {
            "cv_domain": cv_domain,
            "jd_domain": jd_domain,
            "domain_penalty": round(domain_penalty, 2),
            "skill_overlap": round(skill_overlap, 3),
        },
        "embedding_similarity": round(sim, 4),
        "embedding_status": "ok" if sim > 0 else "failed_or_zero",
        "matched_skills": matched_skills,
        "related_skills": related_skills,
        "missing_skills": missing_skills_list[:15],
        "skills_criteria_breakdown": skills_breakdown,
        "criteria_match_results": criteria_match_results,
        "experience_assessment": exp_rationale,
        "experience_detail": _build_experience_detail(cv_data),
        "main_strengths": main_strengths,
        "areas_for_development": areas,
        "recommendation": recommendation,
        "education_rationale": edu_rationale,
        "career_objectives_rationale": career_obj_rationale,
        "company_fit_rationale": company_rationale,
        "cv_candidate": cv_name,
        "job_position": job_title,
        "matched_at": __import__("datetime").datetime.now().isoformat(),
        "features": {
            "experience": exp_features,
        },
        "evidence": {
            "cv_skills": list(_build_skill_groups(cv_data.get("skills", []))),
            "jd_skills_required": list(_build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_required", [])
            )),
            "jd_skills_preferred": list(_build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_preferred", [])
            )),
            "jd_evaluation_criteria": [
                r.get("name", "") for r in criteria_match_results[:20]
            ],
        },
    }