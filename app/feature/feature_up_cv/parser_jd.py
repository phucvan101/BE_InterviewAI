# -*- coding: utf-8 -*-
"""
Enhanced JD Parser - Multi-section skill extraction with importance ranking.

Key improvements:
- Extract skills from EVERY section (responsibilities, requirements, benefits, description)
- Distinguish MUST-HAVE (required) vs NICE-TO-HAVE (preferred) skills
- Skill importance scoring based on frequency and position
- Explicit skill context (why it's mentioned) for better matching
- Self-validation with schema checking
- Post-processing with skill normalization
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.feature.feature_up_cv.gemini_client import generate_content


def _extract_first_json(text: str) -> str | None:
    """Extract the first balanced JSON object from a string."""
    stack = 0
    start = None
    for i, c in enumerate(text):
        if c == "{":
            if stack == 0:
                start = i
            stack += 1
        elif c == "}":
            stack -= 1
            if stack == 0 and start is not None:
                return text[start : i + 1]
    return None


def _build_jd_prompt(jd_text: str) -> str:
    return f"""
Bạn là chuyên gia phân tích JD (Job Description) hàng đầu.
Mục tiêu: trích xuất TẤT CẢ kỹ năng từ mọi phần của JD một cách CHÍNH XÁC và ĐẦY ĐỦ.

QUAN TRỌNG - Phương pháp trích xuất:

1. Đọc TOÀN BỘ JD, không chỉ phần "Yêu cầu kỹ năng"
2. Trích xuất kỹ năng từ MỌI phần:
   - responsibilities (nhiệm vụ) → kỹ năng CẦN CÓ
   - requirements (yêu cầu) → kỹ năng BẮT BUỘC
   - benefits (phúc lợi) → có thể chứa tech stack của công ty
   - job_title, description → kỹ năng implied
   - keywords, industry → kỹ năng domain
3. PHÂN LOẠI chính xác:
   - skills_required (MUST-HAVE): kỹ năng bắt buộc, không có thì không đạt
   - skills_preferred (NICE-TO-HAVE): kỹ năng ưu tiên, có thì được đánh giá cao hơn
4. Đánh dấu MỨC ĐỘ QUAN TRỌNG:
   - CRITICAL: đề cập nhiều lần, trong requirements rõ ràng
   - IMPORTANT: đề cập trong responsibilities hoặc requirements
   - BONUS: đề cập trong benefits hoặc nice-to-have
5. Kỹ năng phải chuẩn tên quốc tế, VIẾT HOA đúng:
   - Ngôn ngữ: "Python", "JavaScript", "TypeScript", "Java", "C++", "Go", "Rust", "C#", "Swift", "Kotlin"
   - Framework: "React", "Vue.js", "Angular", "Django", "FastAPI", "Spring Boot", "Next.js", "NestJS"
   - Database: "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra", "Neo4j"
   - Cloud/DevOps: "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins", "Kafka"
   - AI/ML: "TensorFlow", "PyTorch", "Scikit-learn", "OpenCV", "YOLO", "LangChain", "Hugging Face", "CUDA"
   - Tools: "Git", "GitHub", "Jira", "Linux", "REST API", "GraphQL"

6. VỀ CẤP BẬC (seniority) - phải xác định CHÍNH XÁC:
   - "Junior/Fresher": 0-2 năm kinh nghiệm
   - "Mid-level": 2-4 năm kinh nghiệm
   - "Senior": 4-7 năm kinh nghiệm
   - "Lead/Principal": 7+ năm kinh nghiệm
   - "Manager": quản lý team, không chỉ technical

7. VỀ KEYWORDS/INDUSTRY:
   - Trích xuất tất cả từ khóa ngành: "AI", "Computer Vision", "Fintech", "E-commerce"...
   - Các domain keywords: "Real-time", "Scalable", "Microservices", "API-first"...

Ràng buộc:
- CHỈ trả về 1 JSON object. KHÔNG text/markdown khác. KHÔNG giải thích.
- Không chắc chắn -> "" hoặc [] (không bịa).
- Loại bỏ trùng lặp.
- Giữ thứ tự quan trọng trước trong list.

Schema output:
{{
  "job_title": "",
  "location": "",
  "seniority": "",
  "years_of_experience": "",
  "employment_type": "",
  "skills_required": [],
  "skills_preferred": [],
  "responsibilities": [],
  "requirements": [],
  "benefits": [],
  "industry": "",
  "keywords": [],
  "skill_importance": {{}},
  "experience_context": "",
  "culture_keywords": [],
  "evidence": {{
    "job_title": "",
    "years_of_experience": "",
    "skills_required": [],
    "skills_preferred": [],
    "responsibilities": [],
    "requirements": []
  }}
}}

NOTE: evidence là bản sao các trường chính, KHÔNG phải nơi để bổ sung thêm skills.
skills_required và skills_preferred trong evidence phải giống hệt trong structured chính.

