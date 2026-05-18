# -*- coding: utf-8 -*-
"""
Hybrid CV-JD Scoring Engine — v3.

Fixes over v2:
1. PROJECT DURATION default giảm từ 1.5 năm → 0.25 năm (≈3 tháng thực tế)
2. DOMAIN PENALTY dựa trên industry tag + skill overlap, không chỉ skill overlap
3. EXPERIENCE RATIONALE phản ánh đúng domain mismatch thay vì chỉ seniority
4. EMBEDDING SIMILARITY fallback trả 0.0 thay vì 0.5 để phân biệt fail/thật
5. EDUCATION SCORING thêm major relevance check, không chỉ degree level
6. SOFT SKILL tách riêng khỏi skill scoring chính, không inflate điểm
7. SENIORITY SCORE = 0 nếu domain mismatch nặng (tránh fresher AI = fresher Sales)
"""

import logging
import re
from typing import Dict, List, Tuple

import numpy as np

from app.feature.feature_up_cv.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

logger = logging.getLogger(__name__)

# ── Industry / domain taxonomy ────────────────────────────────────────────────
# Dùng để phát hiện domain mismatch sớm trước khi tính điểm chi tiết.
# Mỗi domain có một tập keywords đặc trưng.
_DOMAIN_TAXONOMY: Dict[str, List[str]] = {
    "tech_ai": [
        "machine learning", "deep learning", "computer vision", "nlp",
        "pytorch", "tensorflow", "opencv", "yolo", "cnn", "transformer",
        "data science", "mlops", "ai engineer", "ml engineer",
        "artificial intelligence", "neural network", "model training",
    ],
    "tech_software": [
        "software engineer", "backend", "frontend", "fullstack", "devops",
        "python", "javascript", "java", "golang", "react", "nodejs",
        "docker", "kubernetes", "aws", "api", "microservice", "database",
    ],
    "tech_data": [
        "data engineer", "data analyst", "data warehouse", "etl",
        "spark", "airflow", "kafka", "sql", "bi", "tableau", "power bi",
        "data pipeline", "analytics",
    ],
    "sales": [
        "sales", "bán hàng", "kinh doanh", "business development",
        "negotiation", "crm", "lead generation", "sales executive",
        "account manager", "customer relationship", "revenue",
        "sales target", "chỉ tiêu doanh số", "khách hàng tiềm năng",
    ],
    "marketing": [
        "marketing", "digital marketing", "seo", "sem", "content",
        "social media", "brand", "campaign", "advertising", "pr",
        "copywriting", "growth hacking",
    ],
    "finance": [
        "finance", "accounting", "tài chính", "kế toán", "audit",
        "tax", "financial analysis", "investment", "banking", "cfa",
        "budget", "forecasting", "p&l",
    ],
    "hr": [
        "human resource", "recruitment", "talent acquisition", "hr",
        "nhân sự", "tuyển dụng", "payroll", "training", "learning development",
        "employee relations", "hrbp",
    ],
    "operations": [
        "operations", "supply chain", "logistics", "vận hành", "lean",
        "six sigma", "warehouse", "procurement", "vendor management",
        "project management", "process improvement",
    ],
}

