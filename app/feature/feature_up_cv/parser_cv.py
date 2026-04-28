from __future__ import annotations

import json
from typing import Any, Dict

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


def _build_cv_prompt(cv_text: str) -> str:
    return f"""
You are an information extraction system for CV/Resume.
Goal: convert CV text into a structured JSON object for downstream CV-JD matching.

Hard rules:
- Output ONLY one JSON object. No extra text. No markdown fences.
- Do NOT explain. Do NOT include reasoning.
- If unsure, leave "" or [] (do not invent).
- Normalize skills to short keywords (e.g., "Python", "FastAPI", "SQL", "Docker", "AWS").
- Remove duplicates from lists.
- Always keep in mind that the current year is 2026, and perform the necessary calculations to determine the number of years.

Schema (keep keys & types exactly):
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
  "education": [{{"school":"", "degree":"", "major":"", "start":"", "end":""}}],
  "work_experience": [{{"company":"", "title":"", "start":"", "end":"", "highlights":[]}}],
  "projects": [{{"name":"", "role":"", "start":"", "end":"", "description":"", "technologies":[]}}],
  "skills": [],
  "evidence": {{
    "name": "",
    "email": "",
    "phone": "",
    "skills": []
  }}
}}

CV_TEXT (may be truncated):
{cv_text[:7000]}
""".strip()


def _validate_json(data: Dict[str, Any]) -> bool:
    required = ["personal_info", "education", "work_experience", "projects", "skills"]
    return isinstance(data, dict) and all(k in data for k in required)


def _fallback() -> Dict[str, Any]:
    return {
        "personal_info": {"name": "", "dob": "", "gender": "", "phone": "", "email": "", "address": ""},
        "objective": "",
        "education": [],
        "work_experience": [],
        "projects": [],
        "skills": [],
        "evidence": {"name": "", "email": "", "phone": "", "skills": []},
    }


def llm_parser_cv(cv_text: str, max_retry: int = 3) -> Dict[str, Any]:
    """LLM parse CV text -> structured CV JSON."""
    if not cv_text or not cv_text.strip():
        return _fallback()

    prompt = _build_cv_prompt(cv_text)
    for _ in range(max_retry):
        raw = generate_content(prompt=prompt, step="llm_parser_cv")
        json_text = _extract_first_json(raw)
        if not json_text:
            continue
        try:
            parsed = json.loads(json_text)
            if _validate_json(parsed):
                return parsed
        except Exception:
            continue

    return _fallback()