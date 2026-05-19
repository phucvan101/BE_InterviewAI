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
import re
from typing import Any, Dict, List, Tuple

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
        "sales": "business",
        "marketing": "business",
        "finance": "business",
        "hr": "business",
        "operations": "business",
    }
    cv_family = _DOMAIN_FAMILY.get(cv_domain, cv_domain)
    jd_family = _DOMAIN_FAMILY.get(jd_domain, jd_domain)

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
            " ".join([
                " ".join(jd_struct.get("skills_required", [])),
                " ".join(jd_struct.get("skills_preferred", [])),
                " ".join(jd_struct.get("responsibilities", [])),
                " ".join(jd_struct.get("requirements", [])),
            ]),
            embedder,
            threshold=0.30,
            default_duration=default_proj_dur,
        )

    all_exp_years = total_work_years + project_years

    # 3. Years score (0-40)
    # Intern/Fresher: years_req thường = 1 hoặc 0.
    # Khi years_req = 0 (pure intern), mọi CV có project đều đủ điều kiện → cho điểm tối đa.
    # Khi years_req = 1, project 6 tháng × relevance 0.6 ≈ 0.5 năm → ratio 0.5 → vẫn hợp lý.
    if is_entry_level and years_req == 0:
        # JD không yêu cầu năm kinh nghiệm → có project/work là đủ
        # Guard: chỉ cho điểm cao khi thực sự có bằng chứng (project hoặc work)
        has_evidence = project_years > 0 or total_work_years > 0
        has_any_project = len(cv_data.get("projects", [])) > 0
        if has_evidence:
            years_score = 40.0  # Cho phép đạt điểm max nếu project có relevance
        elif has_any_project:
            # Có project nhưng relevance quá thấp → project_years = 0
            years_score = 20.0  # Tồn tại nhưng không liên quan
        else:
            years_score = 10.0  # Không có gì
    elif years_req > 0:
        ratio = min(all_exp_years / years_req, 2.0)
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

    if domain_penalty >= 0.7:
        seniority_score = 0.0
    elif is_entry_level:
        # Intern/Fresher JD: có project relevant là đủ seniority match
        avg_rel = (
            sum(project_relevance_scores) / len(project_relevance_scores)
            if project_relevance_scores else 0.0
        )
        if total_work_years > 0:
            seniority_score = 10.0  # có work experience thì full marks
        elif avg_rel >= 0.50:
            seniority_score = 8.0   # project relevant tốt
        elif avg_rel >= 0.30:
            seniority_score = 5.0   # project có liên quan
        else:
            seniority_score = 2.0   # có project nhưng không relevant
    elif cv_level >= req_level:
        seniority_score = 10.0
    elif cv_level == req_level - 1:
        seniority_score = 5.0
    elif cv_level > 0:
        seniority_score = 2.0
    else:
        seniority_score = 0.0

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
            # Intern/Fresher: threshold thấp hơn vì project là primary evidence
            rel_threshold_high = 0.55 if is_entry_level else 0.65
            rel_threshold_mid = 0.35 if is_entry_level else 0.50
            if avg_rel >= rel_threshold_high:
                bonus += 5.0
            elif avg_rel >= rel_threshold_mid:
                bonus += 3.0

    raw_total = years_score + seniority_score + bonus
    total_exp = round(min(raw_total * (1.0 - domain_penalty), 50.0), 2)

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
                    return int(m.group()), 1
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


def _criterion_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _coerce_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_importance(value: Any, fallback: str = "IMPORTANT") -> str:
    level = str(value or "").strip().upper()
    return level if level in {"CRITICAL", "IMPORTANT", "BONUS"} else fallback


def _criterion_weight(importance: str) -> float:
    return {"CRITICAL": 3.0, "IMPORTANT": 2.0, "BONUS": 1.0}.get(
        _normalize_importance(importance), 2.0
    )