# ── Skill synonym groups ──────────────────────────────────────────────────────
_SKILL_SYNONYMS: Dict[str, List[str]] = {
    # Vision / AI
    "computervision": [
        "computer vision", "cv", "image processing", "image analysis",
        "opencv", "yolo", "yolov5", "yolov8", "yolov7", "yolov6",
        "cnn", "object detection", "image classification", "image segmentation",
        "face recognition", "ocr", "detectron2", "mmdetection",
        "image recognition", "real-time processing", "video processing",
        "r-cnn", "fast r-cnn", "faster r-cnn", "ssd", "retinanet",
        "vit", "vision transformer", "resnet", "vgg",
    ],
    "nlp": [
        "natural language processing", "text processing", "text mining",
        "llm", "large language model", "language model", "nlp",
        "transformer", "bert", "gpt", "chatbot", "text classification",
        "tokenization", "word embedding", "seq2seq",
    ],
    "deeplearning": [
        "deep learning", "dl", "neural network", "neural networks",
        "pytorch", "tensorflow", "keras", "torch",
    ],
    "machinelearning": [
        "machine learning", "ml", "ml algorithms", "ml models",
        "scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost",
        "gradient boosting", "random forest", "svm", "knn", "k-means",
    ],
    "trainingpipeline": [
        "training pipeline", "data pipeline", "ml pipeline", "data engineering",
        "data preparation", "data augmentation", "feature engineering",
        "model training", "hyperparameter tuning", "model evaluation",
    ],
    "deployment": [
        "deployment", "deploy", "model serving", "model inference",
        "flask", "fastapi", "django", "streamlit", "gradio",
        "web application", "web app", "api",
    ],
    "modeloptimization": [
        "model optimization", "optimization", "quantization", "pruning",
        "onnx", "tensorrt", "trt", "openvino", "mnn", "ncnn",
        "tflite", "tensorflow lite", "torchscript", "model compression",
    ],
    # Backend / DevOps
    "python": ["python", "py", "python3"],
    "javascript": ["javascript", "js", "ecmascript", "node.js", "nodejs"],
    "typescript": ["typescript", "ts"],
    "postgresql": ["postgresql", "postgres", "psql", "postgre"],
    "mongodb": ["mongodb", "mongo", "mongo-db"],
    "redis": ["redis", "redis-cache"],
    "docker": ["docker", "docker-compose", "dockerfile", "containerization"],
    "kubernetes": ["kubernetes", "k8s", "k8", "eks", "gke", "aks", "helm"],
    "aws": ["aws", "amazon web services", "amazon-web-services", "aws-ec2", "aws-s3"],
    "gcp": ["gcp", "google cloud platform", "google cloud", "googlecloud"],
    "azure": ["azure", "microsoft azure", "ms azure", "azure-devops"],
    "git": ["git", "github", "gitlab", "bitbucket", "git-flow", "gitops"],
    "linux": ["linux", "ubuntu", "debian", "centos", "unix", "bash", "shell script"],
    "devops": ["devops", "dev-ops", "sre", "platform engineering", "ci/cd", "cicd"],
    "restapi": ["rest api", "restapi", "rest", "restful", "restful api", "api design"],
    "graphql": ["graphql", "gql", "graphql-api"],
    "kafka": ["kafka", "apache kafka", "msk", "kafka streams"],
    "airflow": ["airflow", "apache airflow"],
    "c++": ["c++", "cpp", "c plus plus"],
    "java": ["java", "spring"],
    "c#": ["c#", "csharp", ".net", "dotnet"],
    # Soft skills — tách riêng, không dùng để inflate technical score
    "problemsolving": [
        "problem solving", "problem-solving", "analytical", "analytical thinking",
        "logical thinking", "kỹ năng giải quyết vấn đề",
    ],
    "communication": [
        "communication", "giao tiếp", "presentation", "public speaking",
        "soft skills", "interpersonal",
    ],
    "agile": ["agile", "scrum", "kanban", "jira", "agile methodology"],
    "projectmanagement": ["project management", "quản lý dự án", "pm"],
    # Sales-specific
    "negotiation": ["negotiation", "đàm phán", "thương lượng", "persuasion", "thuyết phục"],
    "crm": [
        "crm", "customer relationship management", "salesforce", "hubspot",
        "customer relationship", "chăm sóc khách hàng",
    ],
    "salesprospecting": [
        "sales prospecting", "lead generation", "tìm kiếm khách hàng",
        "cold calling", "outbound sales",
    ],
    "businessdevelopment": [
        "business development", "phát triển kinh doanh", "bd",
        "market analysis", "phân tích thị trường", "market research",
    ],
}

# Soft skill keys — không tính vào technical skill score chính
_SOFT_SKILL_KEYS = {
    "communication", "problemsolving", "projectmanagement", "agile",
    "teamwork", "leadership", "creativity", "adaptability",
}


def _normalize_skill_key(skill: str) -> str:
    """Normalize skill string to its canonical group key."""
    s = skill.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    for group_key, aliases in _SKILL_SYNONYMS.items():
        if s == group_key or s in aliases:
            return group_key
        for alias in aliases:
            if s in alias or alias in s:
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


# ── Domain detection ──────────────────────────────────────────────────────────
def _detect_domain(text: str) -> str:
    """
    Phát hiện domain chính từ một đoạn text (CV hoặc JD).
    Trả về domain key có score cao nhất, hoặc 'unknown'.
    """
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for domain, keywords in _DOMAIN_TAXONOMY.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] >= 2 else "unknown"