QUAN TRỌNG - Không trùng lặp:
- `evidence` phải đồng bộ với các trường chính, không thêm skills_extra
- Mỗi skill chỉ nên xuất hiện trong đúng 1 danh sách (required HOẶC preferred, không cả 2)

Ví dụ Few-shot:
INPUT: "Backend Engineer. 3+ years. Python, FastAPI, PostgreSQL required. Docker, AWS preferred."
OUTPUT:
{{
  "job_title": "Backend Engineer",
  "location": "",
  "seniority": "Mid-level",
  "years_of_experience": "3+",
  "employment_type": "",
  "skills_required": ["Python", "FastAPI", "PostgreSQL", "REST API", "Git"],
  "skills_preferred": ["Docker", "AWS", "Kubernetes", "Redis", "MongoDB"],
  "responsibilities": ["Phát triển API", "Thiết kế database", "Tối ưu hiệu suất"],
  "requirements": ["3+ năm kinh nghiệm backend", "Thành thạo Python"],
  "benefits": [],
  "industry": "Software/Tech",
  "keywords": ["Backend", "API", "Microservices"],
  "skill_importance": {{"Python": "CRITICAL", "FastAPI": "CRITICAL", "PostgreSQL": "IMPORTANT", "Docker": "BONUS"}},
  "experience_context": "Cần 3+ năm kinh nghiệm backend development với Python",
  "culture_keywords": [],
  "evidence": {{"job_title":"Backend Engineer","years_of_experience":"3+","skills_required":["Python","FastAPI","PostgreSQL"],"skills_preferred":["Docker","AWS"],"responsibilities":[],"requirements":[]}}
}}

Self-check:
- Đã đọc toàn bộ JD chưa?
- Skills_required có thiếu kỹ năng nào từ responsibilities không?
- Tất cả skills có đúng chính tả không?
- seniority và years_of_experience có nhất quán không?
- skill_importance đánh đúng mức độ cho tất cả skills trong skills_required và skills_preferred

JD_TEXT:
{jd_text[:8000]}
""".strip()


def _validate_jd_schema(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("job_title", "skills_required", "skills_preferred", "industry"):
        if key not in data:
            return False
    return True


def _fallback_structured() -> Dict[str, Any]:
    return {
        "job_title": "",
        "location": "",
        "seniority": "",
        "years_of_experience": "",
        "employment_type": "",
        "skills_required": [],
        "skills_preferred": [],
        "responsibilities": [],
        "requirements": [],
        "benefits": [],
        "industry": "",
        "keywords": [],
        "skill_importance": {},
        "experience_context": "",
        "culture_keywords": [],
        "evidence": {
            "job_title": "",
            "years_of_experience": "",
            "skills_required": [],
            "skills_preferred": [],
            "responsibilities": [],
            "requirements": [],
        },
    }


def llm_parser_jd(jd_text: str) -> Dict[str, Any]:
    """
    Enhanced JD parser with multi-section skill extraction.

    Returns:
    {
        "job_title": "Senior AI Engineer",
        "structured": {
            ...full structured data with skill_importance...
        }
    }
    """
    prompt = _build_jd_prompt(jd_text)
    structured: Dict[str, Any] | None = None

    for attempt in range(3):
        raw = generate_content(prompt=prompt, step="llm_parser_jd")
        candidate = _extract_first_json(raw) or raw.strip()
        try:
            parsed = json.loads(candidate)
            if _validate_jd_schema(parsed):
                structured = parsed
                break
        except json.JSONDecodeError:
            continue

    if structured is None:
        structured = _fallback_structured()

    # Ensure nested evidence exists
    if "evidence" not in structured:
        structured["evidence"] = {}
    if "skill_importance" not in structured:
        structured["skill_importance"] = {}
    if "culture_keywords" not in structured:
        structured["culture_keywords"] = []

    # Ensure all list fields are lists
    for list_field in (
        "skills_required", "skills_preferred", "responsibilities",
        "requirements", "benefits", "keywords", "culture_keywords"
    ):
        if list_field in structured and not isinstance(structured[list_field], list):
            structured[list_field] = []

    # Post-process: ensure evidence mirrors the structured fields exactly
    evidence = structured.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    evidence["skills_required"] = [s for s in structured.get("skills_required", []) if isinstance(s, str)]
    evidence["skills_preferred"] = [s for s in structured.get("skills_preferred", []) if isinstance(s, str)]
    evidence["responsibilities"] = [r for r in structured.get("responsibilities", []) if isinstance(r, str)]
    evidence["requirements"] = [r for r in structured.get("requirements", []) if isinstance(r, str)]
    evidence["job_title"] = structured.get("job_title", "")
    evidence["years_of_experience"] = structured.get("years_of_experience", "")
    structured["evidence"] = evidence

    return {
        "job_title": structured.get("job_title") or "Job Description",
        "structured": structured,
    }
