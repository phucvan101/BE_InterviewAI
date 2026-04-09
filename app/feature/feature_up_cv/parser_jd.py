from __future__ import annotations

import json
from typing import Any, Dict
from app.feature.feature_up_cv.gemini_client import generate_content


def _extract_first_json(text: str) -> str | None:
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
Bạn là chuyên gia phân tích mô tả công việc (JD). Mục tiêu: trích xuất JD thành dữ liệu có cấu trúc để phục vụ so khớp CV–JD.

Ràng buộc bắt buộc:
- CHỈ trả về 1 JSON object, KHÔNG có bất kỳ text/markdown nào khác.
- KHÔNG giải thích, KHÔNG nêu suy luận.
- Không chắc chắn -> để "" hoặc [] (KHÔNG bịa).
- Chuẩn hoá kỹ năng: keyword ngắn gọn, đúng tên công nghệ (vd: "Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes").
- Loại bỏ trùng lặp trong list, giữ thứ tự quan trọng trước.
- Ngôn ngữ: Tiếng Việt (trừ keyword công nghệ).

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
  "evidence": {{
    "job_title": "",
    "years_of_experience": "",
    "skills_required": [],
    "skills_preferred": [],
    "responsibilities": [],
    "requirements": []
  }}
}}

Few-shot (tham chiếu FORMAT):
JD_EXAMPLE: "Backend Engineer (FastAPI). 2+ năm. Python, FastAPI, PostgreSQL."
OUTPUT_EXAMPLE:
{{
  "job_title":"Backend Engineer",
  "location":"",
  "seniority":"",
  "years_of_experience":"2+",
  "employment_type":"",
  "skills_required":["Python","FastAPI","PostgreSQL"],
  "skills_preferred":[],
  "responsibilities":[],
  "requirements":[],
  "benefits":[],
  "industry":"",
  "keywords":["Backend","API"],
  "evidence":{{"job_title":"Backend Engineer (FastAPI)","years_of_experience":"2+","skills_required":["Python","FastAPI","PostgreSQL"],"skills_preferred":[],"responsibilities":[],"requirements":[]}}
}}

Self-check:
- Valid JSON only?
- No text outside JSON?

JD_TEXT:
{jd_text[:7000]}
""".strip()


def llm_parser_jd(jd_text: str, max_retry: int = 3) -> Dict[str, Any]:
    """
    LLM parse JD text.

    Trả về payload tối giản cho downstream matching:
    {
      "job_title": "...",
      "structured": { ... }
    }

    """
    prompt = _build_jd_prompt(jd_text)
    structured: Dict[str, Any] | None = None

    for _ in range(max_retry):
        raw = generate_content(prompt=prompt, step="llm_parser_jd")
        candidate = _extract_first_json(raw) or raw.strip()
        try:
            structured = json.loads(candidate)
            break
        except Exception:
            continue

    if structured is None:
        structured = {
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
            "evidence": {
                "job_title": "",
                "years_of_experience": "",
                "skills_required": [],
                "skills_preferred": [],
                "responsibilities": [],
                "requirements": [],
            },
        }

    return {
        "job_title": structured.get("job_title") or "Job Description",
        "structured": structured,
    }