def _build_cv_text(cv_data: dict) -> str:
    """Gộp toàn bộ nội dung CV thành một chuỗi để detect domain."""
    parts = [
        cv_data.get("objective", ""),
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
        "sales": "business",
        "marketing": "business",
        "finance": "business",
        "hr": "business",
        "operations": "business",
    }
    cv_family = _DOMAIN_FAMILY.get(cv_domain, cv_domain)
    jd_family = _DOMAIN_FAMILY.get(jd_domain, jd_domain)

    if cv_domain == jd_domain:
        # Cùng domain: không phạt
        return 0.0, "Domain khớp."

    if cv_family == jd_family:
        # Cùng họ (vd: tech_ai vs tech_software): phạt nhẹ nếu skill overlap thấp
        if skill_overlap >= 0.25:
            return 0.0, f"Domain gần nhau ({cv_domain} vs {jd_domain}), skill overlap đủ."
        return 0.2, f"Domain gần nhau ({cv_domain} vs {jd_domain}) nhưng skill overlap thấp ({skill_overlap:.0%})."

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
) -> Tuple[float, str]:
    jd_struct = jd_data.get("structured", jd_data)

    # 0. JD yêu cầu bao nhiêu năm kinh nghiệm
    seniority_req = (jd_struct.get("seniority") or "").lower()
    seniority_parts = [p.strip() for p in seniority_req.split("/")]
    seniority_level_map = {
        "intern": 0, "fresher": 0, "junior": 1,
        "mid": 2, "mid-level": 2, "senior": 3,
        "lead": 4, "principal": 4, "expert": 4, "manager": 4,
    }
    req_level = max(
        (seniority_level_map.get(p, 2) for p in seniority_parts),
        default=2,
    )

    years_req_map = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    years_req_raw = jd_struct.get("years_of_experience", "")
    if years_req_raw:
        numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(years_req_raw))]
        years_req = max(numbers) if numbers else years_req_map.get(req_level, 2.0)
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

    # 2. Project years — SEMANTIC MATCHING: dùng embedding thay keyword matching
    project_years, project_relevance_scores, project_descriptions = \
        _semantic_project_relevance(
            cv_data.get("projects", []),
            " ".join([
                " ".join(jd_struct.get("skills_required", [])),
                " ".join(jd_struct.get("skills_preferred", [])),
                " ".join(jd_struct.get("responsibilities", [])),
                " ".join(jd_struct.get("requirements", [])),
            ]),
            embedder,
            threshold=0.30,
        )

    all_exp_years = total_work_years + project_years

    # 3. Years score (0-40)
    if years_req > 0:
        ratio = min(all_exp_years / years_req, 2.0)
        years_score = min(40.0 * ratio, 40.0)
    else:
        years_score = min(all_exp_years * 20.0, 40.0)

    # 4. Seniority match (0-10) — SEMANTIC: dùng embedding thay keyword
    domain_penalty, penalty_reason = _compute_domain_penalty(cv_domain, jd_domain, skill_overlap)

    cv_level = _semantic_seniority_detection(
        exp_titles, project_descriptions, embedder
    )

    # FIX: Không cho seniority score nếu domain khác hoàn toàn
    if domain_penalty >= 0.7:
        seniority_score = 0.0
    elif cv_level >= req_level:
        seniority_score = 10.0
    elif cv_level == req_level - 1:
        seniority_score = 5.0
    elif cv_level > 0:
        seniority_score = 2.0
    else:
        seniority_score = 0.0

    # 5. Bonus — chỉ cộng khi domain gần nhau
    bonus = 0.0
    if domain_penalty < 0.4:
        if total_work_years > 0 and project_years > 0:
            bonus += 8.0
        elif project_years > 0 and skill_overlap >= 0.20:
            avg_rel = (
                sum(project_relevance_scores) / len(project_relevance_scores)
                if project_relevance_scores else 0
            )
            if avg_rel >= 0.65:
                bonus += 5.0
            elif avg_rel >= 0.5:
                bonus += 3.0

    raw_total = years_score + seniority_score + bonus
    total_exp = round(min(raw_total * (1.0 - domain_penalty), 50.0), 2)

    # 6. FIX: Rationale phản ánh đúng domain mismatch
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
    elif seniority_score >= 10:
        rationale = "Kinh nghiệm và cấp độ đạt yêu cầu."
    elif seniority_score >= 5:
        rationale = "Kinh nghiệm gần đạt yêu cầu."
    elif total_work_years > 0 or project_years > 0:
        rationale = "Kinh nghiệm thấp hơn yêu cầu (fresh grad / dự án cá nhân)."
    else:
        rationale = "Chưa có kinh nghiệm làm việc hoặc dự án liên quan."

    return total_exp, rationale


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
        now = datetime.datetime.now().year

        def _extract_year(val):
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
                val = val.strip()
                if val.lower() in ("present", "nay", "hien tai", "now", "hiện tại", "đến nay", "hiện nay"):
                    return now
                m = re.search(r"\d{4}", val)
                if m:
                    return int(m.group())
            return None

        sy = _extract_year(start)
        ey = _extract_year(end)
        if sy and ey:
            return max(0.0, float(ey - sy))
        if sy:
            return max(0.0, float(now - sy))
        return 0.0
    except Exception:
        return 0.0


