# -*- coding: utf-8 -*-
"""
Enhanced CV Parser - Single-pass extraction with comprehensive skill extraction.

Key improvements:
- ONE LLM call per document (not two)
- Comprehensive extraction: structure + skills + experience analysis
- Post-processing: skill normalization via skill_normalizer
- Robust deduplication and type validation
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.feature.feature_up_cv.core.gemini_client import generate_content
from app.feature.feature_up_cv.core.utils import extract_first_json as _extract_first_json


def _build_cv_prompt(cv_text: str) -> str:
    return f"""
Bạn là hệ thống trích xuất thông tin CV chuyên nghiệp.
Mục tiêu: chuyển đổi text CV thành JSON có cấu trúc chuẩn cho CV-JD matching.

QUAN TRỌNG - QUY TẮC TRÍCH XUẤT SKILLS:
1. Đọc TOÀN BỘ CV text (không chỉ phần "Kỹ năng")
2. Trích xuất kỹ năng từ MỌI phần:
   - work_experience.highlights → đây là nguồn quan trọng nhất
   - projects.description / projects.technologies
   - education.certifications
   - phần "Kỹ năng" nếu có
3. PHÂN LOẠI kỹ năng (đặt vào đúng category):
   - TECHNICAL: ngôn ngữ lập trình, framework, database, cloud, devops, tools, AI/ML frameworks
   - DOMAIN: nghiệp vụ chuyên môn (sales, marketing, finance, logistics, consulting...)
   - SOFT: giao tiếp, làm việc nhóm, lãnh đạo, presentation
4. Năm hiện tại là 2026. Tính chính xác số năm kinh nghiệm.

QUAN TRỌNG - RÀNG BUỘC:
- CHỈ trả về 1 JSON object. KHÔNG có text/markdown nào khác. KHÔNG giải thích.
- Nếu không chắc chắn -> để "" hoặc [] (không bịa đặt).
- MỖI phần tử trong list "skills" PHẢI LÀ STRING thuần túy. Ví dụ: "Python", "Sales", "Docker"
- KHÔNG ĐƯA dict/objects vào trong list skills. Nếu muốn gắn mức độ -> dùng mastery_evidence
- Loại bỏ trùng lặp trong list. Giữ thứ tự quan trọng trước.
- Tên công nghệ chuẩn VIẾT HOA: "Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes", "TensorFlow", "PyTorch"

Schema (giữ đúng keys và types):
{{
  "personal_info": {{
    "name": "",
    "dob": "",
    "gender": "",
    "phone": "",
    "email": "",
    "address": ""
  }},
  "objective": "",
  "career_objectives": "",
  "education": [{{"school": "", "degree": "", "major": "", "start": "", "end": ""}}],
  "work_experience": [{{
    "company": "",
    "title": "",
    "start": "",
    "end": "",
    "highlights": []
  }}],
  "projects": [{{
    "name": "",
    "role": "",
    "start": "",
    "end": "",
    "description": "",
    "technologies": []
  }}],
  "skills": [],
  "technical_skills": [],
  "domain_skills": [],
  "soft_skills": [],
  "certifications": [],
  "evidence": {{
    "name": "",
    "email": "",
    "phone": "",
    "skills": []
  }}
}}

NOTE: career_objectives là mục tiêu nghề nghiệp dài hạn/công việc mong muốn (ví dụ: "Backend Engineer với 5 năm kinh nghiệm, mong muốn phát triển sâu hơn về AI/ML"). Trích xuất chính xác từ phần "Mục tiêu nghề nghiệp" hoặc "Career Objective" của CV. Nếu không có, để chuỗi rỗng "".

Few-shot (FORMAT reference):
INPUT: "Nguyễn Văn A. Backend Developer tại ABC Corp. 2020-2023. Python, FastAPI, PostgreSQL. Đạt KPI 120%. Giao tiếp tốt."
OUTPUT:
{{
  "personal_info": {{"name":"Nguyễn Văn A","dob":"","gender":"","phone":"","email":"","address":""}},
  "objective": "",
  "education": [],
  "work_experience": [{{"company":"ABC Corp","title":"Backend Developer","start":"2020","end":"2023","highlights":["Đạt KPI 120%"]}}],
  "projects": [],
  "skills": ["Python","FastAPI","PostgreSQL","Giao tiếp"],
  "technical_skills": ["Python","FastAPI","PostgreSQL"],
  "domain_skills": [],
  "soft_skills": ["Giao tiếp"],
  "certifications": [],
  "evidence": {{"name":"","email":"","phone":"","skills":["Python","FastAPI","PostgreSQL"]}}
}}

