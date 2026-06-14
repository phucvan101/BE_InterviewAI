# -*- coding: utf-8 -*-
"""
Enhanced Company Parser - Tech stack and culture focused extraction.

Key improvements:
- Tech stack extraction from all text (not just explicit "tech" section)
- Industry classification with nuance (e.g., "AI/ML", "Fintech", "E-commerce")
- Company culture and values normalization
- Products/services keywords for domain matching
- Size and growth signals
- Self-validation with schema checking
"""


import json
import re
from typing import Any, Dict

from app.feature.feature_up_cv.core.gemini_client import generate_content
from app.feature.feature_up_cv.core.utils import extract_first_json as _extract_first_json


def _build_company_prompt(text: str) -> str:
    template = """
Bạn là chuyên gia nghiên cứu doanh nghiệp.
Mục tiêu: trích xuất thông tin công ty thành JSON cấu trúc để phục vụ phân tích CV-JD-Company matching.

QUAN TRỌNG - Phương pháp trích xuất:

1. Đọc TOÀN BỘ tài liệu (không chỉ phần "Công nghệ")
2. Trích xuất TECH STACK từ MỌI nơi:
   - Trong mô tả sản phẩm/dịch vụ
   - Trong job postings hoặc hiring info
   - Trong case studies / achievements
   - Trong "about us" / company description
   - Trong technical blog posts
3. PHÂN LOẠI tech stack:
   - PRIMARY_LANGUAGES: ngôn ngữ lập trình chính
   - FRAMEWORKS: web/mobile frameworks
   - DATABASES: database systems
   - INFRASTRUCTURE: cloud, devops, infrastructure tools
   - AI/ML: nếu công ty làm AI/ML
   - SPECIALIZED: domain-specific tools (Fintech tools, design tools, etc.)
4. INDUSTRY CLASSIFICATION:
   - Primary industry (e.g., "AI/ML", "Fintech", "E-commerce", "SaaS", "Gaming")
   - Sub-industry nếu có
   - Business model: B2B, B2C, B2B2C, Marketplace
5. CULTURE & VALUES:
   - Work style: Remote-first, Hybrid, Onsite, Flexible
   - Tech culture: Startup, Enterprise, Research-focused
   - Engineering values: CI/CD, Code review, Testing, Documentation

6. VỀ TECH STACK - kỹ năng phải chuẩn VIẾT HOA:
   - Languages: "Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "C#"
   - Frameworks: "React", "Vue.js", "Angular", "Django", "FastAPI", "Spring Boot"
   - Databases: "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch"
   - Cloud: "AWS", "GCP", "Azure", "Docker", "Kubernetes"
   - AI/ML: "TensorFlow", "PyTorch", "Hugging Face", "OpenCV", "LangChain"
   - Tools: "Git", "Kafka", "Airflow", "Terraform", "Prometheus"

7. PRODUCTS/SERVICES:
   - Tên sản phẩm chính
   - Mô tả ngắn gọn
   - Target customers
   - Key features

Ràng buộc:
- CHỈ trả về 1 JSON object. KHÔNG text/markdown khác. KHÔNG giải thích.
- Không có thông tin -> "" hoặc [] (không bịa).
- Deduplicate trong list.
- Ngôn ngữ: Tiếng Việt (trừ tech keywords).

Schema output:
{{
  "company_name": "",
  "industry": "",
  "sub_industry": "",
  "business_model": "",
  "description": "",
  "mission": "",
  "values": [],
  "work_culture": "",
  "tech_culture": "",
  "remote_policy": "",
  "key_skills": [],
  "technologies": [],
  "primary_languages": [],
  "frameworks": [],
  "databases": [],
  "infrastructure": [],
  "ai_ml_stack": [],
  "products": [],
  "target_customers": [],
  "company_size": "",
  "growth_stage": "",
  "company_culture": "",
  "key_achievements": [],
  "engineering_practices": []
}}

Few-shot:
INPUT: "FPT Software - IT outsourcing company. Java, .NET, Python. AWS, GCP. AI/ML solutions."
OUTPUT:
{{
  "company_name": "FPT Software",
  "industry": "IT Outsourcing",
  "sub_industry": "Software Development",
  "business_model": "B2B",
  "description": "IT outsourcing company",
  "mission": "",
  "values": [],
  "work_culture": "Offshore development",
  "tech_culture": "Enterprise",
  "remote_policy": "",
  "key_skills": ["Java", ".NET", "Python", "AWS", "GCP", "AI/ML"],
  "technologies": ["Java", ".NET", "Python", "AWS", "GCP"],
  "primary_languages": ["Java", "Python", ".NET"],
  "frameworks": [],
  "databases": [],
  "infrastructure": ["AWS", "GCP"],
  "ai_ml_stack": ["AI/ML"],
  "products": [],
  "target_customers": ["International enterprises"],
  "company_size": "",
  "growth_stage": "",
  "company_culture": "Offshore IT outsourcing",
  "key_achievements": [],
  "engineering_practices": []
}}

Self-check:
- Đã đọc toàn bộ text chưa?
- Tech stack có thiếu không?
- Industry classification đúng chưa?
- Spelling của tech keywords đúng chưa?

DOCUMENT_TEXT:
"""
    return template + text[:8000] + """

"""


def _validate_company_schema(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    required = ["company_name", "industry", "key_skills", "technologies"]
    return all(k in data for k in required)


def _fallback() -> Dict[str, Any]:
    return {
        "success": False,
        "error": "Failed to parse company JSON",
        "company_name": "",
        "industry": "",
        "sub_industry": "",
        "business_model": "",
        "description": "",
        "mission": "",
        "values": [],
        "work_culture": "",
        "tech_culture": "",
        "remote_policy": "",
        "key_skills": [],
        "technologies": [],
        "primary_languages": [],
        "frameworks": [],
        "databases": [],
        "infrastructure": [],
        "ai_ml_stack": [],
        "products": [],
        "target_customers": [],
        "company_size": "",
        "growth_stage": "",
        "company_culture": "",
        "key_achievements": [],
        "engineering_practices": [],
    }


def llm_parser_company(text: str) -> Dict[str, Any]:
    """
    Enhanced company parser with tech stack and culture extraction.
    Returns structured company JSON for CV-JD-Company matching.
    """
    prompt = _build_company_prompt(text)

    for attempt in range(2):
        raw = generate_content(prompt=prompt, step="llm_parser_company")
        response_text = raw.strip()
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text, re.DOTALL)
            if json_match:
                company_info = json.loads(json_match.group(0))
            else:
                company_info = json.loads(response_text)

            if _validate_company_schema(company_info):
                company_info["success"] = True
                return company_info
        except Exception:
            continue

    result = _fallback()
    result["success"] = False
    result["error"] = "Failed to parse company JSON after retries"
    return result