# ── Skills Scoring (0-30) ─────────────────────────────────────────────────────
def _score_skills(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
    domain_penalty: float,
) -> Tuple[float, List[str], List[str]]:
    """
    Score 0-30:
    - Technical skills chính (CRITICAL/IMPORTANT/BONUS) từ JD
    - Soft skills chỉ được tính nếu JD đánh dấu CRITICAL
    - Embedding similarity boost tối đa +3 (chỉ khi similarity thực, không fallback)
    - Domain penalty cap: nếu penalty cao thì skills score bị giới hạn
    """
    jd_struct = jd_data.get("structured", jd_data)
    skill_importance = jd_struct.get("skill_importance", {})

    # 1. Thu thập CV skills từ mọi nguồn
    cv_skills_raw: List[str] = []
    for s in cv_data.get("skills", []):
        if isinstance(s, str) and s.strip():
            cv_skills_raw.append(s.strip())
    for meta_key in ("technical_skills", "domain_skills"):
        for s in cv_data.get(meta_key, []):
            if isinstance(s, str) and s.strip():
                cv_skills_raw.append(s.strip())
    # FIX: soft_skills tách riêng, chỉ thêm vào nếu JD thực sự cần soft skill CRITICAL
    soft_skills_cv: List[str] = []
    for s in cv_data.get("soft_skills", []):
        if isinstance(s, str) and s.strip():
            soft_skills_cv.append(s.strip())

    for exp in cv_data.get("work_experience", []):
        for hl in exp.get("highlights", []) + exp.get("responsibilities", []):
            cv_skills_raw.extend(_extract_skills_from_text(str(hl)))
    for proj in cv_data.get("projects", []):
        for tech in proj.get("technologies", []):
            if isinstance(tech, str) and tech.strip():
                cv_skills_raw.append(tech.strip())
        cv_skills_raw.extend(_extract_skills_from_text(str(proj.get("name", ""))))
        cv_skills_raw.extend(_extract_skills_from_text(str(proj.get("description", ""))))
        for r in proj.get("highlights", []) + proj.get("responsibilities", []):
            cv_skills_raw.extend(_extract_skills_from_text(str(r)))
    for edu in cv_data.get("education", []):
        edu_text = str(edu.get("description", "")) + " " + str(edu.get("details", ""))
        cv_skills_raw.extend(_extract_skills_from_text(edu_text))

    # Dedup
    seen: set = set()
    deduped: List[str] = []
    for s in cv_skills_raw:
        key = s.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(s.strip())
    cv_skills_raw = deduped

    jd_req = jd_struct.get("skills_required", [])
    jd_pref = jd_struct.get("skills_preferred", [])

    # SEMANTIC MATCHING: thay _build_skill_groups + _skill_group_match
    # Thêm soft skill CV vào matching pool nếu JD có soft skill CRITICAL
    cv_for_match = list(cv_skills_raw)
    jd_critical_soft_keys = {
        _normalize_skill_key(s)
        for s in jd_req
        if skill_importance.get(s, "").upper() == "CRITICAL"
        and _normalize_skill_key(s) in _SOFT_SKILL_KEYS
    }
    if jd_critical_soft_keys:
        cv_for_match.extend(soft_skills_cv)

    matched_groups_raw, missing_groups_raw = _semantic_skill_match(
        cv_for_match, jd_req + jd_pref, embedder, sim_threshold=0.65
    )
    # Convert matched raw skills → group keys (for score calculation)
    matched_groups = [_normalize_skill_key(s) for s in matched_groups_raw]
    matched_groups = list(dict.fromkeys(matched_groups))  # dedup preserve order
    missing_groups = missing_groups_raw  # raw JD skills missing

    # 3. Weighted score theo importance
    def _count_importance(skill_list: list, level: str) -> int:
        return sum(
            1 for s in skill_list
            if skill_importance.get(s, "").upper() == level
        )

    total_critical = _count_importance(jd_req, "CRITICAL") or 1
    total_important = _count_importance(jd_req, "IMPORTANT") or 1
    total_bonus = _count_importance(jd_req + jd_pref, "BONUS") or 1

    matched_critical = sum(
        1 for g in matched_groups
        for s in jd_req
        if skill_importance.get(s, "").upper() == "CRITICAL"
        and _normalize_skill_key(s) == g
    )
    matched_important = sum(
        1 for g in matched_groups
        for s in jd_req
        if skill_importance.get(s, "").upper() == "IMPORTANT"
        and _normalize_skill_key(s) == g
    )
    matched_bonus = sum(
        1 for g in matched_groups
        for s in (jd_req + jd_pref)
        if skill_importance.get(s, "").upper() == "BONUS"
        and _normalize_skill_key(s) == g
    )

    base_score = (
        min(matched_critical * (15.0 / total_critical), 15.0)
        + min(matched_important * (10.0 / total_important), 10.0)
        + min(matched_bonus * (5.0 / total_bonus), 5.0)
    )

    overlap_ratio = len(matched_groups) / max(len(set(_normalize_skill_key(s) for s in jd_req + jd_pref)), 1)
    overlap_bonus = overlap_ratio * 5.0

    # 4. Semantic boost — FIX: chỉ dùng khi embedding thực sự thành công (sim > 0)
    semantic_bonus = 0.0
    sim = 0.0
    try:
        cv_text = embedder.encode_structured_cv(cv_data)
        jd_text = embedder.encode_structured_jd(jd_data)
        cv_emb = embedder.encode(cv_text)
        jd_emb = embedder.encode(jd_text)
        sim_raw = float(np.dot(cv_emb, jd_emb))
        sim = float(np.clip(sim_raw, 0.0, 1.0))
        if sim >= 0.7:
            semantic_bonus = (sim - 0.7) / 0.3 * 3.0
        elif sim >= 0.5:
            semantic_bonus = (sim - 0.5) / 0.2 * 1.5
        else:
            semantic_bonus = 0.0
    except Exception as e:
        logger.warning(f"Embedding failed in skills scoring: {e}")
        sim = 0.0  # FIX: 0.0 thay vì 0.5 để biết là fail
        semantic_bonus = 0.0

    raw_skills = min(base_score + overlap_bonus + semantic_bonus, 30.0)

    # FIX: Cap skills score nếu domain penalty cao
    if domain_penalty >= 0.7:
        max_skills = 8.0   # domain hoàn toàn khác: chỉ cho tối đa 8/30
    elif domain_penalty >= 0.4:
        max_skills = 15.0  # domain lệch: tối đa 15/30
    else:
        max_skills = 30.0
    total_score = round(min(raw_skills, max_skills), 2)

    # 5. Build missing display
    missing_display: List[str] = []
    for g in missing_groups:
        for s in jd_req:
            if _normalize_skill_key(s) == g:
                missing_display.append(s)
                break
        else:
            for s in jd_pref:
                if _normalize_skill_key(s) == g:
                    missing_display.append(s)
                    break

    return total_score, matched_groups, missing_display, sim