def _criterion_id(index: int, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:32]
    return f"crit_{index:02d}" + (f"_{slug}" if slug else "")


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
            all_texts = cv_evidence + criterion_texts
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[: len(cv_evidence)]
            criterion_embs = embs[len(cv_evidence):]
            if cv_embs.size and criterion_embs.size:
                sim_matrix = np.dot(cv_embs, criterion_embs.T)
        except Exception as e:
            logger.warning(f"Criteria evidence embedding failed: {e}")

    results: List[Dict[str, Any]] = []
    for j, criterion in enumerate(criteria):
        importance = _normalize_importance(criterion.get("importance"))
        status, evidence = _find_exact_criterion_evidence(criterion, cv_skill_pool)
        best_sim = 1.0 if status else 0.0

        if not status and sim_matrix is not None:
            best_idx = int(sim_matrix[:, j].argmax())
            best_sim = float(np.clip(sim_matrix[best_idx, j], 0.0, 1.0))
            evidence = cv_evidence[best_idx]
            category = str(criterion.get("category", "")).lower()
            source = str(criterion.get("source", "")).lower()
            is_atomic_skill = source.startswith("skills_") or category in {"skill", "technical_skill", "tool"}
            match_threshold = 0.70 if is_atomic_skill else 0.66
            related_threshold = 0.55 if is_atomic_skill else 0.50
            if best_sim >= match_threshold:
                status = "semantic_match"
            elif best_sim >= related_threshold:
                status = "related_only"
            else:
                status = "missing"
                evidence = ""

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
            "cv_evidence": evidence,
            "question_intent": criterion.get("question_intent", "validate_depth"),
        })

    return results, cv_skill_pool


