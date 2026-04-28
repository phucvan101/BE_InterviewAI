# -*- coding: utf-8 -*-
"""
Extract company research information from documents
- Industry/Field
- Company Mission
- Values
- Culture
- Key achievements
- Skills/Technologies used
"""

import json
import re
from pathlib import Path
from app.feature.feature_up_cv.gemini_client import generate_content
from app.feature.feature_up_cv.text_extract import extract_text_auto, UnsupportedFileTypeError

def _build_company_prompt(text: str) -> str:
    return f"""
Bạn là hệ thống trích xuất thông tin công ty từ tài liệu (company research / brochure / profile).
Mục tiêu: tạo JSON cấu trúc để dùng làm ngữ cảnh cho phân tích phù hợp CV–JD.

Ràng buộc bắt buộc:
- CHỈ trả về 1 JSON object, KHÔNG có text/markdown nào khác.
- KHÔNG giải thích, KHÔNG nêu suy luận.
- Nếu không có thông tin -> "" hoặc [] (không bịa).
- Danh sách kỹ năng/công nghệ phải là keyword ngắn gọn, không trùng lặp.
- Ngôn ngữ: Tiếng Việt (trừ keyword công nghệ).

Schema:
{{
  "company_name": "",
  "industry": "",
  "description": "",
  "mission": "",
  "values": [],
  "key_skills": [],
  "technologies": [],
  "company_culture": "",
  "key_achievements": [],
  "evidence": {{
    "company_name": "",
    "industry": "",
    "key_skills": [],
    "technologies": []
  }}
}}

Few-shot (format reference only):
DOC_EXAMPLE:
"ABC Tech - Lĩnh vực Fintech. Công nghệ: Java, Spring, Kafka. Giá trị: Minh bạch, Đổi mới."
OUTPUT_EXAMPLE:
{{
  "company_name":"ABC Tech",
  "industry":"Fintech",
  "description":"",
  "mission":"",
  "values":["Minh bạch","Đổi mới"],
  "key_skills":[],
  "technologies":["Java","Spring","Kafka"],
  "company_culture":"",
  "key_achievements":[],
  "evidence":{{"company_name":"ABC Tech","industry":"Fintech","key_skills":[],"technologies":["Java","Spring","Kafka"]}}
}}

Self-check:
- Valid JSON only?
- Correct schema types?
- No text outside JSON?

DOCUMENT_TEXT (may be truncated):
{text[:7000]}
""".strip()


def llm_parser_company(text: str, max_retry: int = 2) -> dict:
    """
    LLM parse company text -> structured company JSON.
    Renamed from previous internal model call flow.
    """
    prompt = _build_company_prompt(text)
    for _ in range(max_retry):
        raw = generate_content(prompt=prompt, step="llm_parser_company")
        response_text = raw.strip()
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text, re.DOTALL)
            if json_match:
                company_info = json.loads(json_match.group(0))
            else:
                company_info = json.loads(response_text)

            company_info["success"] = True
            return company_info
        except Exception:
            continue

    return {
        "success": False,
        "error": "Failed to parse company JSON",
        "company_name": "",
        "industry": "",
        "description": "",
        "mission": "",
        "values": [],
        "key_skills": [],
        "technologies": [],
        "company_culture": "",
        "key_achievements": [],
    }

if __name__ == "__main__":
    pass