# ════════════════════════════════════════════════════════════════════════════
# SEMANTIC MATCHING — thay thế keyword matching bằng embedding similarity
# ════════════════════════════════════════════════════════════════════════════

# Domain anchor descriptions — mô tả semantic cho mỗi domain
_DOMAIN_ANCHORS = {
    "tech_ai": "AI Machine Learning Deep Learning Computer Vision NLP Neural Network Model Training MLOps",
    "tech_software": "Software Engineer Backend Frontend Fullstack DevOps Software Development API Database Microservice",
    "tech_data": "Data Engineer Data Analyst ETL Data Pipeline Analytics Business Intelligence SQL Data Warehouse",
    "sales": "Sales Business Development Account Management CRM Negotiation Lead Generation Revenue Customer Relationship B2B B2C",
    "marketing": "Digital Marketing SEO SEM Content Marketing Social Media Brand Campaign Advertising Growth",
    "finance": "Finance Accounting Financial Analysis Investment Banking Audit Tax Budgeting CFA Risk Management",
    "hr": "Human Resources Recruitment Talent Acquisition HRBP Training Employee Relations Payroll L&D",
    "operations": "Operations Supply Chain Logistics Procurement Process Improvement Lean Six Sigma Project Management",
}

# Seniority anchor descriptions
_SENIORITY_ANCHORS = {
    0: "Internship Fresher entry level no experience trainee beginner intern junior trainee",
    1: "Junior Developer Junior Engineer Entry level with 1-2 years experience junior software engineer",
    2: "Mid-level Developer Software Engineer with 2-5 years experience mid senior independent contributor",
    3: "Senior Developer Senior Engineer Lead with 5+ years experience senior specialist expert technical lead",
    4: "Principal Lead Manager Director Head Chief with 7+ years experience principal architect manager director chief",
}

# Cache cho domain/seniority embeddings — init lần đầu khi dùng
_domain_anchors_embs: Dict[str, np.ndarray] = {}
_seniority_anchors_embs: Dict[int, np.ndarray] = {}


def _ensure_anchor_embs(embedder: EmbeddingService) -> None:
    """Pre-compute và cache domain/seniority anchor embeddings."""
    if not _domain_anchors_embs:
        for key, desc in _DOMAIN_ANCHORS.items():
            _domain_anchors_embs[key] = embedder.encode(desc, normalize=True)
    if not _seniority_anchors_embs:
        for level, desc in _SENIORITY_ANCHORS.items():
            _seniority_anchors_embs[level] = embedder.encode(desc, normalize=True)


def _semantic_skill_match(
    cv_skills: List[str],
    jd_skills: List[str],
    embedder: EmbeddingService,
    sim_threshold: float = 0.65,
) -> Tuple[List[str], List[str]]:
    """
    Semantic skill matching: so sánh từng skill CV với từng skill JD bằng embedding.

    Returns (matched_skills, missing_skills) — danh sách JD skills được match/missing.
    Một JD skill được coi là matched nếu có ít nhất 1 CV skill với similarity >= sim_threshold.
    """
    if not jd_skills:
        return [], []
    if not cv_skills:
        return [], list(jd_skills)

    # Batch encode tất cả skills cùng lúc (hiệu quả hơn encode từng cái)
    all_texts = cv_skills + jd_skills
    embs = embedder.encode_batch(all_texts, normalize=True)
    cv_embs = embs[: len(cv_skills)]
    jd_embs = embs[len(cv_skills) :]

    # Pairwise similarity matrix (cv × jd)
    sim_matrix = np.dot(cv_embs, jd_embs.T)

    matched: List[str] = []
    missing: List[str] = []
    for j, jd_skill in enumerate(jd_skills):
        max_sim = float(sim_matrix[:, j].max()) if cv_embs.size else 0.0
        if max_sim >= sim_threshold:
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    return matched, missing