def _compute_skill_overlap_ratio(
    cv_skills: List[str],
    jd_skills: List[str],
    embedder: EmbeddingService,
    threshold: float = 0.72,
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
            all_texts = cv_skills + unmatched
            embs = embedder.encode_batch(all_texts, normalize=True)
            cv_embs = embs[: len(cv_skills)]
            jd_embs = embs[len(cv_skills):]
            if cv_embs.size and jd_embs.size:
                sim_matrix = np.dot(cv_embs, jd_embs.T)
                max_sims = sim_matrix.max(axis=0)
                matched += int(np.sum(max_sims >= threshold))
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
            "criteria_count": 0,
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

    # Domain taxonomy chỉ là phụ trợ: chỉ cap nếu domain penalty cao và coverage thực sự thấp.
    max_skills = 30.0
    if domain_penalty >= 0.7 and coverage_ratio < 0.35:
        max_skills = 12.0
    elif domain_penalty >= 0.4 and coverage_ratio < 0.25:
        max_skills = 18.0

    total_score = round(min(raw_skills, max_skills), 2)
    cap_factor = total_score / raw_skills if raw_skills > 0 else 1.0
    rule_score = round(min(total_score, (exact_weight / total_weight) * 30.0 * cap_factor), 2)
    semantic_score = round(max(0.0, total_score - rule_score), 2)

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
    # Loại criteria category='education' khỏi missing_skills:
    # Các yêu cầu học vấn ("Currently a 3rd/4th year student...") đã được tính
    # trong education_score riêng, không nên xuất hiện trong danh sách skills thiếu.
    _EDUCATION_CATEGORIES = {"education", "degree", "academic"}
    missing_display = [
        r["name"]
        for r in criteria_results
        if r["match_status"] == "missing"
        and r["importance"] != "BONUS"
        and str(r.get("category", "")).lower() not in _EDUCATION_CATEGORIES
    ]
    missing_display.extend(
        r["name"]
        for r in criteria_results
        if r["match_status"] == "missing"
        and r["importance"] == "BONUS"
        and str(r.get("category", "")).lower() not in _EDUCATION_CATEGORIES
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
            cv_emb = embedder.encode(cv_text)
            jd_emb = embedder.encode(jd_text)
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
        "rule_score": rule_score,
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

# Cache SIM calibration (SIM_MIN, SIM_MAX) theo model name
# Tránh 4 lần encode mỗi request trong _score_career_objectives
_sim_calibration_cache: Dict[str, tuple] = {}


def _ensure_anchor_embs(embedder: EmbeddingService) -> None:
    """Pre-compute và cache domain/seniority anchor embeddings."""
    if not _domain_anchors_embs:
        for key, desc in _DOMAIN_ANCHORS.items():
            _domain_anchors_embs[key] = embedder.encode(desc, normalize=True)
    if not _seniority_anchors_embs:
        for level, desc in _SENIORITY_ANCHORS.items():
            _seniority_anchors_embs[level] = embedder.encode(desc, normalize=True)


def _get_sim_calibration(embedder: EmbeddingService) -> tuple:
    """
    Trả về (SIM_MIN, SIM_MAX) được calibrate theo embedding model hiện tại.

    Kết quả được cache theo model_name — chỉ thực hiện 4 lần encode một lần duy nhất
    trong toàn bộ lifecycle ứng dụng. Các lần gọi sau trả về cached value O(1).

    SIM_MIN: similarity của 2 câu hoàn toàn không liên quan (lower bound).
    SIM_MAX: similarity của 2 câu gần giống nhau (upper bound).
    Dùng để rescale raw cosine similarity → [0, 10] score.
    """
    _SIM_MIN_DEFAULT = 0.25
    _SIM_MAX_DEFAULT = 0.65
    # Key cache: dùng model_name nếu có, fallback về id(embedder)
    cache_key = str(getattr(embedder, "model_name", None) or id(embedder))
    if cache_key in _sim_calibration_cache:
        return _sim_calibration_cache[cache_key]
    try:
        _unrelated_a = embedder.encode("software engineer python backend", normalize=True)
        _unrelated_b = embedder.encode("chef cooking restaurant food", normalize=True)
        _identical_a = embedder.encode("machine learning engineer AI", normalize=True)
        _identical_b = embedder.encode("machine learning engineer artificial intelligence", normalize=True)
        sim_low = float(np.clip(np.dot(_unrelated_a, _unrelated_b), 0.0, 1.0))
        sim_high = float(np.clip(np.dot(_identical_a, _identical_b), 0.0, 1.0))
        if sim_high - sim_low > 0.1:
            result = (sim_low, sim_high)
        else:
            result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)
    except Exception:
        result = (_SIM_MIN_DEFAULT, _SIM_MAX_DEFAULT)
    _sim_calibration_cache[cache_key] = result
    logger.debug(f"SIM calibration cached for model '{cache_key}': min={result[0]:.3f}, max={result[1]:.3f}")
    return result


def _semantic_skill_match(
    cv_skills: List[str],
    jd_skills: List[str],
    embedder: EmbeddingService,
    sim_threshold: float = 0.65,
) -> Tuple[List[str], List[str]]:
    """
    Pure semantic skill matching — không dùng keyword/synonym normalization.

    Mỗi JD skill được embed thành vector, so sánh cosine với TẤT CẢ CV skills.
    Nếu có bất kỳ CV skill nào similarity >= sim_threshold → JD skill được coi là matched.

    Ưu điểm so với keyword matching:
    - "YOLOv8" match với "Object Detection" dù không cùng từ
    - "Customer Relationship" match với "CRM" dù viết khác
    - "Negotiation" KHÔNG match với "CNN" dù cùng 3 chữ cái
    - Cover mọi ngành nghề mà không cần maintain synonym list

    Returns (matched_jd_skills, missing_jd_skills) — original JD skill strings.
    """
    if not jd_skills:
        return [], []
    if not cv_skills:
        return [], list(jd_skills)

    try:
        # Batch encode tất cả cùng lúc — hiệu quả hơn encode từng cái
        all_texts = cv_skills + jd_skills
        embs = embedder.encode_batch(all_texts, normalize=True)
        cv_embs = embs[: len(cv_skills)]   # shape: (n_cv, dim)
        jd_embs = embs[len(cv_skills):]    # shape: (n_jd, dim)

        # Ma trận similarity: hàng = CV skill, cột = JD skill
        # sim_matrix[i, j] = cosine(cv_skills[i], jd_skills[j])
        sim_matrix = np.dot(cv_embs, jd_embs.T)  # shape: (n_cv, n_jd)

        matched: List[str] = []
        missing: List[str] = []

        for j, jd_skill in enumerate(jd_skills):
            # Max similarity giữa JD skill này với tất cả CV skills
            best_cv_sim = float(sim_matrix[:, j].max())
            if best_cv_sim >= sim_threshold:
                matched.append(jd_skill)
            else:
                missing.append(jd_skill)

        return matched, missing

    except Exception as e:
        logger.warning(f"_semantic_skill_match embedding failed: {e}. Fallback: all missing.")
        return [], list(jd_skills)


def _semantic_domain_detection(
    text: str,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> str:
    """
    Semantic domain detection: embed text rồi so sánh cosine với domain anchors.
    Falls back to keyword-based detection if semantic score is too low.
    """
    _ensure_anchor_embs(embedder)
    if not text.strip():
        return "unknown"

    text_emb = embedder.encode(text, normalize=True)
    scores: Dict[str, float] = {}
    for key, anchor_emb in _domain_anchors_embs.items():
        scores[key] = float(np.dot(text_emb, anchor_emb))

    best_domain = max(scores, key=lambda d: scores[d])
    best_score = scores[best_domain]

    # Fallback: if semantic score too low, try keyword matching
    if best_score < threshold:
        keyword_domain = _detect_domain(text)
        if keyword_domain != "unknown":
            return keyword_domain

    return best_domain if best_score >= threshold else "unknown"


def _semantic_project_relevance(
    projects: List[dict],
    jd_text: str,
    embedder: EmbeddingService,
    threshold: float = 0.30,
    default_duration: float = 0.25,
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
        elif proj.get("start") or proj.get("end"):
            parsed_duration = _parse_years(proj.get("start", ""), proj.get("end", ""))
            durations.append(parsed_duration if parsed_duration > 0 else default_duration)
        else:
            durations.append(default_duration)  # caller quyết định default

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

    # Collect JD keywords for fallback boost from jd_text
    jd_keywords = [w.lower() for w in re.split(r'\W+', jd_text) if len(w) > 2]

    # Similarity vs JD
    relevances: List[float] = []
    for i in range(len(projects)):
        sim = float(np.dot(proj_embs[i], jd_emb))
        
        # Keyword Boost: giúp vượt qua khác biệt ngôn ngữ (Eng CV vs Viet JD)
        proj_text_lower = proj_texts[i].lower()
        match_count = sum(1 for kw in jd_keywords if kw in proj_text_lower)
        if match_count > 0:
            sim = min(sim + (match_count * 0.08), 1.0)
            
        if sim < threshold:
            relevances.append(0.0)
        else:
            # Rescale above threshold so unrelated projects do not create "virtual years".
            relevances.append(float(np.clip((sim - threshold) / max(1.0 - threshold, 1e-6), 0.0, 1.0)))

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


def _major_keyword_match(cv_education: List[dict], jd_data: dict) -> bool:
    """
    Keyword-based fallback cho major relevance.

    Dùng khi semantic embedding không đủ độ tin cậy (ví dụ: major text quá ngắn
    như "Artificial Intelligence" → embedding không đủ dense để vượt threshold 0.40
    khi so với JD text rất dài).

    Chiến lược: so sánh trực tiếp các từ trong major/degree với JD title + industry.
    Sử dụng các nhóm từ đồng nghĩa ngành học phổ biến.
    """
    _MAJOR_GROUPS: Dict[str, List[str]] = {
        "tech_ai": [
            "artificial intelligence", "ai", "machine learning", "deep learning",
            "computer vision", "data science", "nlp", "trí tuệ nhân tạo",
            "học máy", "khoa học dữ liệu",
        ],
        "tech_cs": [
            "computer science", "khoa học máy tính", "information technology",
            "công nghệ thông tin", "cntt", "software engineering",
            "kỹ thuật phần mềm", "information systems", "hệ thống thông tin",
            "computing", "informatics", "tin học",
        ],
        "tech_data": [
            "data engineering", "data analytics", "statistics", "thống kê",
            "mathematics", "toán học", "applied mathematics", "toán ứng dụng",
        ],
        "tech_electronics": [
            "electronics", "electrical engineering", "điện tử", "kỹ thuật điện",
            "embedded systems", "robotics", "robot",
        ],
    }
    _JD_DOMAIN_GROUPS: Dict[str, List[str]] = {
        "tech_ai": [
            "ai", "artificial intelligence", "machine learning", "deep learning",
            "computer vision", "data science", "nlp", "intern", "engineer",
        ],
        "tech_cs": [
            "software", "backend", "frontend", "fullstack", "developer",
            "engineer", "devops", "web", "mobile",
        ],
        "tech_data": [
            "data", "analytics", "analyst", "bi", "etl", "warehouse",
        ],
        "tech_electronics": [
            "embedded", "iot", "robotics", "hardware", "electronics",
        ],
    }

    jd_struct = jd_data.get("structured", jd_data)
    jd_title = (
        (jd_struct.get("job_title") or jd_data.get("job_title") or "") + " " +
        (jd_struct.get("industry") or "")
    ).lower()

    # Detect JD domain từ title
    jd_domains: set = set()
    for domain, kws in _JD_DOMAIN_GROUPS.items():
        if any(kw in jd_title for kw in kws):
            jd_domains.add(domain)

    if not jd_domains:
        return False  # Không detect được JD domain → không thể kết luận

    for edu in cv_education:
        major_text = (
            (edu.get("major") or "") + " " + (edu.get("degree") or "")
        ).lower()
        if not major_text.strip():
            continue
        # Detect major domain
        for domain, kws in _MAJOR_GROUPS.items():
            if any(kw in major_text for kw in kws):
                if domain in jd_domains:
                    return True  # Major domain khớp JD domain
    return False


def _semantic_major_relevance(
    cv_education: List[dict],
    jd_data: dict,
    embedder: EmbeddingService,
    threshold: float = 0.40,
) -> bool:
    """
    Semantic major relevance: embed JD field description + major text, so sánh similarity.

    Chiến lược 2 tầng:
    1. Keyword fallback TRƯỚC: nếu major keywords khớp JD domain rõ ràng → True ngay.
       (Tránh false negative khi major text quá ngắn làm embedding kém tin cậy.)
    2. Semantic embedding: embed education text vs JD field text, threshold >= 0.40.

    Returns True nếu ít nhất 1 education entry phù hợp JD field.
    """
    if not cv_education:
        return False

    # Tầng 1: Keyword-based match — nhanh và chắc cho major ngắn
    if _major_keyword_match(cv_education, jd_data):
        return True

    # Tầng 2: Semantic embedding — cho trường hợp phức tạp hơn
    jd_struct = jd_data.get("structured", jd_data)
    # Dùng job_title + industry (ngắn, focused) thay vì toàn bộ JD text
    # để tránh "dilution" khi JD text quá dài → similarity bị kéo xuống
    jd_focused = " ".join(filter(None, [
        jd_struct.get("job_title", ""),
        jd_data.get("job_title", ""),
        jd_struct.get("industry", ""),
    ]))
    if not jd_focused.strip():
        return False

    # Build education texts — enrich major ngắn với context ngành
    edu_texts: List[str] = []
    for edu in cv_education:
        parts = [
            edu.get("degree", ""),
            edu.get("major", ""),
            edu.get("school", ""),
            edu.get("description", ""),
        ]
        edu_text = " ".join(filter(None, parts))
        edu_texts.append(edu_text)

    if not any(t.strip() for t in edu_texts):
        return False

    try:
        jd_emb = embedder.encode(jd_focused, normalize=True)
        edu_embs = embedder.encode_batch(edu_texts, normalize=True)
        for i in range(len(cv_education)):
            sim = float(np.dot(edu_embs[i], jd_emb))
            if sim >= threshold:
                return True
    except Exception as e:
        logger.warning(f"Semantic major relevance embedding failed: {e}")

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

    import datetime
    current_year = datetime.datetime.now().year

    cv_degree = 0
    cv_is_student = False  # đang học đại học (chưa tốt nghiệp)
    for edu in cv_data.get("education", []):
        text = f"{edu.get('degree', '')} {edu.get('major', '')} {edu.get('school', '')}".lower()
        for kw, val in degree_map.items():
            if kw in text:
                cv_degree = max(cv_degree, val)
        if edu.get("degree") or edu.get("major"):
            cv_degree = max(cv_degree, 2)
        # Detect sinh viên đang học: end year >= current year → chưa tốt nghiệp
        end_year_str = str(edu.get("end", "") or "")
        m_year = re.search(r"\d{4}", end_year_str)
        if m_year and int(m_year.group()) >= current_year:
            cv_is_student = True
            # Đang học đại học → treat như degree = 3 (sẽ tốt nghiệp)
            cv_degree = max(cv_degree, 3)

    # SEMANTIC MATCHING: thay keyword-based major relevance bằng embedding similarity
    cv_major_match = _semantic_major_relevance(
        cv_data.get("education", []), jd_data, embedder, threshold=0.40
    )

    cert_count = 0
    cv_text_lower = str(cv_data).lower()
    # BUG 4 FIX: Loại bỏ "kaggle" khỏi cert_keywords.
    # Kaggle là learning platform/competition platform, KHÔNG phải certification
    # như AWS Certified, PMP hay Scrum Master. Việc có "kaggle" trong CV text
    # (vd: kaggle competition, kaggle dataset) không nên count là cert.
    cert_keywords = [
        "aws certified", "google certified",
        "azure certified", "cisco certified", "oracle certified",
        "salesforce certified", "pmp certified", "pmp certificate",
        "scrum master", "deep learning specialization", "google data analytics",
        "certification", "certificate",
    ]
    for kw in cert_keywords:
        if kw in cv_text_lower:
            cert_count += 1

    # BUG 3 FIX: JD Intern thường viết "Sinh viên năm 3, 4" hoặc "đang học đại học"
    # thay vì "Cao đẳng/Đại học" → req_degree = 0 dù thực tế JD kỳ vọng SV đại học.
    # Khi req_degree = 0 mà JD có dấu hiệu intern/student → treat như req_degree = 3
    # để base điểm là 6.0 (đúng ngành) thay vì bị giảm về 4.0 (no req).
    jd_req_text_lower = req_text.lower()
    jd_is_intern_student = any(
        kw in jd_req_text_lower for kw in [
            "intern", "sinh viên", "student", "năm 3", "năm 4", "năm cuối",
            "fresher", "đang học", "chưa tốt nghiệp",
        ]
    )
    # Cũng check seniority field
    seniority_req_edu = (jd_struct.get("seniority") or "").lower()
    if not jd_is_intern_student and any(kw in seniority_req_edu for kw in ["intern", "fresher"]):
        jd_is_intern_student = True

    effective_req_degree = req_degree
    if req_degree == 0 and jd_is_intern_student:
        # JD dành cho sinh viên/intern: kỳ vọng ngầm là đang học đại học
        effective_req_degree = 3

    if effective_req_degree > 0:
        if cv_degree >= effective_req_degree:
            base = 6.0 if cv_major_match else 3.5
        elif cv_is_student and cv_degree >= effective_req_degree - 1:
            # Đang học, sắp đủ bằng → không penalize nặng
            base = 5.5 if cv_major_match else 3.0
        else:
            base = max(0.0, (cv_degree / max(effective_req_degree, 1)) * 4.0)
            if cv_major_match:
                base += 1.0
    else:
        base = 4.0 if cv_major_match else 2.5

    # Bonus cho sinh viên đang học đúng ngành với JD intern/fresher
    if cv_is_student and cv_major_match:
        base = min(base + 1.5, 8.0)  # tối đa 8 để còn chỗ cho cert bonus

    score = min(base + min(cert_count, 3) * 0.8, 10.0)

    major_note = "Ngành học phù hợp." if cv_major_match else "Ngành học không liên quan trực tiếp."
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
) -> Tuple[float, str]:
    """
    Score 0-10:
    - So sánh career objective trong CV với JD (job title, responsibilities, industry)
    - Semantic matching: embed và so sánh cosine similarity
    - Fallback keyword matching nếu embedding fail
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
            return 3.0, "CV không có mục tiêu nghề nghiệp. Không đủ thông tin để đánh giá (điểm mặc định 3/10)."
        # Dùng proxy text để tính similarity, nhưng cap tối đa 6/10 vì thiếu objective
        try:
            proxy_emb = embedder.encode(cv_proxy_text, normalize=True)
            jd_emb_fb = embedder.encode(jd_goal_text, normalize=True)
            sim_fb = float(np.clip(np.dot(proxy_emb, jd_emb_fb), 0.0, 1.0))
            SIM_MIN_FB, SIM_MAX_FB = 0.25, 0.65
            proxy_score = float(np.clip((sim_fb - SIM_MIN_FB) / (SIM_MAX_FB - SIM_MIN_FB) * 6.0, 0.0, 6.0))
            return round(proxy_score, 2), (
                f"CV không có mục tiêu nghề nghiệp. "
                f"Điểm proxy từ skills + kinh nghiệm (tối đa 6/10): {proxy_score:.1f}/10."
            )
        except Exception:
            return 3.0, "CV không có mục tiêu nghề nghiệp. Không thể tính điểm proxy (điểm mặc định 3/10)."

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
        cv_emb = embedder.encode(cv_objective, normalize=True)
        jd_emb = embedder.encode(jd_focused_text, normalize=True)
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
        cv_text_full = _build_cv_text(cv_data)
        jd_text_full = _build_jd_text(jd_data)
        cv_domain = _semantic_domain_detection(cv_text_full, embedder, threshold=0.40)
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

        exp_score, exp_rationale = _score_experience(
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
        edu_score, edu_rationale = _score_education(cv_data, jd_data, embedder)
        career_obj_score, career_obj_rationale = _score_career_objectives(
            cv_data, jd_data, embedder
        )
        company_score, company_rationale = _score_company_fit(cv_data, company_data, embedder)

        overall = round(min(exp_score + skills_score + edu_score + career_obj_score, 100.0))

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
        exp_score = skills_score = edu_score = career_obj_score = company_score = overall = 0
        exp_rationale = "Không thể tính điểm kinh nghiệm."
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