Self-check:
- CHỈ có JSON? Không có text ngoài JSON?
- Tất cả required keys có mặt?
- skills là list of STRING, không có dict/object?
- technical_skills, domain_skills, soft_skills là list of STRING?
- Không trùng lặp trong skills?

CV_TEXT (có thể bị cắt ngắn):
{cv_text[:8000]}
""".strip()


def _is_valid_skill(val: Any) -> bool:
    """Check if a value is a valid skill (non-empty string)."""
    return isinstance(val, str) and val.strip()


def _safe_str(val: Any, default: str = "") -> str:
    """Convert any value to string safely."""
    if isinstance(val, str):
        return val.strip()
    if val is None:
        return default
    return str(val).strip()


def _merge_skills(*lists: Any) -> List[str]:
    """Merge multiple skill lists, deduplicate, keep strings only."""
    seen: set = set()
    result: List[str] = []
    for lst in lists:
        if not isinstance(lst, (list, tuple)):
            continue
        for item in lst:
            s = _safe_str(item)
            if s and s.lower() not in seen:
                seen.add(s.lower())
                result.append(s)
    return result


def _fallback() -> Dict[str, Any]:
    return {
        "personal_info": {
            "name": "", "dob": "", "gender": "", "phone": "", "email": "", "address": ""
        },
        "objective": "",
        "career_objectives": "",
        "education": [],
        "work_experience": [],
        "projects": [],
        "skills": [],
        "technical_skills": [],
        "domain_skills": [],
        "soft_skills": [],
        "certifications": [],
        "evidence": {"name": "", "email": "", "phone": "", "skills": []},
    }


def llm_parser_cv(cv_text: str) -> Dict[str, Any]:
    """
    Single-pass CV parser:
      - ONE LLM call only
      - Extracts basic structure + all skill categories in one go
      - Post-processes with skill_normalizer for canonical form

    Returns structured CV JSON with comprehensive, normalized skills list.
    """
    if not cv_text or not cv_text.strip():
        return _fallback()

    prompt = _build_cv_prompt(cv_text)

    for attempt in range(3):
        raw = generate_content(prompt=prompt, step="llm_parser_cv")
        json_text = _extract_first_json(raw)
        if not json_text:
            continue
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, dict) and "personal_info" in parsed:
                result = parsed
                break
        except json.JSONDecodeError:
            continue
    else:
        return _fallback()

    # ── Post-processing: merge & normalize skills ───────────────────────────
    # Collect skills from all skill-related fields
    raw_skills = _merge_skills(
        result.get("skills", []),
        result.get("technical_skills", []),
        result.get("domain_skills", []),
        result.get("soft_skills", []),
        result.get("certifications", []),
    )

    # Also extract skills from work_experience highlights via regex
    try:
        from app.feature.feature_up_cv.core.skill_normalizer import extract_skills_from_text
        for exp in result.get("work_experience", []):
            for hl in exp.get("highlights", []):
                extra = extract_skills_from_text(str(hl))
                raw_skills = _merge_skills(raw_skills, extra)
        for proj in result.get("projects", []):
            for tech in proj.get("technologies", []):
                extra = extract_skills_from_text(str(tech))
                raw_skills = _merge_skills(raw_skills, extra)
    except Exception:
        pass  # skill_normalizer may not be available

    # Normalize via skill_normalizer if available
    try:
        from app.feature.feature_up_cv.core.skill_normalizer import normalize_skills_list
        result["skills"] = normalize_skills_list(raw_skills)
    except Exception:
        result["skills"] = raw_skills

    # Ensure all required top-level keys exist
    for key in ("objective", "career_objectives"):
        if key not in result:
            result[key] = ""
    for key in ("education", "work_experience", "projects"):
        if key not in result:
            result[key] = []
    for key in ("technical_skills", "domain_skills", "soft_skills", "certifications"):
        if key not in result:
            result[key] = []

    # Ensure evidence exists and has skills
    if "evidence" not in result or not isinstance(result["evidence"], dict):
        result["evidence"] = {}
    for field in ("name", "email", "phone", "skills"):
        if field not in result["evidence"]:
            result["evidence"][field] = ""

    # evidence.skills = top 20 skills
    result["evidence"]["skills"] = result["skills"][:20]

    # skill_metadata: mirror all skill categories
    result["skill_metadata"] = {
        "technical_skills": result.get("technical_skills", []),
        "domain_skills": result.get("domain_skills", []),
        "soft_skills": result.get("soft_skills", []),
        "certifications": result.get("certifications", []),
    }

    return result