def _semantic_domain_detection(
    text: str,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> str:
    """
    Semantic domain detection: embed text rồi so sánh cosine với domain anchors.

    Trả về domain key có similarity cao nhất, hoặc 'unknown'.
    """
    _ensure_anchor_embs(embedder)
    if not text.strip():
        return "unknown"

    text_emb = embedder.encode(text, normalize=True)
    scores: Dict[str, float] = {}
    for key, anchor_emb in _domain_anchors_embs.items():
        scores[key] = float(np.dot(text_emb, anchor_emb))

    best_domain = max(scores, key=lambda d: scores[d])
    return best_domain if scores[best_domain] >= threshold else "unknown"


def _semantic_project_relevance(
    projects: List[dict],
    jd_text: str,
    embedder: EmbeddingService,
    threshold: float = 0.30,
) -> Tuple[float, List[float], List[str]]:
    """
    Semantic project relevance: embed project description + name rồi so sánh với JD text.

    Returns (total_weighted_years, list_of_relevance_scores, list_of_descriptions).
    total_weighted_years = sum(proj_dur * relevance) trên tất cả projects.
    relevance được tính bằng max similarity giữa project text và JD text.
    """
    if not projects:
        return 0.0, [], []

    # Parse durations
    durations: List[float] = []
    for proj in projects:
        dur_str = str(proj.get("duration", ""))
        m = re.search(r"(\d+(?:\.\d+)?)\s*(month|year)", dur_str, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            durations.append(val / 12 if "month" in m.group(2).lower() else val)
        else:
            durations.append(0.25)  # ≈ 3 tháng mặc định

    # Build project texts
    proj_texts: List[str] = []
    for proj in projects:
        name = proj.get("name", "")
        desc = proj.get("description", "")
        techs = " ".join(proj.get("technologies", []))
        proj_texts.append(f"{name}. {desc}. Technologies: {techs}")

    # Encode all
    jd_emb = embedder.encode(jd_text, normalize=True)
    proj_embs = embedder.encode_batch(proj_texts, normalize=True)

    # Similarity vs JD
    relevances: List[float] = []
    for i in range(len(projects)):
        sim = float(np.dot(proj_embs[i], jd_emb))
        relevances.append(max(0.0, sim))

    # Weighted years
    weighted_years = sum(durations[i] * relevances[i] for i in range(len(projects)))

    return weighted_years, relevances, proj_texts


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

    cv_emb = embedder.encode(cv_text, normalize=True)
    best_level = 0
    best_sim = -1.0
    for level, anchor_emb in _seniority_anchors_embs.items():
        sim = float(np.dot(cv_emb, anchor_emb))
        if sim > best_sim:
            best_sim = sim
            best_level = level

    return best_level


def _semantic_major_relevance(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> bool:
    """
    Semantic major relevance: embed JD field description + major text, so sánh similarity.

    Returns True nếu ít nhất 1 education entry có similarity >= threshold với JD field.
    """
    if not cv_education:
        return False

    # Build JD field description
    jd_struct = jd_data.get("structured", jd_data)
    jd_field_text = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        " ".join(jd_struct.get("requirements", [])),
        " ".join(jd_struct.get("responsibilities", [])),
    ]))

    if not jd_field_text.strip():
        return False

    # Build education texts
    edu_texts: List[str] = []
    for edu in cv_education:
        parts = [
            edu.get("degree", ""),
            edu.get("major", ""),
            edu.get("school", ""),
            edu.get("description", ""),
        ]
        edu_texts.append(" ".join(filter(None, parts)))

    # Encode all
    jd_emb = embedder.encode(jd_field_text, normalize=True)
    edu_embs = embedder.encode_batch(edu_texts, normalize=True)

    # Check if any education matches JD field
    for i in range(len(cv_education)):
        sim = float(np.dot(edu_embs[i], jd_emb))
        if sim >= threshold:
            return True

    return False


# ════════════════════════════════════════════════════════════════════════════
# END SEMANTIC MATCHING
# ════════════════════════════════════════════════════════════════════════════


def _extract_skills_from_text(text: str) -> List[str]:
    patterns = [
        r"\b(Python|JavaScript|TypeScript|Java|C\+\+|C#|Go|Rust|Swift|Kotlin|Ruby|PHP|Scala|Shell|R)\b",
        r"\b(React|Vue|Angular|Node\.js|Django|Flask|FastAPI|Spring|Laravel|Rails)\b",
        r"\b(TensorFlow|PyTorch|Keras|Scikit-learn|Pandas|Numpy|Spark|Hadoop|Kafka|Airflow)\b",
        r"\b(PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Cassandra|Neo4j|SQLite|DynamoDB)\b",
        r"\b(Docker|Kubernetes|Terraform|Ansible|Jenkins|CircleCI|GitHubActions)\b",
        r"\b(AWS|Azure|GCP|Google\s*Cloud)\b",
        r"\b(OpenCV|Open-CV|CUDA|TensorRT|ONNX|YOLO|OCR|LSTM|CNN|Transformer|YOLOv8)\b",
        r"\b(REST|GraphQL|gRPC|API)\b",
        r"\b(HTML5|CSS3|SASS|LESS|Bootstrap|Tailwind)\b",
        r"\b(Machine Learning|Deep Learning|NLP|Computer Vision|MLOps|AI)\b",
        r"\b(Agile|Scrum|Kanban|Jira|Git|Linux)\b",
    ]
    found: set = set()
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            skill = m.group(0).strip()
            if len(skill) >= 2:
                found.add(skill)
    return list(found)


# ── Education Scoring (0-10) ──────────────────────────────────────────────────
def _score_education(
    cv_data: dict,
    jd_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
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

    # SEMANTIC MATCHING: thay keyword-based major relevance bằng embedding similarity
    cv_major_match = _semantic_major_relevance(
        cv_data.get("education", []), jd_data, embedder, threshold=0.40
    )

    cert_count = 0
    cv_text_lower = str(cv_data).lower()
    cert_keywords = [
        "certification", "certificate", "aws certified", "google certified",
        "azure certified", "cisco", "oracle", "salesforce", "pmp", "scrum master",
        "kaggle", "deep learning specialization", "google data analytics",
    ]
    for kw in cert_keywords:
        if kw in cv_text_lower:
            cert_count += 1

    if req_degree > 0:
        if cv_degree >= req_degree:
            base = 6.0 if cv_major_match else 3.5
        else:
            base = max(0.0, (cv_degree / max(req_degree, 1)) * 4.0)
            if cv_major_match:
                base += 1.0
    else:
        base = 4.0 if cv_major_match else 2.5

    score = min(base + min(cert_count, 3) * 0.8, 10.0)

    major_note = "Ngành học phù hợp." if cv_major_match else "Ngành học không liên quan trực tiếp."
    rationale = f"Trình độ: {cv_degree}/5. {major_note}"
    if cert_count > 0:
        rationale += f" Có {cert_count} chứng chỉ liên quan."

    return round(min(score, 10.0), 2), rationale


# ── Company Fit Scoring (0-10) ────────────────────────────────────────────────
def _score_company_fit(
    cv_data: dict,
    company_data: dict,
    embedder: EmbeddingService,
) -> Tuple[float, str]:
    if not company_data:
        return 0.0, "Không có dữ liệu công ty."

    cv_skills = cv_data.get("skills", [])
    company_skills = company_data.get("key_skills", []) + company_data.get("technologies", [])
    cv_groups = _build_skill_groups(cv_skills)
    comp_groups = _build_skill_groups(company_skills)
    matched, _ = _skill_group_match(cv_groups, comp_groups)

    overlap_ratio = len(matched) / max(len(comp_groups), 1)
    skills_score = min(overlap_ratio * 6.0, 6.0)

    semantic_bonus = 0.0
    try:
        cv_emb = embedder.encode(embedder.encode_structured_cv(cv_data))
        company_text = " ".join(filter(None, [
            company_data.get("description", ""),
            company_data.get("mission", ""),
            company_data.get("company_culture", ""),
        ]))
        if company_text.strip():
            comp_emb = embedder.encode(company_text)
            sim = float(np.clip(np.dot(cv_emb, comp_emb), 0.0, 1.0))
            semantic_bonus = min(sim * 4.0, 4.0)
    except Exception as e:
        logger.warning(f"Embedding failed in company fit: {e}")

    score = min(skills_score + semantic_bonus, 10.0)
    rationale = f"Kỹ năng trùng công ty: {len(matched)}/{len(comp_groups)} nhóm."
    return round(score, 2), rationale


# ── Main Entry Point ──────────────────────────────────────────────────────────
def calculate_hybrid_score(
    cv_data: dict,
    jd_data: dict,
    company_data: dict = None,
    cv_embedding: np.ndarray = None,
    jd_embedding: np.ndarray = None,
) -> dict:
    """
    Hybrid CV-JD scoring v3.

    Scoring formula (max = 100):
        experience_score  : 0-50  — work years + seniority + domain penalty
        skills_score      : 0-30  — CRITICAL/IMPORTANT/BONUS + embedding boost + domain cap
        education_score   : 0-10  — degree level + major relevance + certifications
        company_fit_score : 0-10  — skill overlap với company profile

    Domain penalty được tính một lần, áp dụng xuyên suốt exp và skills.
    """
    try:
        embedder = get_embedding_service()

        # Detect domain sớm — dùng cho penalty toàn hệ thống
        # SEMANTIC MATCHING: dùng embedding thay keyword cho domain detection
        cv_text_full = _build_cv_text(cv_data)
        jd_text_full = _build_jd_text(jd_data)
        cv_domain = _semantic_domain_detection(cv_text_full, embedder, threshold=0.40)
        jd_domain = _semantic_domain_detection(jd_text_full, embedder, threshold=0.40)

        # SEMANTIC MATCHING: skill overlap dùng embedding similarity thay group matching
        jd_struct = jd_data.get("structured", jd_data)
        jd_skills_flat = [
            s for s in jd_struct.get("skills_required", []) + jd_struct.get("skills_preferred", [])
            if isinstance(s, str) and s.strip()
        ]
        cv_skills_flat = list({
            s.strip()
            for key in ("skills", "technical_skills", "domain_skills")
            for s in cv_data.get(key, [])
            if isinstance(s, str) and s.strip()
        })
        for proj in cv_data.get("projects", []):
            cv_skills_flat.extend(t for t in proj.get("technologies", []) if isinstance(t, str))

        # Semantic skill overlap: avg max-similarity across JD skills
        if jd_skills_flat:
            all_texts = cv_skills_flat + jd_skills_flat
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[: len(cv_skills_flat)]
            jd_embs = embs[len(cv_skills_flat) :]
            if jd_embs.size and cv_embs.size:
                sim_matrix = np.dot(cv_embs, jd_embs.T)
                max_sims = sim_matrix.max(axis=0)
                skill_overlap = float(max_sims.mean())
            else:
                skill_overlap = 0.0
        else:
            skill_overlap = 0.0

        domain_penalty, _ = _compute_domain_penalty(cv_domain, jd_domain, skill_overlap)

        exp_score, exp_rationale = _score_experience(
            cv_data, jd_data, cv_domain, jd_domain, skill_overlap, embedder
        )
        skills_score, matched_skills, missing_skills, sim = _score_skills(
            cv_data, jd_data, embedder, domain_penalty
        )
        edu_score, edu_rationale = _score_education(cv_data, jd_data, embedder)
        company_score, company_rationale = _score_company_fit(cv_data, company_data, embedder)

        overall = round(min(exp_score + skills_score + edu_score + company_score, 100.0))

    except Exception as e:
        logger.error(f"Scoring failed, using fallback: {e}")
        embedder = get_embedding_service()
        sim = 0.0
        try:
            cv_emb = embedder.encode(embedder.encode_structured_cv(cv_data))
            jd_emb = embedder.encode(embedder.encode_structured_jd(jd_data))
            sim = round(float(np.clip(np.dot(cv_emb, jd_emb), 0.0, 1.0)), 4)
        except Exception as inner_e:
            logger.error(f"Fallback embedding also failed: {inner_e}")
            sim = 0.0
        exp_score = skills_score = edu_score = company_score = overall = 0
        exp_rationale = "Không thể tính điểm kinh nghiệm."
        matched_skills = []
        missing_skills = []
        edu_rationale = "Không thể tính điểm học vấn."
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
    if company_score >= 7:
        main_strengths.append("Phù hợp với văn hóa và kỹ năng công ty")

    # Build areas
    areas: List[str] = []
    if missing_skills:
        areas.append(f"Bổ sung kỹ năng: {', '.join(missing_skills[:5])}")
    if domain_penalty >= 0.5:
        areas.append(f"Domain không phù hợp: CV thuộc {cv_domain}, JD yêu cầu {jd_domain}")
    if exp_score < 25:
        areas.append("Tích lũy thêm kinh nghiệm thực tế trong đúng ngành")
    if skills_score < 15:
        areas.append("Mở rộng kỹ năng theo yêu cầu JD")

    # Recommendation
    if overall >= 75:
        recommendation = "Ứng viên rất phù hợp. Nên mời phỏng vấn."
    elif overall >= 55:
        recommendation = "Ứng viên khá phù hợp. Cân nhắc phỏng vấn."
    elif overall >= 35:
        recommendation = "Ứng viên đáp ứng một phần. Cân nhắc nếu thiếu ứng viên khác."
    else:
        recommendation = "Ứng viên chưa đáp ứng yêu cầu chính. Không khuyến khích tuyển."

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
            "skills_keyword_score": round(skills_score * 0.6),
            "skills_embedding_score": round(skills_score * 0.4),
            "skills_total_score": round(skills_score),
            "education_score": round(edu_score),
            "company_fit_score": round(company_score),
        },
        "score_rationale": (
            f"Kinh nghiệm: {exp_score}/50, Kỹ năng: {skills_score}/30, "
            f"Học vấn: {edu_score}/10, Công ty: {company_score}/10. "
            f"Tổng: {overall}/100."
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
        "related_skills": [],
        "missing_skills": missing_skills[:15],
        "experience_assessment": exp_rationale,
        "experience_detail": _build_experience_detail(cv_data),
        "main_strengths": main_strengths,
        "areas_for_development": areas,
        "recommendation": recommendation,
        "education_rationale": edu_rationale,
        "company_fit_rationale": company_rationale,
        "cv_candidate": cv_name,
        "job_position": job_title,
        "matched_at": __import__("datetime").datetime.now().isoformat(),
        "evidence": {
            "cv_skills": list(_build_skill_groups(cv_data.get("skills", []))),
            "jd_skills_required": list(_build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_required", [])
            )),
            "jd_skills_preferred": list(_build_skill_groups(
                (jd_data.get("structured", {}) or {}).get("skills_preferred", [])
            )),
        },
    }